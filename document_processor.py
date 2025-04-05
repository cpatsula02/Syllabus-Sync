import os
import re
import nltk
import logging
import pdfplumber
from docx import Document
from typing import List, Dict, Tuple, Any, Optional
from nltk.corpus import stopwords

# Initialize NLTK
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
    nltk.download('punkt')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise ValueError(f"Unable to extract text from PDF: {str(e)}")
    
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a DOCX file."""
    try:
        doc = Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {str(e)}")
        raise ValueError(f"Unable to extract text from DOCX: {str(e)}")

def extract_text(file_path: str) -> str:
    """Extract text from a document based on its file extension."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()

def extract_checklist_items(text: str) -> List[str]:
    """
    Extract checklist items from the checklist document.
    Only extract numbered or bulleted items, excluding any other text.
    """
    # Define patterns for numbered or bulleted items
    patterns = [
        r'^\s*\d+\.\s*(.*?)(?=\n\s*\d+\.|\n\s*$|$)',  # Numbered items (1. Item)
        r'^\s*[a-zA-Z]\.\s*(.*?)(?=\n\s*[a-zA-Z]\.|\n\s*$|$)',  # Letter items (a. Item)
        r'^\s*•\s*(.*?)(?=\n\s*•|\n\s*$|$)',  # Bullet items (• Item)
        r'^\s*\*\s*(.*?)(?=\n\s*\*|\n\s*$|$)',  # Asterisk items (* Item)
        r'^\s*-\s*(.*?)(?=\n\s*-|\n\s*$|$)',  # Dash items (- Item)
        r'^\s*o\s*(.*?)(?=\n\s*o|\n\s*$|$)',  # Circle items (o Item)
    ]
    
    items = []
    lines = text.split('\n')
    
    # First pass: extract items based on patterns
    for pattern in patterns:
        for line in lines:
            line = line.strip()
            matches = re.findall(pattern, line, re.MULTILINE)
            items.extend([match.strip() for match in matches if match.strip()])
    
    # Second pass: if no items found with patterns, try parsing lines directly
    if not items:
        current_item = ""
        for line in lines:
            line = line.strip()
            
            # Check if line starts with a potential list marker
            if re.match(r'^\s*(\d+\.|[a-zA-Z]\.|•|\*|-|o)\s+', line):
                if current_item:
                    items.append(current_item)
                current_item = re.sub(r'^\s*(\d+\.|[a-zA-Z]\.|•|\*|-|o)\s+', '', line)
            elif current_item and line:  # Continue previous item if it's not a new marker
                current_item += " " + line
        
        # Add the last item if exists
        if current_item:
            items.append(current_item)
    
    # Remove duplicate items and short/invalid entries
    unique_items = []
    for item in items:
        item = item.strip()
        if (
            item and len(item) > 5  # Skip very short entries
            and item not in unique_items
            and not item.startswith('Page')  # Skip page numbers
            and not re.match(r'^[\d\s]+$', item)  # Skip items with only numbers
        ):
            unique_items.append(item)
    
    return unique_items

def check_item_in_document(item: str, document_text: str) -> bool:
    """
    Advanced semantic matching with strict validation for critical elements.
    Uses multiple strategies including header recognition, semantic equivalence,
    and specific pattern validation for critical items.
    """
    document_lower = document_text.lower()
    item_lower = item.lower()
    
    # Check for direct matches
    if item_lower in document_lower:
        return True
    
    # Extract core concepts from the item and look for them in the document
    item_concepts = extract_core_concepts(item_lower)
    if not item_concepts:
        return False
    
    # Get document sections
    sections = extract_document_sections(document_lower)
    for section_title, section_content in sections.items():
        # Check if section title is related to the item
        if sections_are_related(section_title, item_concepts):
            # Check if section content contains the concepts
            if content_contains_concepts(section_content, item_concepts):
                return True
    
    # Special handling for common policy types
    policy_type = extract_policy_type(item_lower)
    if policy_type:
        policy_pattern = rf"{policy_type}\s+(policy|policies|guidelines|requirements)"
        return bool(re.search(policy_pattern, document_lower))
    
    # Advanced pattern matching for remaining cases
    return check_special_entity_patterns(item_lower, document_lower)

