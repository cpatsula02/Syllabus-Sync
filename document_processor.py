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
    for i, item in enumerate(checklist_items, 1):
        logging.info(f"Checklist item {i}: {item}")

    return checklist_items

def check_item_in_document(item: str, document_text: str) -> bool:
    """
    Advanced semantic matching with strict validation for critical elements.
    Uses multiple strategies including header recognition, semantic equivalence,
    and specific pattern validation for critical items.
    """
    item_lower = item.lower()
    document_lower = document_text.lower()

    # Strict validation for critical elements
    if '@ucalgary.ca' in item_lower:
        # Specifically check for valid ucalgary.ca email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b'
        if not re.search(email_pattern, document_text):
            return False

    if 'late policy' in item_lower or 'late submission' in item_lower:
        late_patterns = [
            r'late\s+(?:submission|assignment)s?\s+(?:policy|policies|rule|guideline)',
            r'(?:policy|policies|penalty|penalties)\s+(?:for|on|regarding)\s+late\s+(?:submission|work|assignment)',
            r'late\s+(?:work|submission|assignment)s?\s+(?:will|shall|must|may|are|is)\s+(?:not\s+)?(?:be\s+)?(?:accepted|penalized|subject)'
        ]
        if not any(re.search(pattern, document_lower) for pattern in late_patterns):
            return False

    if 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
        missed_patterns = [
            r'miss(?:ed|ing)\s+(?:assignment|assessment|work|exam)s?\s+(?:policy|procedure|rule)',
            r'(?:policy|procedure)\s+(?:for|on|regarding)\s+miss(?:ed|ing)\s+(?:assignment|assessment|work)',
            r'(?:if|when)\s+you\s+miss\s+(?:an?\s+)?(?:assignment|assessment|exam)',
            r'deferral\s+(?:policy|procedure|request)',
            r'absence\s+(?:policy|procedure)'
        ]
        if not any(re.search(pattern, document_lower) for pattern in missed_patterns):
            return False

    if 'grade distribution' in item_lower or 'grading scheme' in item_lower:
        grade_patterns = [
            r'grade\s+(?:distribution|breakdown)',
            r'grading\s+(?:scheme|structure|system)',
            r'(?:course|final)\s+grade\s+(?:calculation|determination)',
            r'(?:assignment|assessment|component)\s+weight(?:ing)?s?',
            r'\b\d+%\s*(?:[-–]\s*\d+%)?(?:\s*:\s*|\s+for\s+)\w+'
        ]
        if not any(re.search(pattern, document_lower) for pattern in grade_patterns):
            return False

    if 'textbook' in item_lower or 'required reading' in item_lower:
        textbook_patterns = [
            r'(?:required|recommended)\s+(?:text|textbook|reading|material)',
            r'textbooks?\s*(?::|and\s+materials?)',
            r'course\s+materials?\s*:',
            r'reading\s+list',
            r'required\s+materials?\s+and\s+texts?'
        ]
        if not any(re.search(pattern, document_lower) for pattern in textbook_patterns):
            return False

    if 'final exam' in item_lower:
        exam_patterns = [
            r'final\s+exam(?:ination)?\s+(?:date|time|schedule|weight|worth|value)',
            r'final\s+exam(?:ination)?\s+(?:will|shall|must|may|is|are)\s+(?:be|worth|count|scheduled)',
            r'(?:date|time|schedule)\s+of\s+(?:the\s+)?final\s+exam',
            r'final\s+exam(?:ination)?\s*:\s*\d+%'
        ]
        if not any(re.search(pattern, document_lower) for pattern in exam_patterns):
            return False

    if 'instructor' in item_lower and 'contact' in item_lower:
        contact_patterns = [
            r'(?:instructor|professor|faculty)\s+contact\s+information',
            r'contact(?:ing)?\s+(?:the|your)\s+(?:instructor|professor)',
            r'instructor\s+(?:email|office\s+hours?|availability)',
            r'office\s+hours?\s*:',
            r'(?:email|contact)\s*:\s*[^\s]+@(?:ucalgary\.ca|[^\s]+)'
        ]
        if not any(re.search(pattern, document_lower) for pattern in contact_patterns):
            return False

    # Enhanced semantic matching for remaining items
    key_terms = extract_core_concepts(item_lower)
    section_matches = extract_document_sections(document_lower)

    # Check if any section contains the key terms with high confidence
    for section_title, content in section_matches.items():
        if sections_are_related(section_title, key_terms):
            if content_contains_concepts(content, key_terms):
                return True

    # Additional pattern matching for specific content types
    return check_special_entity_patterns(item, document_text)

    # Define semantic equivalence groups
    semantic_groups = {
        'missed_work': ['missed', 'absence', 'deferral', 'extension', 'make-up', 'makeup'],
        'assignment': ['assignment', 'work', 'task', 'project', 'submission', 'deliverable'],
        'exam': ['exam', 'test', 'quiz', 'assessment', 'examination'],
        'textbook': ['textbook', 'book', 'reading', 'material', 'resource'],
        'grade': ['grade', 'mark', 'score', 'weight', 'distribution', 'percentage'],
        'participation': ['participation', 'engage', 'discussion', 'contribute', 'attendance'],
    }

    # Extract document sections with headers
    sections = []
    current_header = ""
    current_content = []

    for line in document_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Header detection patterns
        header_patterns = [
            r'^[A-Z][^a-z]{0,3}[A-Z].*:?$',  # All caps headers
            r'^[A-Z][a-zA-Z\s]{2,50}:$',      # Title case with colon
            r'^\d+\.\s+[A-Z].*:?$',           # Numbered headers
            r'^[A-Z][a-zA-Z\s&]+\(?s?\)?:?$'  # Common section headers
        ]

        is_header = any(re.match(pattern, line) for pattern in header_patterns)

        if is_header:
            if current_header and current_content:
                sections.append((current_header, ' '.join(current_content)))
            current_header = line
            current_content = []
        else:
            current_content.append(line)

    # Add last section
    if current_header and current_content:
        sections.append((current_header, ' '.join(current_content)))

    # Check for semantic matches in each section
    for header, content in sections:
        header_lower = header.lower()
        content_lower = content.lower()

        # Direct matches in header
        if any(phrase in header_lower for phrase in re.findall(r'\b\w+\b', item_lower)):
            # Verify content relevance
            key_terms = set(re.findall(r'\b\w+\b', item_lower))
            content_terms = set(re.findall(r'\b\w+\b', content_lower))
            if len(key_terms & content_terms) >= 2:  # At least 2 matching terms
                return True

        # Semantic group matching
        for group_terms in semantic_groups.values():
            if any(term in item_lower for term in group_terms):
                # If item matches a semantic group, check if content contains related terms
                if any(term in content_lower for term in group_terms):
                    return True

        # Special case for policies
        if 'policy' in item_lower or 'policies' in item_lower:
            policy_indicators = ['policy', 'procedure', 'guideline', 'requirement', 'rule']
            if any(indicator in header_lower for indicator in policy_indicators):
                # Check content relevance
                policy_type = re.findall(r'\b\w+\b', item_lower)
                if any(word in content_lower for word in policy_type):
                    return True

        # Check for semantic equivalence in content
        key_phrases = re.findall(r'\b\w+\b', item_lower)
        content_phrases = re.findall(r'\b\w+\b', content_lower)

        # Calculate semantic similarity
        shared_terms = set(key_phrases) & set(content_phrases)
        if len(shared_terms) >= len(key_phrases) * 0.6:  # 60% match threshold
            return True

    # Special cases for specific content types
    if check_special_entity_patterns(item, document_text):
        return True

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
    if 'objective' in item_lower or 'listed' in item_lower or 'numbered' in item_lower:
        objective_patterns = [
            r'(?:course|learning)\s+objectives?(?:\s*:|\n)',
            r'\d+\.\s*(?:[A-Z][^.]*\.)',
            r'(?:^\s*|\n\s*)\d+\.\s+[A-Za-z]',
            r'(?:^\s*|\n\s*)(?:•|-|\*)\s+[A-Za-z]'
        ]
        return any(re.search(pattern, document, re.MULTILINE) for pattern in objective_patterns)

    # Check for tools/platforms/resources section
    if any(word in item_lower for word in ['tool', 'platform', 'resource']):
        resource_patterns = [
            r'(?:required|recommended)\s+(?:tools?|platforms?|resources?)',
            r'technology\s+requirements?',
            r'd2l',
            r'learning\s+management\s+system',
            r'software\s+requirements?',
            r'course\s+materials?\s+and\s+resources?'
        ]
        return any(re.search(pattern, document_lower) for pattern in resource_patterns)

    # Check for course workload section
    if 'workload' in item_lower:
        workload_patterns = [
            r'(?:course|expected)\s+workload',
            r'time\s+commitment',
            r'hours?\s+(?:per|each)\s+week',
            r'weekly\s+(?:time|hour|workload)',
            r'student\s+effort'
        ]
        return any(re.search(pattern, document_lower) for pattern in workload_patterns)

    # Check for missed assessment policy
    if 'missed' in item_lower and ('assessment' in item_lower or 'policy' in item_lower):
        missed_patterns = [
            r'missed\s+(?:assessment|assignment|exam|test)s?\s+(?:policy|procedure)',
            r'(?:policy|procedure)\s+(?:for|on|regarding)\s+missed',
            r'missing\s+(?:work|assignment|assessment)',
            r'absence\s+policy'
        ]
        return any(re.search(pattern, document_lower) for pattern in missed_patterns)

    # Check for late policy
    if 'late' in item_lower and 'policy' in item_lower:
        late_patterns = [
            r'late\s+(?:submission|work|assignment)s?\s+policy',
            r'(?:policy|penalties)\s+(?:for|on|regarding)\s+late',
            r'late\s+work\s+(?:will|shall|must|may)',
            r'penalties?\s+for\s+late'
        ]
        return any(re.search(pattern, document_lower) for pattern in late_patterns)

    # Check for contacting instructor section
    if 'contact' in item_lower or 'instructor' in item_lower:
        contact_patterns = [
            r'contact(?:ing)?\s+(?:your|the|an?)\s+(?:instructor|professor)',
            r'instructor\s+contact\s+information',
            r'(?:office|contact)\s+hours?',
            r'email:\s*[^\s]+@[^\s]+',
            r'instructor\s+availability'
        ]
        return any(re.search(pattern, document_lower) for pattern in contact_patterns)

    # Check for valid links
    if 'link' in item_lower or 'validate' in item_lower:
        url_patterns = [
            r'https?://[^\s<>"]+|www\.[^\s<>"]+',
            r'(?:ucalgary|d2l)\.ca/[^\s<>"]+',
            r'mailto:[^\s<>"]+@[^\s<>"]+'
        ]
        found_links = []
        for pattern in url_patterns:
            found_links.extend(re.findall(pattern, document))
        return len(found_links) > 0

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
        # CRITICAL REQUIREMENT: Only consider valid if we find:
        # 1. Email ending with @ucalgary.ca
        # 2. In a clear instructor context

        # IMPROVED DETECTION STRATEGY:
        # 1. First look for email patterns specifically
        # 2. Then verify the context is instructor-related
        # 3. Use multiple fallback strategies if initial check fails

        # Define all possible email formats we might encounter
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@ucalgary\.ca\b',  # Standard email format
            r'\b[A-Za-z0-9._%+-]+\s*\[\s*at\s*\]\s*ucalgary\s*\[\s*dot\s*\]\s*ca\b',  # Obfuscated format
            r'\b[A-Za-z0-9._%+-]+\s*\(\s*at\s*\)\s*ucalgary\s*\(\s*dot\s*\)\s*ca\b',  # Alternative obfuscation
        ]

        # FIND ALL EMAILS first, then check context
        all_emails = []
        for pattern in email_patterns:
            emails_found = re.findall(pattern, document)
            all_emails.extend(emails_found)

        # If no emails found at all, return false immediately
        if not all_emails:
            logging.debug(f"No ucalgary.ca email addresses found in document")
            return False

        # CONTEXT VERIFICATION - multiple approaches

        # 1. Find all possible instructor sections
        instructor_sections = []

        # Define stronger instructor-related section patterns with clearer boundaries
        instructor_section_patterns = [
            # Explicit instructor section headers
            r'(?:^|\n|\r)\s*(?:instructor|professor|faculty|teacher)(?:\s+information|\s*:)',
            r'(?:^|\n|\r)\s*contact(?:\s+information|\s*:)',
            r'(?:^|\n|\r)\s*contacting\s+(?:your|the|an?)\s+(?:instructor|professor|faculty|teacher)',
            r'(?:^|\n|\r)\s*course\s+(?:instructor|coordinator|professor|contact)(?:\s*:|\s+information)',

            # Common formats for contact information sections
            r'(?:^|\n|\r)\s*(?:instructor|professor|faculty|teacher|contact)\s*:',
            r'(?:^|\n|\r)\s*name\s*:.*?(?:instructor|professor|faculty)',
            r'(?:^|\n|\r)\s*(?:instructor|professor|faculty|teacher)\s+name\s*:'
        ]

        # Section-based approach: find instructor sections first
        paragraphs = document.split('\n\n')
        for i, paragraph in enumerate(paragraphs):
            paragraph_lower = paragraph.lower()

            # Check if this looks like an instructor section
            if any(re.search(pattern, paragraph_lower, re.MULTILINE) for pattern in instructor_section_patterns):
                # Found an instructor section - include this paragraph and next 2 paragraphs
                section_text = paragraph
                for j in range(1, 3):
                    if i + j < len(paragraphs):
                        section_text += "\n\n" + paragraphs[i+j]
                instructor_sections.append(section_text)

        # If we have both emails and instructor sections, check if they overlap
        if instructor_sections:
            for section in instructor_sections:
                section_lower = section.lower()

                # Check if any email appears in this section
                for email in all_emails:
                    if email.lower() in section_lower:
                        logging.debug(f"Found email {email} in instructor section")
                        return True

                # Also check for obfuscated emails in format
                for pattern in email_patterns:
                    if re.search(pattern, section, re.IGNORECASE):
                        logging.debug(f"Found email pattern in instructor section")
                        return True

        # 2. Contextual proximity approach
        # If we reach here, we have emails but not in instructor sections
        # Look for instructor terms near email addresses
        for email in all_emails:
            email_idx = document.lower().find(email.lower())
            if email_idx >= 0:
                # Look at 150 characters before and after the email
                surrounding_text = document[max(0, email_idx-150):min(len(document), email_idx+len(email)+150)]
                surrounding_lower = surrounding_text.lower()

                # Check for instructor context terms
                instructor_context_terms = [
                    'instructor', 'professor', 'faculty', 'teacher', 'lecturer', 
                    'contact', 'office', 'hours', 'email'
                ]

                context_score = sum(1 for term in instructor_context_terms if term in surrounding_lower)

                # If we have at least 2 context terms, this is likely an instructor email
                if context_score >= 2:
                    logging.debug(f"Found email {email} with instructor context (score: {context_score})")

                    # Verify this isn't a generic university email not tied to instructor
                    negative_patterns = [
                        r'example', r'do not email', r'general inquiries', 
                        r'department email', r'faculty email', r'university email',
                        r'sample', r'template'
                    ]

                    # Check for negative context that would invalidate this match
                    if not any(re.search(pattern, surrounding_lower) for pattern in negative_patterns):
                        return True

        # 3. Line-based instructor context
        # If we reach here, try one more approach: look for lines that contain both
        # instructor terms and emails
        lines = document.split('\n')
        for line in lines:
            line_lower = line.lower()

            # Check if line contains instructor context
            has_instructor_context = any(term in line_lower for term in 
                                         ['instructor', 'professor', 'faculty', 'contact', 'email'])

            # Check if line contains email
            has_email = any(re.search(pattern, line) for pattern in email_patterns)

            # If both conditions are true, this is a match
            if has_instructor_context and has_email:
                logging.debug(f"Found email with instructor context on same line")
                return True

        # If we've exhausted all methods and still can't verify the context,
        # this might be a false positive email somewhere in the document
        logging.debug(f"Found ucalgary.ca emails but couldn't verify instructor context")
        return False

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

    # Balanced threshold calculation considering both strict and lenient criteria
    min_score_threshold = 1.5 + (len(item) / 150)  # Reduced base threshold
    min_matches = 2  # Reduced required matches

    # Consider semantic variations and context
    has_semantic_match = any(
        term in best_content.lower() 
        for term in best_matches 
        if len(term) > 4  # Only consider meaningful terms
    )

    # More lenient scoring for certain types of items
    if any(keyword in item.lower() for keyword in ['policy', 'procedure', 'guideline', 'requirement']):
        min_score_threshold *= 0.8  # 20% more lenient for policy-related items

    if best_score >= min_score_threshold or len(best_matches) >= min_matches or has_semantic_match:
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

