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
    
    Enhanced to handle specific problem areas that were causing false positives/negatives:
    - Course objectives listed & numbered
    - Tools and platforms resources
    - Course workload section
    - Missed assessment policy header
    - Late policy header
    - Contacting instructor section
    - Link validation
    """
    # Clean and normalize text for comparison
    item_lower = item.lower()
    document_lower = document_text.lower()
    
    # 1. IDENTIFY SPECIAL CASES that need specialized handling
    # These are known problem areas where we need custom detection logic
    
    # Course objectives listed/numbered
    is_course_objectives = any(keyword in item_lower for keyword in ['objective', 'goals', 'outcomes']) and any(keyword in item_lower for keyword in ['listed', 'numbered', 'course'])
    
    # Tools and platforms resources
    is_tools_platforms = any(keyword in item_lower for keyword in ['tools', 'platforms', 'resources', 'software']) and any(keyword in item_lower for keyword in ['student', 'available', 'use', 'access'])
    
    # Course workload section
    is_workload = 'workload' in item_lower and 'course' in item_lower
    
    # Missed assessment policy
    is_missed_assessment = any(keyword in item_lower for keyword in ['missed', 'missing']) and any(keyword in item_lower for keyword in ['assessment', 'exam', 'test', 'assignment', 'policy'])
    
    # Late policy
    is_late_policy = any(keyword in item_lower for keyword in ['late', 'policy', 'deadline'])
    
    # Contacting instructor section
    is_contacting_instructor = any(keyword in item_lower for keyword in ['contacting', 'contact']) and any(keyword in item_lower for keyword in ['instructor', 'professor', 'faculty', 'teacher'])
    
    # Link validation
    is_link_validation = any(keyword in item_lower for keyword in ['link', 'url', 'website', 'http', 'www'])
    
    # 2. SPECIALIZED HANDLING FOR EACH CASE
    
    # Course objectives - need to find numbered or bulleted list
    if is_course_objectives:
        # Look for section heading related to objectives
        objective_section_patterns = [
            r'(?:course|learning)\s+(?:objective|outcome|goal)s?',
            r'objective|goal|outcome\s*:',
            r'by\s+the\s+end\s+of\s+this\s+course',
            r'student\s+will\s+be\s+able\s+to'
        ]
        
        # Find potential objective sections
        sections = document_text.split('\n\n')
        objective_section = ""
        
        # First identify the objective section
        for i, section in enumerate(sections):
            section_lower = section.lower()
            if any(re.search(pattern, section_lower) for pattern in objective_section_patterns):
                # Found an objective section, now look for the content (which might be in the next paragraph)
                objective_section = section
                # Check the next 2-3 paragraphs for the actual list
                for j in range(1, 4):
                    if i + j < len(sections):
                        objective_section += "\n\n" + sections[i+j]
        
        # Now check if the objectives are actually listed/numbered
        if objective_section:
            # Check for numbered/bulleted list patterns
            list_patterns = [
                r'^\s*\d+\.\s+', # Numbered: "1. Something"
                r'^\s*[•\-\*\✓\✔\→\⇨\⇒\⇰\◆\◇\○\●\★\☆]\s+', # Bulleted
                r'(?:\n|\r|^)\s*\d+\.\s+', # Numbered with line break
                r'(?:\n|\r|^)\s*[•\-\*\✓\✔\→\⇨\⇒\⇰\◆\◇\○\●\★\☆]\s+', # Bulleted with line break
                r'(?:\n|\r|^)\s*[a-zA-Z]\)\s+', # Format: "a) Something"
                r'(?:\n|\r|^)\s*[a-zA-Z]\.\s+', # Format: "a. Something"
                r'(?:\n|\r|^)\s*[ivxIVX]+\.\s+', # Roman numerals: "i. Something"
            ]
            
            # If we find any list pattern in the objective section, consider it a match
            if any(re.search(pattern, objective_section, re.MULTILINE) for pattern in list_patterns):
                return True
                
            # Also check for phrases that imply a list of objectives
            list_phrases = [
                r'students\s+will\s+(?:be\s+able\s+to|learn\s+to|learn\s+how\s+to)',
                r'(?:learn|achieve|demonstrate|develop|display|acquire|master)\s+the\s+(?:following|ability)',
                r'course\s+is\s+designed\s+to'
            ]
            
            if any(re.search(pattern, objective_section.lower()) for pattern in list_phrases):
                # Look for multiple verbs commonly used in learning objectives
                objective_verbs = [
                    r'identify', r'explain', r'describe', r'analyze', r'evaluate', 
                    r'apply', r'demonstrate', r'understand', r'create', r'develop',
                    r'design', r'implement', r'synthesize', r'compare', r'contrast'
                ]
                
                # If we find at least 3 different objective verbs, it's likely a list of objectives
                verb_count = sum(1 for verb in objective_verbs if re.search(r'\b' + verb + r'\b', objective_section.lower()))
                if verb_count >= 3:
                    return True
                    
        # If we reach here, objectives section might exist but not as a proper list
        return False
    
    # Tools and platforms resources
    if is_tools_platforms:
        # Look for specific tool mentions
        tool_patterns = [
            r'(?:using|use|access|available\s+(?:on|through|at|via))\s+(?:d2l|desire2learn|canvas|blackboard|moodle)',
            r'(?:software|tool|application|platform|resource)s?\s+(?:include|used|required|needed)',
            r'(?:computer|software|tool|application|platform)\s+requirement',
            r'(?:zoom|teams|google\s+meet|webex)',
            r'(?:matlab|python|r|spss|sas|excel|powerpoint|tableau|github)',
            r'(?:technology|equipment)\s+required'
        ]
        
        for pattern in tool_patterns:
            if re.search(pattern, document_lower):
                return True
                
        # Look for a resource section with specific tools
        resource_section_headers = [
            r'(?:course|required)\s+(?:materials|resources|tools|technologies|software)',
            r'technical\s+requirements',
            r'(?:software|platform|technology)\s+requirements'
        ]
        
        # Common technology terms that would indicate tools
        tech_terms = [
            r'browser', r'internet', r'software', r'hardware', r'computer', 
            r'laptop', r'webcam', r'microphone', r'headphones', r'application',
            r'platform', r'account', r'download', r'install'
        ]
        
        # Check if any section header about resources exists and contains tech terms
        sections = document_text.split('\n\n')
        for i, section in enumerate(sections):
            section_lower = section.lower()
            
            if any(re.search(pattern, section_lower) for pattern in resource_section_headers):
                # Look at this section and the next 2 paragraphs for tech terms
                content = section
                for j in range(1, 3):
                    if i + j < len(sections):
                        content += "\n\n" + sections[i+j]
                
                content_lower = content.lower()
                term_count = sum(1 for term in tech_terms if re.search(r'\b' + term + r'\b', content_lower))
                
                # If we find at least 2 tech terms, it's likely a tools section
                if term_count >= 2:
                    return True
        
        return False
    
    # Course workload section
    if is_workload:
        # Look for explicit workload mentions with time estimates
        workload_patterns = [
            r'(?:course|weekly|estimated)\s+(?:workload|time\s+commitment)',
            r'(?:expect|required|approximately|average)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:hour|hr)s?',
            r'(?:hour|hr)s?\s+(?:per|each|a)\s+(?:week|day|class|lecture)',
            r'time\s+(?:commitment|investment|expectation)'
        ]
        
        for pattern in workload_patterns:
            if re.search(pattern, document_lower):
                return True
                
        # Look for specific time breakdowns
        time_patterns = [
            r'\d+\s*(?:hour|hr)',
            r'(?:lecture|lab|tutorial|class)\s*:\s*\d+\s*(?:hour|hr)',
            r'(?:in-class|outside\s+of\s+class)\s*:\s*\d+'
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, document_lower):
                return True
                
        return False
        
    # Missed assessment policy header
    if is_missed_assessment:
        # Look for explicit policy headers
        missed_policy_headers = [
            r'missed\s+(?:assessment|assignment|exam|test|quiz|work)',
            r'(?:policy|policies|procedure)\s+(?:on|for|regarding)\s+missed',
            r'(?:missing|absence|absent|unable\s+to\s+(?:complete|attend))',
            r'(?:deferral|extension|accommodation)\s+(?:policy|request|procedure)'
        ]
        
        # First check for headers/titles
        for pattern in missed_policy_headers:
            # Look for patterns that appear as headers (standalone or with : )
            header_match = re.search(r'(?:^|\n|\r)(?:[A-Z][A-Za-z\s]*)?(?:' + pattern + r')(?:\s*:|$|\n|\r)', document_text, re.MULTILINE)
            if header_match:
                return True
            
        # Also check for missed policy content even if not a proper header
        missed_policy_content = [
            r'if\s+(?:you|a\s+student)\s+(?:miss|are\s+absent|cannot\s+(?:attend|complete|write|submit))',
            r'(?:student|you)\s+who\s+(?:miss|are\s+absent|cannot\s+(?:attend|complete|write|submit))',
            r'missed\s+(?:assessments|assignments|exams|tests|quizzes)\s+(?:will|may|must|should|can)'
        ]
        
        for pattern in missed_policy_content:
            content_match = re.search(pattern, document_lower)
            if content_match:
                # Find the paragraph containing this policy
                paragraphs = document_text.split('\n\n')
                for paragraph in paragraphs:
                    if re.search(pattern, paragraph.lower()):
                        if len(paragraph.strip()) > 50:  # Ensure it's substantial content
                            return True
                
        return False
        
    # Late policy header
    if is_late_policy:
        # Look for explicit late policy headers
        late_policy_headers = [
            r'late\s+(?:policy|policies|submission|penalties|work)',
            r'(?:policy|policies|procedure)\s+(?:on|for|regarding)\s+late',
            r'(?:late|overdue)\s+(?:assignment|work|submission)',
            r'(?:penalty|penalties|deduction|reduction)\s+for\s+late'
        ]
        
        # First check for headers/titles
        for pattern in late_policy_headers:
            # Look for patterns that appear as headers (standalone or with : )
            header_match = re.search(r'(?:^|\n|\r)(?:[A-Z][A-Za-z\s]*)?(?:' + pattern + r')(?:\s*:|$|\n|\r)', document_text, re.MULTILINE)
            if header_match:
                return True
            
        # Also check for late policy content even if not a proper header
        late_policy_content = [
            r'(?:assignment|work|project)s?\s+(?:submitted|turned\s+in|received)\s+late',
            r'(?:\d+|\w+)\s*%\s+(?:penalty|deduction|reduction|off)\s+(?:per|for\s+each)\s+(?:day|hour|class)',
            r'late\s+(?:submission|assignment|work|project)s?\s+(?:will|may|must|shall|can|are|is)'
        ]
        
        for pattern in late_policy_content:
            content_match = re.search(pattern, document_lower)
            if content_match:
                # Find the paragraph containing this policy
                paragraphs = document_text.split('\n\n')
                for paragraph in paragraphs:
                    if re.search(pattern, paragraph.lower()):
                        if len(paragraph.strip()) > 50:  # Ensure it's substantial content
                            return True
                
        return False
    
    # Contacting instructor section
    if is_contacting_instructor:
        # Look for explicit contacting sections
        contact_section_headers = [
            r'(?:contacting|contact|email(?:ing)?)\s+(?:your|the)\s+(?:instructor|professor|faculty|teacher)',
            r'(?:instructor|professor|faculty|teacher)\s+(?:contact|communication)',
            r'communication\s+(?:with|policy)',
            r'(?:office\s+hours|email\s+policy)'
        ]
        
        # First check for headers/titles
        for pattern in contact_section_headers:
            # Look for patterns that appear as headers (standalone or with : )
            header_match = re.search(r'(?:^|\n|\r)(?:[A-Z][A-Za-z\s]*)?(?:' + pattern + r')(?:\s*:|$|\n|\r)', document_text, re.MULTILINE)
            if header_match:
                # Verify the section contains substantial contact information
                start_pos = header_match.start()
                section_text = document_text[start_pos:start_pos+500]  # Get 500 chars after the header
                
                # Check if the section mentions email or office hours
                if re.search(r'(?:email|@|office\s+hour|contact|available|respond|response)', section_text.lower()):
                    return True
            
        # Also check for contact info even if not a proper section
        contact_content = [
            r'(?:instructor|professor|faculty|teacher)\s+is\s+(?:available|reachable|contactable)',
            r'(?:question|concern|query)s?\s+(?:about|regarding)\s+(?:the\s+course|course\s+material)',
            r'(?:email|office\s+hour)s?\s+(?:are|is|will\s+be)\s+(?:the|a)\s+(?:preferred|primary|main)'
        ]
        
        for pattern in contact_content:
            content_match = re.search(pattern, document_lower)
            if content_match:
                # Find the paragraph containing this content
                paragraphs = document_text.split('\n\n')
                for paragraph in paragraphs:
                    if re.search(pattern, paragraph.lower()):
                        if len(paragraph.strip()) > 70:  # Ensure it's substantial content
                            return True
                
        return False
    
    # Link validation
    if is_link_validation:
        # Look for URLs in the document
        url_patterns = [
            r'https?://[a-zA-Z0-9\-.]+\.[a-zA-Z]{2,}(?:/[^\\s]*)?',
            r'www\.[a-zA-Z0-9\-.]+\.[a-zA-Z]{2,}(?:/[^\\s]*)?',
            r'(?:visit|go\s+to|available\s+at|access\s+at|access\s+through)\s+[a-zA-Z0-9\-.]+\.[a-zA-Z]{2,}',
            r'site\.ucalgary\.ca',
            r'd2l\.ucalgary\.ca'
        ]
        
        for pattern in url_patterns:
            urls = re.findall(pattern, document_text)
            if urls:
                return True
                
        return False
    
    # GENERAL CASE HANDLING (for items not matching special cases above)
    
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
    
    # Check for course objectives with numbering
    if any(word in item_lower for word in ['objective', 'learning outcome', 'goal']):
        objective_patterns = [
            r'(?:course\s+)?objectives?[:]\s*\n\s*(?:\d+\.|\-|\*)\s+\w+',
            r'learning\s+outcomes?[:]\s*\n\s*(?:\d+\.|\-|\*)\s+\w+',
            r'course\s+goals?[:]\s*\n\s*(?:\d+\.|\-|\*)\s+\w+'
        ]
        return any(re.search(pattern, document_lower, re.MULTILINE) for pattern in objective_patterns)
    
    # Check for tools/platforms/resources section
    if any(word in item_lower for word in ['tool', 'platform', 'resource', 'material']):
        resource_patterns = [
            r'(?:required|recommended)\s+(?:tools?|platforms?|resources?|materials?)',
            r'technology\s+requirements?',
            r'learning\s+(?:tools?|platforms?|resources?)',
            r'(?:course|required)\s+materials?\s+and\s+resources?'
        ]
        return any(re.search(pattern, document_lower) for pattern in resource_patterns)
    
    # Check for course workload section
    if any(word in item_lower for word in ['workload', 'time', 'hours']):
        workload_patterns = [
            r'course\s+workload',
            r'expected\s+(?:hours?|time)',
            r'weekly\s+(?:hours?|workload)',
            r'time\s+commitment',
            r'student\s+effort'
        ]
        return any(re.search(pattern, document_lower) for pattern in workload_patterns)
    
    # Check for missed assessment policy
    if 'missed' in item_lower and ('assessment' in item_lower or 'policy' in item_lower):
        missed_patterns = [
            r'missed\s+(?:assignments?|assessments?)',
            r'missing\s+(?:work|assignments?|assessments?)',
            r'absence\s+policy',
            r'missed\s+.*?\s+policy'
        ]
        return any(re.search(pattern, document_lower) for pattern in missed_patterns)
    
    # Check for late policy
    if 'late' in item_lower and 'policy' in item_lower:
        late_patterns = [
            r'late\s+(?:submission|work|assignment)s?\s+policy',
            r'late\s+policy',
            r'policies?\s+(?:on|regarding)\s+late'
        ]
        return any(re.search(pattern, document_lower) for pattern in late_patterns)
    
    # Check for contacting instructor section
    if any(word in item_lower for word in ['contact', 'instructor', 'professor']):
        contact_patterns = [
            r'(?:contacting|contact)\s+(?:your|the)\s+instructor',
            r'instructor\s+contact\s+information',
            r'(?:office|contact)\s+hours',
            r'how\s+to\s+contact'
        ]
        return any(re.search(pattern, document_lower) for pattern in contact_patterns)
    
    # Check for valid links
    if any(word in item_lower for word in ['link', 'url', 'hyperlink']):
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return bool(re.findall(url_pattern, document))
    
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
        # First look for any email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ucalgary_pattern = r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b'
        
        # Look specifically for @ucalgary.ca emails
        ucalgary_emails = re.findall(ucalgary_pattern, document)
        
        if ucalgary_emails:
            # Check if the email appears in an instructor context
            for email in ucalgary_emails:
                email_idx = document.find(email)
                if email_idx >= 0:
                    # Look for instructor context in surrounding text (100 chars before and after)
                    context_start = max(0, email_idx - 100)
                    context_end = min(len(document), email_idx + len(email) + 100)
                    context = document[context_start:context_end].lower()
                    
                    # Check for instructor-related terms in context
                    instructor_terms = ['instructor', 'professor', 'faculty', 'teacher', 'lecturer']
                    if any(term in context for term in instructor_terms):
                        return True
        
        # First, find instructor-related sections in the document
        instructor_sections = []
        
        # Define stronger instructor-related section patterns with clearer boundaries
        instructor_section_patterns = [
            # Patterns with clear section headers or formatting
            r'(instructor|professor|faculty|teacher|contact|course coordinator)\s*information',
            r'contacting\s+(your|the)\s+(instructor|professor|faculty|teacher)',
            r'(instructor|professor|faculty|teacher|contact)\s*:',
            # Common formats for contact information sections
            r'^\s*(instructor|professor|faculty|teacher|contact)\s*:.*?$',
            r'^\s*(name|instructor name)\s*:.*?$'
        ]
        
        # Find potential instructor sections with stricter context
        paragraphs = document.split('\n\n')
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            # Only consider paragraphs with instructor-related terms
            if any(instructor_term in paragraph_lower for instructor_term in 
                   ['instructor', 'professor', 'faculty', 'teacher', 'contact']):
                if any(re.search(pattern, paragraph_lower) for pattern in instructor_section_patterns):
                    instructor_sections.append(paragraph)
        
        # If no sections were found, try another approach with smaller chunks
        if not instructor_sections:
            lines = document.split('\n')
            current_section = []
            for line in lines:
                line_lower = line.lower()
                if any(instructor_term in line_lower for instructor_term in 
                       ['instructor', 'professor', 'faculty', 'contact']):
                    current_section.append(line)
                    # Add the next few lines for context
                    idx = lines.index(line)
                    if idx + 3 < len(lines):
                        current_section.extend(lines[idx+1:idx+4])
                    instructor_sections.append('\n'.join(current_section))
                    current_section = []
        
        # Now strictly validate for ucalgary.ca domain in these contexts
        ucalgary_email_found = False
        found_email = None
        valid_context = False
        
        # Check instructor sections first (most reliable)
        for section in instructor_sections:
            # Find all emails ending with @ucalgary.ca
            ucalgary_emails = re.findall(r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b', section)
            if ucalgary_emails:
                ucalgary_email_found = True
                found_email = ucalgary_emails[0]
                
                # Check if this section has instructor context within a close range
                section_lower = section.lower()
                if any(term in section_lower for term in 
                       ['instructor:', 'professor:', 'faculty:', 'contact:', 'instructor email',
                        'professor email', 'email:', 'instructor name']):
                    valid_context = True
                    break
                    
                # Also check for instructor-email proximity pattern
                if re.search(r'(instructor|professor|faculty).{0,30}(email|contact)', section_lower):
                    valid_context = True
                    break
        
        # If we have a ucalgary email but no valid context, look more carefully for context
        if ucalgary_email_found and not valid_context:
            for email in re.findall(r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b', document):
                # Look for instructor context within 100 characters before/after the email
                email_idx = document.find(email)
                if email_idx > 0:
                    surrounding_text = document[max(0, email_idx-100):min(len(document), email_idx+100)]
                    surrounding_lower = surrounding_text.lower()
                    if any(term in surrounding_lower for term in 
                          ['instructor', 'professor', 'faculty', 'contact', 'teacher']):
                        valid_context = True
                        break
        
        # Only return true if we found both a valid ucalgary.ca email AND proper instructor context
        return ucalgary_email_found and valid_context
        
        # IMPORTANT: With this implementation, the function will return False if:
        # 1. No @ucalgary.ca email is found at all
        # 2. An @ucalgary.ca email is found, but not in proper instructor context
        # This should significantly reduce false positives
    
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
    
    # Handle email requirements specially 
    is_email_requirement = any(keyword in item_lower for keyword in ['email', 'contact', 'instructor']) and '@' in item_lower
    
    # Extract more meaningful key terms from the item
    # Use word boundaries to find complete words
    words = re.findall(r'\b\w+\b', item_lower)
    for word in words:
        # More aggressive filtering of common words
        if len(word) > 3 and word not in ['and', 'the', 'that', 'this', 'with', 'from', 'have', 
                                          'for', 'are', 'should', 'would', 'could', 'will', 
                                          'been', 'must', 'they', 'their', 'there', 'than', 
                                          'when', 'what', 'where', 'which', 'who', 'whom', 'whose']:
            key_terms.append(word)
    
    # Add context-specific key terms based on the checklist item type
    if 'grade' in item_lower or 'grading' in item_lower:
        key_terms.extend(['grade', 'grading', 'marks', 'evaluation', 'assessment', 'percentage', 'score', 'distribution'])
    if 'exam' in item_lower or 'test' in item_lower:
        key_terms.extend(['exam', 'examination', 'test', 'final', 'midterm', 'quiz'])
    if 'syllabus' in item_lower or 'course outline' in item_lower:
        key_terms.extend(['syllabus', 'outline', 'course', 'description', 'information'])
    if 'textbook' in item_lower or 'reading' in item_lower:
        key_terms.extend(['textbook', 'book', 'reading', 'material', 'literature', 'resource', 'required'])
    if 'assignment' in item_lower or 'homework' in item_lower:
        key_terms.extend(['assignment', 'project', 'homework', 'submission', 'due', 'deadline', 'deliverable'])
    if 'instructor' in item_lower or 'professor' in item_lower:
        key_terms.extend(['instructor', 'professor', 'faculty', 'teacher', 'contact', 'office', 'hours', 'email'])
    if 'policy' in item_lower:
        key_terms.extend(['policy', 'policies', 'rule', 'regulation', 'guideline', 'requirement'])
    if 'academic' in item_lower and 'integrity' in item_lower:
        key_terms.extend(['academic', 'integrity', 'honesty', 'plagiarism', 'misconduct', 'cheating'])
    if 'missed' in item_lower and ('assignment' in item_lower or 'exam' in item_lower):
        key_terms.extend(['missed', 'missing', 'absence', 'absent', 'late', 'extension', 'deferral'])
    if 'accommodation' in item_lower:
        key_terms.extend(['accommodation', 'disability', 'access', 'accessib', 'student', 'service'])
    
    # For email requirements, add specific email-related terms
    if is_email_requirement:
        key_terms.extend(['email', '@ucalgary.ca', 'contact', 'instructor', 'professor'])
    
    # Remove duplicates and sort by length (longer terms first)
    key_terms = list(set(key_terms))
    key_terms.sort(key=len, reverse=True)
    
    # Use two approaches: paragraph-based and section-based
    
    # 1. Paragraph-based approach (for shorter documents)
    paragraphs = document_text.split('\n\n')
    best_paragraph_score = 0
    best_paragraph = ""
    best_paragraph_matches = []
    
    for paragraph in paragraphs:
        if len(paragraph.strip()) < 10:  # Skip very short paragraphs
            continue
            
        paragraph_lower = paragraph.lower()
        score = 0
        matches = []
        
        for term in key_terms:
            if term in paragraph_lower:
                # Weight longer terms more heavily
                term_weight = 1 + (len(term) / 20)  # e.g., a 10-letter term gets score 1.5
                score += term_weight
                matches.append(term)
                
        if score > best_paragraph_score:
            best_paragraph_score = score
            best_paragraph = paragraph
            best_paragraph_matches = matches
    
    # 2. Section-based approach (for structured documents)
    # Look for multiple paragraphs under the same heading
    section_matches = []
    current_section = ""
    current_section_title = ""
    current_section_score = 0
    current_section_matches = []
    
    for i, paragraph in enumerate(paragraphs):
        # Detect if this paragraph looks like a section title
        is_title = (len(paragraph.strip()) < 100 and 
                   (paragraph.strip().endswith(':') or 
                    paragraph.strip().isupper() or 
                    any(term in paragraph.lower() for term in ['course', 'instructor', 'grade', 'assignment', 
                                                              'policy', 'outline', 'textbook', 'exam'])))
        
        # If it's a title, start a new section
        if is_title:
            # Score and save the previous section if it exists
            if current_section and current_section_score > 0:
                section_matches.append((current_section, current_section_score, current_section_matches, current_section_title))
            
            # Start a new section
            current_section_title = paragraph
            current_section = paragraph + "\n\n"
            current_section_score = 0
            current_section_matches = []
        else:
            # Add to the current section
            current_section += paragraph + "\n\n"
            
            # Score this paragraph and add to section score
            paragraph_lower = paragraph.lower()
            for term in key_terms:
                if term in paragraph_lower:
                    term_weight = 1 + (len(term) / 20)
                    current_section_score += term_weight
                    if term not in current_section_matches:
                        current_section_matches.append(term)
    
    # Add the last section if it exists
    if current_section and current_section_score > 0:
        section_matches.append((current_section, current_section_score, current_section_matches, current_section_title))
    
    # Find the best-matching section
    best_section = ""
    best_section_score = 0
    best_section_matches = []
    
    for section, score, matches, title in section_matches:
        if score > best_section_score:
            best_section = section
            best_section_score = score
            best_section_matches = matches
    
    # Determine which approach gave better results
    use_section = (best_section_score > best_paragraph_score * 1.2)  # Prefer section if significantly better
    
    # Special handling for email requirements - need to find specifically @ucalgary.ca
    if is_email_requirement:
        # First look for ucalgary.ca emails in best matches
        ucalgary_email_regex = r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b'
        best_content = best_section if use_section else best_paragraph
        
        # Extract all ucalgary.ca emails
        ucalgary_emails = re.findall(ucalgary_email_regex, best_content)
        
        # If found, create excerpt focused on the email
        if ucalgary_emails:
            email = ucalgary_emails[0]
            email_idx = best_content.find(email)
            
            # Extract content around the email
            start_pos = max(0, email_idx - 150)
            end_pos = min(len(best_content), email_idx + len(email) + 150)
            
            # Adjust to not cut off in the middle of words
            while start_pos > 0 and best_content[start_pos].isalnum():
                start_pos -= 1
            while end_pos < len(best_content) and best_content[end_pos].isalnum():
                end_pos += 1
                
            excerpt = ("..." if start_pos > 0 else "") + best_content[start_pos:end_pos] + ("..." if end_pos < len(best_content) else "")
            return True, excerpt
    
    # Regular handling for non-email requirements or if email not found
    if use_section:
        best_matches = best_section_matches
        best_score = best_section_score
        best_content = best_section
    else:
        best_matches = best_paragraph_matches
        best_score = best_paragraph_score
        best_content = best_paragraph
    
    # Only consider it a match if we have enough matching terms or a high score
    # Higher threshold for longer items to avoid false positives
    min_score_threshold = 2 + (len(item) / 100)
    
    if best_score >= min_score_threshold or len(best_matches) >= 3:
        # If the content is too long, extract a focused excerpt
        if len(best_content) > 400:
            # Find the highest concentration of matching terms
            match_positions = []
            for term in best_matches:
                # Find all occurrences of this term
                term_lower = term.lower()
                content_lower = best_content.lower()
                start_idx = 0
                while start_idx < len(content_lower):
                    pos = content_lower.find(term_lower, start_idx)
                    if pos == -1:
                        break
                    match_positions.append((pos, term))
                    start_idx = pos + 1
            
            # Find the area with the highest density of matches
            if match_positions:
                # Sort by position
                match_positions.sort(key=lambda x: x[0])
                
                # Use sliding window to find region with most matches
                best_region_start = 0
                best_region_end = 0
                best_region_matches = 0
                window_size = 300
                
                for i in range(len(match_positions)):
                    window_end = match_positions[i][0]
                    window_start = window_end - window_size
                    
                    # Count matches in this window
                    matches_in_window = sum(1 for pos, _ in match_positions if window_start <= pos <= window_end)
                    
                    if matches_in_window > best_region_matches:
                        best_region_matches = matches_in_window
                        best_region_start = window_start
                        best_region_end = window_end
                
                # Adjust the window to include some context
                start_pos = max(0, best_region_start - 50)
                end_pos = min(len(best_content), best_region_end + 150)
                
                # Adjust to not cut off in the middle of words
                while start_pos > 0 and best_content[start_pos].isalnum():
                    start_pos -= 1
                while end_pos < len(best_content) and best_content[end_pos].isalnum():
                    end_pos += 1
                    
                excerpt = ("..." if start_pos > 0 else "") + best_content[start_pos:end_pos] + ("..." if end_pos < len(best_content) else "")
                return True, excerpt
            else:
                # If no match positions (shouldn't happen), use the first part of the content
                excerpt = best_content[:400] + "..."
                return True, excerpt
        else:
            # Content is short enough to use as is
            return True, best_content
    
    # If we reach here, no good match was found
    return False, None