def extract_core_concepts(text):
    """Extract core concepts from text for semantic matching."""
    # Remove common stopwords and keep only significant terms
    words = nltk.word_tokenize(text.lower())
    filtered_words = [w for w in words if w.isalnum() and w not in stopwords.words('english')]
    
    # Focus on key descriptive terms most likely to identify concepts
    return [word for word in filtered_words if len(word) > 3]

def extract_document_sections(document_text):
    """Extract sections with their titles and content from the document."""
    # Look for potential section headers (uppercase words followed by newline, numbered sections, etc.)
    section_patterns = [
        r'([A-Z][A-Z\s]{3,}[A-Z])[\s\n:]+',  # ALL CAPS HEADERS
        r'(\d+\.\s+[A-Za-z\s]{3,}[a-zA-Z])[\s\n:]+',  # Numbered headers like "1. Section Title"
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?):\s*\n',  # Title Case Headers:
    ]
    
    sections = {}
    remaining_text = document_text
    
    for pattern in section_patterns:
        matches = list(re.finditer(pattern, remaining_text))
        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            start_pos = match.end()
            
            # Determine end of section
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(remaining_text)
            
            # Extract section content
            section_content = remaining_text[start_pos:end_pos].strip()
            sections[section_title.lower()] = section_content
    
    # If no sections found with patterns, try a simpler approach
    if not sections:
        lines = document_text.split('\n')
        current_section = 'main'
        current_content = []
        
        for line in lines:
            line = line.strip()
            if line and line == line.upper() and len(line) > 10:  # Potential header
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.lower()
                current_content = []
            else:
                current_content.append(line)
        
        # Add the last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
    
    return sections

def sections_are_related(section_title, item_concepts):
    """Check if a section title is related to the concepts in the checklist item."""
    section_words = nltk.word_tokenize(section_title.lower())
    
    # Check for concept overlaps
    for concept in item_concepts:
        if concept in section_words:
            return True
            
    # Check for specific concept pairs that commonly appear together
    related_concepts = {
        'grade': ['distribution', 'assessment', 'evaluation', 'weight'],
        'policy': ['late', 'missed', 'attendance', 'academic', 'misconduct'],
        'schedule': ['class', 'weekly', 'lecture', 'topic'],
        'instructor': ['name', 'contact', 'email', 'office', 'hours'],
        'textbook': ['required', 'readings', 'materials', 'book'],
    }
    
    for concept, related in related_concepts.items():
        if concept in section_words:
            for item_concept in item_concepts:
                if item_concept in related:
                    return True
    
    return False

def content_contains_concepts(section_content, item_concepts):
    """Check if section content contains the concepts from the checklist item."""
    content_words = nltk.word_tokenize(section_content.lower())
    
    # Count matches to determine relevance
    matches = 0
    for concept in item_concepts:
        if concept in content_words:
            matches += 1
    
    # If at least half of the concepts match, consider it related
    return matches >= len(item_concepts) / 2

def extract_policy_type(item_text):
    """Extract the type of policy from policy-related checklist items."""
    policy_types = [
        'academic integrity', 'late', 'missed', 'attendance', 
        'participation', 'plagiarism', 'misconduct', 'accessibility',
        'accommodation', 'diversity', 'inclusion'
    ]
    
    for policy in policy_types:
        if policy in item_text:
            return policy
    
    return None

def find_original_text(lowercase_text, original_document):
    """
    Find the original text (with correct case) from the lowercase version.
    This helps preserve the original formatting when displaying matches.
    """
    # If the lowercase text is too long, it might be difficult to find exact matches
    if len(lowercase_text) > 300:
        # Try to find the start of the passage in the original document
        start_words = lowercase_text[:50].split()
        for i in range(min(5, len(start_words))):
            search_phrase = ' '.join(start_words[i:i+3])
            start_idx = original_document.lower().find(search_phrase)
            if start_idx >= 0:
                # Extract a reasonable-sized context
                return original_document[start_idx:start_idx + len(lowercase_text)]
        
        # Fallback to the lowercase version if we can't find a good match
        return lowercase_text
    
    # For shorter text, we can be more precise
    start_idx = original_document.lower().find(lowercase_text)
    if start_idx >= 0:
        return original_document[start_idx:start_idx + len(lowercase_text)]
    
    return lowercase_text