def process_documents(checklist_path: str, outline_path: str, api_attempts: int = 3, additional_context: str = "") -> Tuple[List[str], Dict[str, Any]]:
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

        # If additional context is provided, prepend it to the outline text
        if additional_context and additional_context.strip():
            logging.info("Using additional context for analysis")
            outline_text = f"{additional_context}\n\n{outline_text}"

        # Log document sizes for debugging
        logging.info(f"Checklist text length: {len(checklist_text)}")
        logging.info(f"Outline text length: {len(outline_text)}")

        # Extract checklist items from the checklist document
        checklist_items = extract_checklist_items(checklist_text)
        logging.info(f"Extracted {len(checklist_items)} checklist items")

        # If we couldn't extract any items, return error
        if not checklist_items:
            return [], {"error": "No checklist items could be extracted. Please check the format of your checklist."}

        # Determine analysis method based on API attempts parameter
        if api_attempts > 0:
            try:
                # Import here to avoid circular imports
                from openai_helper import analyze_checklist_items_batch
                logging.info(f"Using AI-powered analysis with up to {api_attempts} API requests")
                matching_results = analyze_checklist_items_batch(checklist_items, outline_text, api_attempts)

                # Add more detailed evidence for each item that's present
                for item, result in matching_results.items():
                    if result["present"] and not result.get("evidence"):
                        found, excerpt = find_matching_excerpt(item, outline_text)
                        if found and excerpt:
                            result["evidence"] = excerpt

                return checklist_items, matching_results

            except Exception as e:
                logging.error(f"Error using AI-powered analysis: {str(e)}")
                logging.info("Falling back to traditional pattern matching")
                # Continue with traditional method if AI analysis fails
        else:
            logging.info("Using traditional pattern matching for all items (API attempts set to 0)")

        # Traditional analysis as fallback
        matching_results = {}
        for item in checklist_items:
            is_present = check_item_in_document(item, outline_text)

            # Get evidence if present
            evidence = ""
            if is_present:
                found, excerpt = find_matching_excerpt(item, outline_text)
                if found and excerpt:
                    evidence = excerpt

            # Create a more detailed explanation based on item content
            item_lower = item.lower()

            # Generate useful explanations based on content type
            if is_present:
                if 'policy' in item_lower or 'policies' in item_lower:
                    explanation = "Policy content detected in document sections"
                elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                    explanation = "Found missed assignment/assessment policy content"
                elif 'assignment' in item_lower or 'assessment' in item_lower:
                    explanation = "Assignment/assessment details detected in document"
                elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                    explanation = "Grade information found in document sections"
                elif 'participation' in item_lower:
                    explanation = "Class participation information detected"
                elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                    explanation = "Course materials/textbook information found"
                elif 'objective' in item_lower or 'outcome' in item_lower:
                    explanation = "Course objectives/outcomes detected"
                elif 'schedule' in item_lower or 'calendar' in item_lower:
                    explanation = "Course schedule/calendar information found"
                elif 'contact' in item_lower or 'instructor' in item_lower:
                    explanation = "Instructor contact information detected"
                elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                    explanation = "Exam/assessment information found"
                elif 'late' in item_lower and ('submission' in item_lower or 'assignment' in item_lower):
                    explanation = "Late submission policy information found"
                elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
                    explanation = "Academic integrity policy information found"
                elif 'disability' in item_lower or 'accommodation' in item_lower:
                    explanation = "Accommodation information detected"
                elif 'prerequisite' in item_lower:
                    explanation = "Course prerequisite information found"
                else:
                    explanation = "Content matched through document analysis"
            else:
                explanation = "Not found in document"

            matching_results[item] = {
                "present": is_present,
                "confidence": 0.85 if is_present else 0.2,
                "explanation": explanation,
                "evidence": evidence,
                "method": "traditional"
            }

        return checklist_items, matching_results

    except FileNotFoundError as e:
        logging.error(f"File not found: {str(e)}")
        return [], {"error": str(e)}
    except ValueError as e:
        logging.error(f"Invalid input: {str(e)}")
        return [], {"error": str(e)}
    except Exception as e:
        # Handle any errors during processing
        logging.exception(f"An unexpected error occurred: {str(e)}")
        return [], {"error": f"An unexpected error occurred: {str(e)}"}

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

    # Balanced threshold calculation considering both strict and lenient criteria
    min_score_threshold = 1.5 + (len(item) / 150)  # Reduced base threshold
    min_matches = 2  # Reduced required matches

    # Consider semantic variations and context
    has_semantic_match = any(
        term in best_content.lower() 
        for term in best_matches 
        if len(term) > 4  # Only consider meaningful terms
    )

    # More lenient scoring for certain types of items
    if any(keyword in item.lower() for keyword in ['policy', 'procedure', 'guideline', 'requirement']):
        min_score_threshold *= 0.8  # 20% more lenient for policy-related items

    if best_score >= min_score_threshold or len(best_matches) >= min_matches or has_semantic_match:
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

