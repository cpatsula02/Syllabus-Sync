import re
import logging
from typing import Tuple, List, Dict, Any
import os

# For PDF processing
try:
    import pdfplumber
except ImportError:
    logging.warning("pdfplumber not installed. PDF processing may not work.")

# For DOCX processing
try:
    import docx
except ImportError:
    logging.warning("python-docx not installed. DOCX processing may not work.")

# For NLP processing
try:
    import nltk
    from nltk.tokenize import sent_tokenize
    from nltk.corpus import stopwords
    # Download required NLTK data
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except ImportError:
    logging.warning("NLTK not installed. Advanced text processing may not work.")

# Import OpenAI helper
try:
    import openai_helper
except ImportError:
    logging.warning("OpenAI helper module not found. AI-powered analysis will not be available.")

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        raise
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a DOCX file."""
    text = ""
    try:
        doc = docx.Document(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {str(e)}")
        raise
    return text

def extract_text(file_path: str) -> str:
    """Extract text from a document based on its file extension."""
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension == '.docx':
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

def extract_checklist_items(text: str) -> List[str]:
    """
    Extract checklist items from the checklist document.
    Only extract numbered or bulleted items, excluding any other text.
    """
    # Split text into lines and clean them
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Look for patterns like numbering, bullet points, or similar indicators
    checklist_items = []

    # Common bullet point and numbering patterns - these are the ONLY patterns we'll accept
    bullet_pattern = r'^[\s]*[-•★*]+\s*(.*)'
    number_pattern = r'^[\s]*[0-9]+[.)]\s*(.*)'

    for line in lines:
        # Check if line matches bullet pattern
        bullet_match = re.match(bullet_pattern, line)
        if bullet_match:
            item = bullet_match.group(1).strip()
            if item and len(item) > 3:  # Avoid very short items
                checklist_items.append(item)
            continue

        # Check if line matches numbering pattern
        number_match = re.match(number_pattern, line)
        if number_match:
            item = number_match.group(1).strip()
            if item and len(item) > 3:
                checklist_items.append(item)
            continue

        # If the line doesn't match any of the patterns, skip it
        # We're only interested in explicitly numbered or bulleted items

    # Log how many items were found
    logging.info(f"Found {len(checklist_items)} numbered or bulleted checklist items")

    return checklist_items

def check_item_in_document(item: str, document_text: str) -> bool:
    """
    Check if a checklist item is present in the document text.
    Uses advanced semantic matching to identify related content even when wording differs.
    """
    # Clean and normalize text for comparison
    item_lower = item.lower()
    document_lower = document_text.lower()

    # Special handling for policy items
    if 'policy' in item_lower:
        # Require explicit policy mentions for policy-related items
        policy_words = item_lower.split()
        if 'policy' in policy_words:
            policy_type = ' '.join(policy_words[:policy_words.index('policy')])
            if not any(f"{policy_type} policy" in section.lower() for section in document_lower.split('\n\n')):
                return False

    # Direct match - if the exact phrase appears
    if item_lower in document_lower:
        return True

    # Extract core concepts from the checklist item
    item_concepts = extract_core_concepts(item_lower)

    # 1. Section Header Analysis - Identify document sections and their content
    document_sections = extract_document_sections(document_lower)

    # 2. Check if any of the extracted sections match our item concepts
    for section_title, section_content in document_sections.items():
        # Check if this section's title relates to our item
        if sections_are_related(section_title, item_concepts):
            return True

        # Check if this section's content contains our item concepts
        # Use a proximity search within the section content only
        if content_contains_concepts(section_content, item_concepts):
            return True

    # 3. Check for special entity patterns that might be missed by other methods
    if check_special_entity_patterns(item, document_text):
        return True

    # 4. Fallback: Check for keyword density
    try:
        stop_words = set(stopwords.words('english'))
        item_words = [word for word in re.findall(r'\b\w+\b', item_lower) 
                     if word not in stop_words and len(word) > 2]

        # Count how many important words appear in the document
        words_found = sum(1 for word in item_words if word in document_lower)

        # Increase threshold to 85% for more accurate matches
        if len(item_words) > 0 and words_found / len(item_words) >= 0.85:
            return True
    except:
        # Fall back to simple matching if NLP processing fails
        pass

    return False

def extract_core_concepts(text):
    """Extract core concepts from text for semantic matching."""
    # Define concept categories and their related terms
    concept_categories = {
        'textbook': ['textbook', 'book', 'reading', 'literature', 'material', 'resource'],
        'grade_distribution': ['grade', 'grading', 'mark', 'assessment', 'evaluation', 'distribution', 'weight', 'percentage', 'score'],
        'assignment': ['assignment', 'homework', 'task', 'project', 'paper', 'report', 'submission'],
        'participation': ['participation', 'engage', 'discussion', 'contribute', 'attend', 'attendance'],
        'exam': ['exam', 'examination', 'test', 'quiz', 'final', 'midterm'],
        'policy': ['policy', 'rule', 'guideline', 'requirement', 'procedure', 'protocol', 'regulation'],
        'schedule': ['schedule', 'timetable', 'calendar', 'date', 'deadline', 'timeline', 'due'],
        'objective': ['objective', 'goal', 'outcome', 'aim', 'purpose', 'learning'],
        'instructor': ['instructor', 'professor', 'teacher', 'faculty', 'contact', 'email', 'office']
    }

    # Extract concepts that appear in the text
    found_concepts = {}
    for concept, terms in concept_categories.items():
        for term in terms:
            if term in text:
                if concept not in found_concepts:
                    found_concepts[concept] = []
                found_concepts[concept].append(term)

    return found_concepts

def extract_document_sections(document_text):
    """Extract sections with their titles and content from the document."""
    sections = {}

    # Common section header patterns in course outlines
    header_patterns = [
        # Format: Header followed by a newline
        r'(^|\n)([A-Z][A-Za-z\s\d:&\-\']+)(\n)',
        # Format: Header with colon
        r'(^|\n)([A-Z][A-Za-z\s\d:&\-\']+):',
        # Format: Numbered/bulleted headers
        r'(^|\n)(\d+\.\s+[A-Z][A-Za-z\s\d:&\-\']+)(\n|:)',
        # Format: Headers with formatting marks around them
        r'(^|\n)([\*\-\_\=]{0,3}[A-Z][A-Za-z\s\d:&\-\']+[\*\-\_\=]{0,3})(\n|:)'
    ]

    # Find all potential section headers
    all_headers = []
    for pattern in header_patterns:
        headers = re.finditer(pattern, document_text, re.MULTILINE)
        for match in headers:
            header_text = match.group(2).strip()
            # Filter out very short headers or non-header-like text
            if len(header_text) > 3 and len(header_text.split()) <= 6:
                header_pos = match.start(2)
                all_headers.append((header_pos, header_text))

    # Sort headers by position
    all_headers.sort(key=lambda x: x[0])

    # Extract content between headers
    for i in range(len(all_headers)):
        current_header = all_headers[i][1]
        current_pos = all_headers[i][0]

        # Get content until the next header or end of document
        end_pos = len(document_text)
        if i < len(all_headers) - 1:
            end_pos = all_headers[i+1][0]

        # Extract section content
        start_content_pos = current_pos + len(current_header)
        section_content = document_text[start_content_pos:end_pos].strip()

        # Store the section
        sections[current_header.lower()] = section_content.lower()

    return sections

def sections_are_related(section_title, item_concepts):
    """Check if a section title is related to the concepts in the checklist item."""
    # Look for direct concept matches in the section title
    for concept, terms in item_concepts.items():
        for term in terms:
            if term in section_title:
                return True

    # Check for common concept pairs that might be related
    concept_relations = {
        'textbook': ['material', 'required', 'reading'],
        'grade_distribution': ['breakdown', 'composition', 'scale', 'grading'],
        'participation': ['attendance', 'classroom', 'engagement'],
        'assignment': ['task', 'project', 'work', 'submission', 'paper'],
        'policy': ['late', 'missed', 'absence', 'attendance', 'requirement']
    }

    # Check if any concept from the item appears in related concept terms in the section title
    for item_concept in item_concepts.keys():
        if item_concept in concept_relations:
            related_terms = concept_relations[item_concept]
            for term in related_terms:
                if term in section_title:
                    return True

    return False

def content_contains_concepts(section_content, item_concepts):
    """Check if section content contains the concepts from the checklist item."""
    # Special handling for course workload
    if any('workload' in term for terms in item_concepts.values() for term in terms):
        workload_patterns = [
            r'course\s+workload',
            r'expected\s+(time|hours)',
            r'(time|hours)\s+(required|expected|needed)',
            r'workload\s+expectations?',
            r'(weekly|total)\s+(time|hours|workload)',
            r'hours\s+per\s+week'
        ]
        for pattern in workload_patterns:
            if re.search(pattern, section_content, re.IGNORECASE):
                return True

    # Standard concept matching for other items
    all_concept_terms = []
    for terms in item_concepts.values():
        all_concept_terms.extend(terms)

    terms_found = sum(1 for term in all_concept_terms if term in section_content)
    return len(all_concept_terms) > 0 and terms_found / len(all_concept_terms) >= 0.6

def extract_policy_type(item_text):
    """Extract the type of policy from policy-related checklist items."""
    if 'policy' not in item_text:
        return None

    words = item_text.split()
    if 'policy' in words:
        policy_index = words.index('policy')
        # Get words before 'policy' (limit to 3 words for better precision)
        policy_terms = words[max(0, policy_index-3):policy_index]
        return ' '.join(policy_terms) if policy_terms else None
    return None

def find_original_text(lowercase_text, original_document):
    """
    Find the original text (with correct case) from the lowercase version.
    This helps preserve the original formatting when displaying matches.
    """
    # Try to find the exact match first
    escaped_text = re.escape(lowercase_text)
    match = re.search(escaped_text, original_document.lower())
    if match:
        start, end = match.span()
        return original_document[start:end]
    
    # If exact match fails, return the lowercase as is
    return lowercase_text

def find_best_keyword_section(document_text, keywords):
    """
    Find the section of the document that contains the most keywords.
    Returns a relevant excerpt from the document.
    """
    document_lower = document_text.lower()
    
    # Split the document into paragraphs for analysis
    paragraphs = document_lower.split('\n\n')
    
    # Score each paragraph by the number of keywords it contains
    best_score = 0
    best_paragraph = ""
    
    for paragraph in paragraphs:
        if len(paragraph) < 10:  # Skip very short paragraphs
            continue
            
        score = sum(1 for keyword in keywords if keyword in paragraph)
        
        if score > best_score:
            best_score = score
            best_paragraph = paragraph
    
    # If we found a good paragraph, return the corresponding original text
    if best_score >= 2:  # Require at least 2 keywords for a good match
        # Find original paragraph text
        start_pos = document_lower.find(best_paragraph)
        if start_pos >= 0:
            # Get excerpt (truncate if too long)
            excerpt = document_text[start_pos:start_pos + min(300, len(best_paragraph))]
            return excerpt + ("..." if len(best_paragraph) > 300 else "")
    
    return None

def check_special_entity_patterns(item, document):
    """Check for special entity patterns that might be missed by other methods."""
    document_lower = document.lower()
    item_lower = item.lower()
    
    # 1. Handle exam date patterns
    if any(word in item_lower for word in ['exam', 'examination', 'test', 'quiz', 'final']):
        exam_patterns = [
            r'(exam|examination|test|quiz|final)s?\s+.*?\b(date|scheduled|held)s?\b',
            r'(exam|examination|test|quiz|final)s?\s+.*?\b(on|at)\b\s+.*?\b\d+',
            r'(date|day|time)\s+of\s+.*?\b(exam|examination|test|quiz|final)s?\b'
        ]
        
        for pattern in exam_patterns:
            if re.search(pattern, document_lower):
                return True
    
    # 2. Handle textbook and reading list patterns
    if any(word in item_lower for word in ['textbook', 'reading', 'book', 'material']):
        textbook_patterns = [
            r'required\s+.*?\b(textbook|reading|book|material)s?\b',
            r'(textbook|reading|book|material)s?\s+required',
            r'(textbook|reading|book|material)s?\s+list',
            r'list\s+of\s+.*?\b(textbook|reading|book|material)s?\b'
        ]
        
        for pattern in textbook_patterns:
            if re.search(pattern, document_lower):
                return True
    
    # 3. Handle assignment and submission patterns
    if any(word in item_lower for word in ['assignment', 'submission', 'deadline', 'due']):
        assignment_patterns = [
            r'(assignment|paper|project|report)s?\s+.*?\b(due|deadline|submit|date)s?\b',
            r'(due|deadline|submit|date)s?\s+.*?\b(assignment|paper|project|report)s?\b',
            r'submission\s+.*?\b(policy|procedure|guideline|format)s?\b'
        ]
        
        for pattern in assignment_patterns:
            if re.search(pattern, document_lower):
                return True
    
    # 4. Handle grade distribution and weight patterns
    if any(word in item_lower for word in ['grade', 'weight', 'distribution', 'percentage']):
        grade_patterns = [
            r'(grade|weight|mark)s?\s+.*?\b(distribution|breakdown|allocation)s?\b',
            r'(distribution|breakdown|allocation)s?\s+of\s+.*?\b(grade|weight|mark)s?\b',
            r'(assignment|project|paper|exam|quiz|test)s?\s+.*?\b\d+%',
            r'\b\d+%\s+.*?\b(assignment|project|paper|exam|quiz|test)s?\b'
        ]
        
        for pattern in grade_patterns:
            if re.search(pattern, document_lower):
                return True
    
    # 5. Handle instructor email patterns specifically for @ucalgary.ca domain
    if any(word in item_lower for word in ['instructor', 'email', 'contact', 'professor']):
        # Look for a paragraph or section with instructor-related terms first
        instructor_sections = []
        
        # Define instructor-related section patterns
        instructor_section_patterns = [
            r'(instructor|professor|faculty|teacher|contact|course coordinator)\s*information',
            r'contacting\s+(your|the)\s+(instructor|professor|faculty|teacher)',
            r'(instructor|professor|faculty|teacher|contact)\s*:'
        ]
        
        # Find potential instructor sections
        paragraphs = document.split('\n\n')
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            if any(re.search(pattern, paragraph_lower) for pattern in instructor_section_patterns):
                instructor_sections.append(paragraph)
        
        # If we found instructor sections, look for valid ucalgary email in them first
        if instructor_sections:
            for section in instructor_sections:
                # Look for emails ending with @ucalgary.ca
                ucalgary_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b', section)
                if ucalgary_emails:
                    return True
        
        # If no instructor sections with ucalgary emails were found, apply more strict rules for general document search
        
        # Look for context around email patterns
        email_contexts = []
        
        # Search for potential instructor email context
        instructor_email_patterns = [
            r'(instructor|professor|faculty|teacher|contact)\s*:?\s*[^@\n]{0,40}?[A-Za-z0-9._%+-]+@ucalgary\.ca',
            r'(instructor|professor|faculty|teacher|contact)[\s\S]{0,100}?[A-Za-z0-9._%+-]+@ucalgary\.ca',
            r'email\s*:?\s*[A-Za-z0-9._%+-]+@ucalgary\.ca',
            r'[A-Za-z0-9._%+-]+@ucalgary\.ca\s*\(\s*(instructor|professor|faculty|teacher|contact)\s*\)'
        ]
        
        for pattern in instructor_email_patterns:
            if re.search(pattern, document_lower):
                return True
        
        # If we specifically need an instructor's email ending with @ucalgary.ca
        # Do not match if only a general email is found without instructor context
        general_ucalgary_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b', document)
        
        # Only return true if both an email with @ucalgary.ca AND instructor context exists
        # This prevents matching random emails or example emails
        return False
    
    return False

def process_documents(checklist_path: str, outline_path: str, api_attempts: int = 3, additional_context: str = "") -> Tuple[List[str], Dict[str, Any]]:
    """
    Process both documents and return checklist items and matching results with detailed breakdown.

    Args:
        checklist_path: Path to the checklist document
        outline_path: Path to the course outline document
        api_attempts: Number of API analysis attempts to make (1-10)
        additional_context: Additional context about the course or specific situations

    Returns:
        A tuple of (checklist_items, matching_results)
    """
    try:
        # Extract text from both documents
        checklist_text = extract_text(checklist_path)
        outline_text = extract_text(outline_path)
        
        # Add additional context to the outline if provided
        if additional_context:
            outline_text += f"\n\nADDITIONAL CONTEXT:\n{additional_context}"
            
        # Extract checklist items from the checklist document
        checklist_items = extract_checklist_items(checklist_text)
        logging.info(f"Extracted {len(checklist_items)} checklist items")
        
        # If we couldn't extract any items, return error
        if not checklist_items:
            return [], {"error": "No checklist items could be extracted. Please check the format of your checklist."}
        
        # If OpenAI helper is available, use it for advanced analysis
        try:
            from openai_helper import analyze_checklist_items_batch
            
            # Start with OpenAI processing for all items
            logging.info("Starting item analysis with OpenAI")
            matching_results = analyze_checklist_items_batch(checklist_items, outline_text, max_attempts=api_attempts)
            api_result_count = sum(1 for result in matching_results.values() 
                                  if isinstance(result, dict) and result.get('method', '').startswith('openai'))
            
            # Log how many items were processed with the API
            logging.info(f"Analysis complete: {api_result_count} items processed with OpenAI, {len(checklist_items) - api_result_count} with traditional methods")
            
            # For any items that weren't analyzed (if the OpenAI API was unavailable), analyze them with traditional methods
            for item in checklist_items:
                if item not in matching_results:
                    matches = check_item_in_document(item, outline_text)
                    matching_results[item] = {
                        "present": matches,
                        "confidence": 0.8 if matches else 0.2,
                        "explanation": "Found match in document" if matches else "Not found in document",
                        "method": "traditional"
                    }
            
        except ImportError:
            # Fallback to traditional methods if OpenAI helper is unavailable
            logging.warning("OpenAI helper not available. Using traditional methods only.")
            matching_results = {}
            
            # Process each checklist item using traditional methods
            for item in checklist_items:
                matches = check_item_in_document(item, outline_text)
                matching_results[item] = {
                    "present": matches, 
                    "confidence": 0.8 if matches else 0.2,
                    "explanation": "Found match in document" if matches else "Not found in document",
                    "method": "traditional"
                }
                
        except Exception as e:
            # Handle any other errors
            logging.error(f"Error processing documents with OpenAI: {str(e)}")
            # Fall back to traditional methods
            matching_results = {}
            
            # Process each checklist item using traditional methods
            for item in checklist_items:
                matches = check_item_in_document(item, outline_text)
                matching_results[item] = {
                    "present": matches, 
                    "confidence": 0.7 if matches else 0.3,
                    "explanation": "Found match in document" if matches else "Not found in document",
                    "method": "traditional (after API error)"
                }
        
        return checklist_items, matching_results
        
    except Exception as e:
        # Handle any errors during processing
        logging.error(f"Error processing documents: {str(e)}")
        return [], {"error": f"An error occurred: {str(e)}"}

def find_matching_excerpt(item, document_text):
    """
    Find a relevant excerpt in the document that matches the given checklist item.
    Returns a highlighted excerpt showing where the item was found.
    
    Args:
        item: The checklist item to find in the document
        document_text: The full text of the document to search
        
    Returns:
        A tuple of (found, excerpt) where:
        - found: Boolean indicating if a match was found
        - excerpt: String containing the excerpt with matching keywords highlighted,
                  or None if no match was found
    """
    # Extract key terms from the checklist item
    item_lower = item.lower()
    key_terms = []
    
    # Extract nouns and key phrases from the item
    words = re.findall(r'\b\w+\b', item_lower)
    for word in words:
        if len(word) > 3 and word not in ['and', 'the', 'that', 'this', 'with', 'from', 'have', 'for', 'are', 'should', 'would', 'could']:
            key_terms.append(word)
    
    # Add key phrases based on the checklist item content
    if 'grade' in item_lower:
        key_terms.extend(['grade', 'grading', 'marks', 'evaluation'])
    if 'exam' in item_lower:
        key_terms.extend(['exam', 'examination', 'test', 'final'])
    if 'syllabus' in item_lower or 'course outline' in item_lower:
        key_terms.extend(['syllabus', 'outline', 'course'])
    if 'textbook' in item_lower:
        key_terms.extend(['textbook', 'book', 'reading', 'material'])
    if 'assignment' in item_lower:
        key_terms.extend(['assignment', 'project', 'homework', 'submission'])
    if 'instructor' in item_lower:
        key_terms.extend(['instructor', 'professor', 'faculty', 'teacher', 'contact'])
    
    # Remove duplicates and sort by length (longer terms first)
    key_terms = list(set(key_terms))
    key_terms.sort(key=len, reverse=True)
    
    # Split document into paragraphs and find the best match
    paragraphs = document_text.split('\n\n')
    best_score = 0
    best_paragraph = ""
    best_matches = []
    
    for paragraph in paragraphs:
        if len(paragraph.strip()) < 10:  # Skip very short paragraphs
            continue
            
        paragraph_lower = paragraph.lower()
        score = 0
        matches = []
        
        for term in key_terms:
            if term in paragraph_lower:
                score += 1
                matches.append(term)
                
        if score > best_score:
            best_score = score
            best_paragraph = paragraph
            best_matches = matches
    
    # If we found a good match
    if best_score >= 2:  # Require at least 2 keyword matches for relevance
        # Prepare the excerpt, highlighting the matching terms
        excerpt = best_paragraph
        
        # If the paragraph is too long, get a relevant section around the matched terms
        if len(excerpt) > 300:
            # Find the position of the first matched term
            first_match_pos = min([excerpt.lower().find(term) for term in best_matches if excerpt.lower().find(term) != -1], default=0)
            
            # Extract a portion around the first match
            start_pos = max(0, first_match_pos - 100)
            end_pos = min(len(excerpt), first_match_pos + 200)
            
            # Adjust to not cut off in the middle of words
            while start_pos > 0 and excerpt[start_pos].isalnum():
                start_pos -= 1
            while end_pos < len(excerpt) and excerpt[end_pos].isalnum():
                end_pos += 1
                
            excerpt = ("..." if start_pos > 0 else "") + excerpt[start_pos:end_pos] + ("..." if end_pos < len(excerpt) else "")
        
        return True, excerpt
    
    return False, None