def find_best_keyword_section(document_text, keywords):
    """
    Find the section of the document that contains the most keywords.
    Returns a relevant excerpt from the document.
    """
    document_lower = document_text.lower()
    best_score = 0
    best_excerpt = ""
    
    # Split document into potential sections
    paragraphs = re.split(r'\n\s*\n', document_lower)
    
    for paragraph in paragraphs:
        if len(paragraph.strip()) < 10:  # Skip very short paragraphs
            continue
        
        # Count keyword matches
        score = sum(1 for keyword in keywords if keyword in paragraph)
        
        # If this paragraph has more keywords than previous best, update
        if score > best_score:
            best_score = score
            best_excerpt = paragraph
    
    # If we found a good match, get the original text with proper case
    if best_score > 0:
        return find_original_text(best_excerpt, document_text)
    
    return ""

def check_special_entity_patterns(item, document, additional_context=""):
    """
    Enhanced pattern matching with context awareness and table recognition.
    Supports various document formats and considers additional context.
    """
    # Check for instructor email requirement
    if 'instructor' in item and 'email' in item:
        # Look for email patterns in the document
        email_pattern = r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b'
        instructor_pattern = r'(instructor|professor|teacher|faculty)(.{0,30})(email|contact|reach)'
        
        # Look for email near instructor context
        instructor_matches = re.finditer(instructor_pattern, document, re.IGNORECASE)
        for match in instructor_matches:
            context_start = max(0, match.start() - 100)
            context_end = min(len(document), match.end() + 100)
            context = document[context_start:context_end]
            
            if re.search(email_pattern, context):
                return True
    
    # Check for grade distribution table
    if ('grade' in item and 'distribution' in item) or 'weight' in item:
        # Check for table patterns
        table_patterns = [
            r'\|\s*Assessment\s*\|\s*Weight\s*\|',  # Markdown table header
            r'Component\s+Weight',  # Simple table format
            r'(\w+\s+){1,3}:\s*\d{1,3}\s*%',  # Component: XX% format
            r'\d{1,3}\s*%\s*-\s*(\w+\s+){1,3}',  # XX% - Component format
        ]
        
        for pattern in table_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Check for specific formatting requirements
    if 'formatted' in item or 'format' in item:
        # Check for page numbering, margins, font specifications
        format_patterns = [
            r'(page|margin|font|spacing)(.{0,30})(requirement|specification)',
            r'(format|formatting)(.{0,30})(guide|requirement|instruction)',
        ]
        
        for pattern in format_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Check for learning outcomes
    if 'learning' in item and ('outcome' in item or 'objective' in item):
        outcome_patterns = [
            r'learning\s+outcomes?',
            r'course\s+objectives?',
            r'students\s+will\s+(be\s+able\s+to|learn|understand|demonstrate)',
            r'by\s+the\s+end\s+of\s+this\s+course',
        ]
        
        for pattern in outcome_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Add context-specific checks based on additional_context if provided
    if additional_context:
        context_lower = additional_context.lower()
        if 'graduate course' in context_lower and 'graduate' in item.lower():
            grad_patterns = [
                r'graduate(\s+level|\s+student|\s+program|\s+requirement)',
                r'master\'?s(\s+program|\s+degree|\s+requirement)',
                r'ph\.?d\.?(\s+student|\s+program|\s+requirement)',
            ]
            
            for pattern in grad_patterns:
                if re.search(pattern, document, re.IGNORECASE):
                    return True
    
    return False