def process_documents(checklist_path: str, outline_path: str, api_attempts: int = 3, additional_context: str = "") -> Tuple[List[str], Dict[str, Any]]:
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

        # If additional context is provided, prepend it to the outline text
        if additional_context and additional_context.strip():
            logging.info("Using additional context for analysis")
            outline_text = f"{additional_context}\n\n{outline_text}"

        # Log document sizes for debugging
        logging.info(f"Checklist text length: {len(checklist_text)}")
        logging.info(f"Outline text length: {len(outline_text)}")

        # Extract checklist items from the checklist document
        checklist_items = extract_checklist_items(checklist_text)
        logging.info(f"Extracted {len(checklist_items)} checklist items")

        # If we couldn't extract any items, return error
        if not checklist_items:
            return [], {"error": "No checklist items could be extracted. Please check the format of your checklist."}

        # Determine analysis method based on API attempts parameter
        if api_attempts > 0:
            try:
                # Import here to avoid circular imports
                from openai_helper import analyze_checklist_items_batch
                logging.info(f"Using AI-powered analysis with up to {api_attempts} API requests")
                matching_results = analyze_checklist_items_batch(checklist_items, outline_text, api_attempts)

                # Add more detailed evidence for each item that's present
                for item, result in matching_results.items():
                    if result["present"] and not result.get("evidence"):
                        found, excerpt = find_matching_excerpt(item, outline_text)
                        if found and excerpt:
                            result["evidence"] = excerpt

                return checklist_items, matching_results

            except Exception as e:
                logging.error(f"Error using AI-powered analysis: {str(e)}")
                logging.info("Falling back to traditional pattern matching")
                # Continue with traditional method if AI analysis fails
        else:
            logging.info("Using traditional pattern matching for all items (API attempts set to 0)")

        # Traditional analysis as fallback
        matching_results = {}
        for item in checklist_items:
            is_present = check_item_in_document(item, outline_text)

            # Get evidence if present
            evidence = ""
            if is_present:
                found, excerpt = find_matching_excerpt(item, outline_text)
                if found and excerpt:
                    evidence = excerpt

            # Create a more detailed explanation based on item content
            item_lower = item.lower()

            # Generate useful explanations based on content type
            if is_present:
                if 'policy' in item_lower or 'policies' in item_lower:
                    explanation = "Policy content detected in document sections"
                elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                    explanation = "Found missed assignment/assessment policy content"
                elif 'assignment' in item_lower or 'assessment' in item_lower:
                    explanation = "Assignment/assessment details detected in document"
                elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                    explanation = "Grade information found in document sections"
                elif 'participation' in item_lower:
                    explanation = "Class participation information detected"
                elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                    explanation = "Course materials/textbook information found"
                elif 'objective' in item_lower or 'outcome' in item_lower:
                    explanation = "Course objectives/outcomes detected"
                elif 'schedule' in item_lower or 'calendar' in item_lower:
                    explanation = "Course schedule/calendar information found"
                elif 'contact' in item_lower or 'instructor' in item_lower:
                    explanation = "Instructor contact information detected"
                elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                    explanation = "Exam/assessment information found"
                elif 'late' in item_lower and ('submission' in item_lower or 'assignment' in item_lower):
                    explanation = "Late submission policy information found"
                elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
                    explanation = "Academic integrity policy information found"
                elif 'disability' in item_lower or 'accommodation' in item_lower:
                    explanation = "Accommodation information detected"
                elif 'prerequisite' in item_lower:
                    explanation = "Course prerequisite information found"
                else:
                    explanation = "Content matched through document analysis"
            else:
                explanation = "Not found in document"

            matching_results[item] = {
                "present": is_present,
                "confidence": 0.85 if is_present else 0.2,
                "explanation": explanation,
                "evidence": evidence,
                "method": "traditional"
            }

        return checklist_items, matching_results

    except FileNotFoundError as e:
        logging.error(f"File not found: {str(e)}")
        return [], {"error": str(e)}
    except ValueError as e:
        logging.error(f"Invalid input: {str(e)}")
        return [], {"error": str(e)}
    except Exception as e:
        # Handle any errors during processing
        logging.exception(f"An unexpected error occurred: {str(e)}")
        return [], {"error": f"An unexpected error occurred: {str(e)}"}