def find_matching_excerpt(item, document_text):
    """
    Find a relevant excerpt in the document that matches the given checklist item.

    This function acts as a university academic reviewer, focusing on whether the 
    requirement described in the checklist item is meaningfully fulfilled in the 
    course outline. It identifies the exact section or sentence(s) from the course 
    outline that fulfill the requirement.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses the requirement.

    Args:
        item: The checklist item to find in the document
        document_text: The full text of the document to search

    Returns:
        A tuple of (found, excerpt) where:
        - found: Boolean indicating if a match was found
        - excerpt: String containing the excerpt with matching keywords highlighted,
                  or None if no match was found
    """
    # Extract key concepts from the checklist item
    item_lower = item.lower()
    keywords = [word for word in re.findall(r'\b\w+\b', item_lower) 
               if word not in stopwords.words('english') and len(word) > 3]
    
    # Add additional terms based on common university document sections
    if 'instructor' in item_lower:
        keywords.extend(['professor', 'teacher', 'faculty', 'staff', 'contact'])
    elif 'grade' in item_lower or 'assessment' in item_lower:
        keywords.extend(['evaluation', 'score', 'marking', 'weight', 'distribution'])
    elif 'policy' in item_lower:
        keywords.extend(['guideline', 'procedure', 'rule', 'regulation'])
    elif 'textbook' in item_lower:
        keywords.extend(['book', 'reading', 'material', 'resource'])
    elif 'schedule' in item_lower:
        keywords.extend(['timeline', 'calendar', 'weekly', 'session', 'class'])
    
    # Special handling for grade distribution tables
    if ('grade' in item_lower and 'distribution' in item_lower) or 'weight' in item_lower:
        found, grade_table = identify_grade_distribution_table(document_text)
        if found:
            return True, f"<span style='background-color: #c2f0c2;'><strong>Grade Distribution Table Found:</strong></span><br>{grade_table}"
    
    # Special handling for email patterns
    if 'instructor' in item_lower and 'email' in item_lower:
        email_pattern = r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b'
        instructor_pattern = r'(instructor|professor|teacher|faculty)(.{0,30})(email|contact|reach)'
        
        # Look for email near instructor context
        instructor_matches = re.finditer(instructor_pattern, document_text.lower(), re.IGNORECASE)
        for match in instructor_matches:
            context_start = max(0, match.start() - 100)
            context_end = min(len(document_text), match.end() + 100)
            context = document_text[context_start:context_end]
            
            email_matches = re.finditer(email_pattern, context, re.IGNORECASE)
            for email_match in email_matches:
                # Format the result with highlighting
                result = context
                email = email_match.group(0)
                
                # Add highlighting for email and instructor terms
                result = result.replace(email, f"<span style='background-color: #c2f0c2;'>{email}</span>")
                for term in ['instructor', 'professor', 'teacher', 'faculty']:
                    if term in result.lower():
                        pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                        result = pattern.sub(f"<span style='background-color: #c2f0c2;'>{term}</span>", result)
                
                return True, result
    
    # Find the best section with the most keywords
    best_excerpt = find_best_keyword_section(document_text, keywords)
    
    if not best_excerpt:
        return False, None
    
    # Highlight matching keywords in the excerpt
    highlighted_excerpt = best_excerpt
    for keyword in keywords:
        if len(keyword) > 3:  # Only highlight meaningful words, not short ones
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
            highlighted_excerpt = pattern.sub(f"<span style='background-color: #c2f0c2;'>{keyword}</span>", highlighted_excerpt)
    
    return True, highlighted_excerpt

def identify_grade_distribution_table(document_text: str) -> Tuple[bool, str]:
    """
    Specialized function to identify and extract grade distribution table information.
    Returns a tuple of (found, table_text).
    """
    document_lower = document_text.lower()
    
    # Look for sections likely to contain grade distribution
    section_titles = [
        "grade distribution", 
        "grading system", 
        "assessment", 
        "evaluation",
        "course components",
        "course work",
        "grading scheme"
    ]
    
    # Look for structured grade content in the document
    grade_patterns = [
        # Standard table indicators with percentages
        r'(?:\w+\s+){1,4}(?:(?:is|are|will be) worth|:|\s+-\s+)\s*\d{1,3}%',
        r'\d{1,3}\s*%\s*(?:-|–|:|\s+)\s*(?:\w+\s+){1,4}',
        r'(?:\w+\s+){1,3}(?:\(\s*)?\d{1,3}\s*%(?:\s*\))?',
        
        # Table structures
        r'\|[^|]*\d{1,3}\s*%[^|]*\|',
        r'\+[-+]*\+\n\|[^|]*\|[^|]*\|',
        
        # Lists with percentages
        r'(?:^|\n)(?:•|\*|-|\d+\.)\s+[^%\n]{3,40}%',
        
        # Assessment sections
        r'(?:assessment|evaluation|grading)\s+(?:components?|scheme|breakdown)[^\n]{0,50}\n(?:[^\n]*\n){1,10}[^\n]*\d{1,3}\s*%',
        
        # Components with explicit weights
        r'(?:weight|worth):\s*\d{1,3}\s*%',
    ]
    
    # Check for grade table patterns
    for pattern in grade_patterns:
        matches = re.finditer(pattern, document_lower, re.MULTILINE)
        for match in matches:
            # Extract surrounding paragraph to get context
            start = max(0, match.start() - 200)
            end = min(len(document_lower), match.end() + 400)
            
            section = document_lower[start:end]
            
            # If we have a good match with multiple percentages, return it
            if section.count('%') >= 2:
                # Get original case text from document
                original_section = document_text[start:end]
                
                # Clean the section a bit (remove excess newlines, etc.)
                cleaned = re.sub(r'\n{3,}', '\n\n', original_section)
                
                return True, cleaned
    
    # Look for specific sections in the document
    sections = extract_document_sections(document_text)
    for title in section_titles:
        for section_title, content in sections.items():
            if title in section_title and '%' in content:
                # Find actual content in original case
                start = document_lower.find(content)
                if start >= 0:
                    original_content = document_text[start:start+len(content)]
                    return True, original_content
    
    return False, ""

def process_documents(checklist_path: str, outline_path: str, api_attempts: int = 3, additional_context: str = "") -> Tuple[List[str], Dict[str, Any]]:
    """
    Enhanced document processing with context awareness and improved pattern recognition.
    Handles various document formats and considers user-provided context for analysis.
    """
    try:
        # Validate file paths
        if not os.path.exists(checklist_path):
            raise FileNotFoundError(f"Checklist file not found: {checklist_path}")
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"Course outline file not found: {outline_path}")

        # Extract and validate text from both documents
        checklist_text = extract_text(checklist_path)
        if not checklist_text.strip():
            raise ValueError("Checklist file is empty")

        outline_text = extract_text(outline_path)
        if not outline_text.strip():
            raise ValueError("Course outline file is empty")

        # Parse checklist items, focusing on numbered/bulleted items
        checklist_items = extract_checklist_items(checklist_text)
        if not checklist_items:
            raise ValueError("No checklist items found in the document")

        # Preprocess document for better pattern matching
        outline_tokens = nltk.word_tokenize(outline_text.lower())
        outline_stopwords = [word for word in outline_tokens if word.lower() not in stopwords.words('english')]
        
        # Pre-identify grade distribution table for enhanced matching
        has_grade_table, grade_table_text = identify_grade_distribution_table(outline_text)
        
        # Add insights about grade table to additional context if found
        enhanced_context = additional_context
        if has_grade_table and additional_context:
            if not any(term in additional_context.lower() for term in ['grade distribution', 'grade table']):
                enhanced_context += "\n\nNote: The document contains a grade distribution table or assessment weighting information."
        
        # Enhanced context for late/missed policies
        if re.search(r'(late|missed)\s+(polic|assessment)', checklist_text, re.IGNORECASE):
            policies = []
            for policy_type in ['late', 'missed']:
                pattern = rf"({policy_type})\s+(submission|assessment|assignment|work)s?\s+(polic|procedure)"
                if re.search(pattern, outline_text, re.IGNORECASE):
                    policies.append(f"{policy_type.title()} policy")
            
            if policies and enhanced_context:
                enhanced_context += f"\n\nNote: The document appears to contain policies for: {', '.join(policies)}."

        # Process using AI if permitted, otherwise use traditional matching
        from openai_helper import analyze_checklist_items_batch
        results = analyze_checklist_items_batch(checklist_items, outline_text, max_attempts=api_attempts)
        
        # Post-process grade distribution items with the extracted table if found
        if has_grade_table:
            for item in checklist_items:
                item_lower = item.lower()
                if ('grade' in item_lower and 'distribution' in item_lower) or 'weight' in item_lower:
                    # Check if the item was marked as not present or has low confidence
                    if item in results and (
                        not results[item].get('present', False) or
                        results[item].get('confidence', 0) < 0.6
                    ):
                        # Re-check with specialized extraction
                        results[item] = {
                            'present': True,
                            'confidence': 0.9,
                            'explanation': 'A grade distribution table with component weights was found in the document.',
                            'evidence': f"<span style='background-color: #c2f0c2;'><strong>Grade Distribution Table:</strong></span><br>{grade_table_text}",
                            'method': 'grade_table_extraction'
                        }

        # Return checklist items and analysis results
        return checklist_items, results

    except Exception as e:
        logging.exception(f"Error processing documents: {str(e)}")
        return [], {"error": str(e)}