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
    
    # 3. Policy-specific checks
    if any(word in item_lower for word in ['policy', 'policies', 'requirements', 'guideline', 'guidelines']):
        # Extract policy type (e.g., "missed assignment policy" -> "missed assignment")
        policy_type = extract_policy_type(item_lower)
        
        if policy_type:
            policy_patterns = [
                # Policy header patterns
                r'(^|\n)([^.!?\n]*' + re.escape(policy_type) + r'[^.!?\n]*(?:policy|policies|guidelines|rule|protocol)[^.!?\n]*)',
                # Policy in paragraph patterns
                r'([^.!?]*' + re.escape(policy_type) + r'[^.!?]*(?:policy|policies|guidelines|rule|protocol)[^.!?]*[.!?])'
            ]
            
            for pattern in policy_patterns:
                if re.search(pattern, document_lower, re.IGNORECASE):
                    return True
    
    # 4. Check for semantically similar content without exact wording matches
    if check_semantic_similarity(item_lower, document_lower, item_concepts):
        return True
    
    # 5. Special entity-specific checks
    if check_special_entity_patterns(item_lower, document_lower):
        return True
    
    # 6. Fallback: Check for keyword density
    try:
        stop_words = set(stopwords.words('english'))
        item_words = [word for word in re.findall(r'\b\w+\b', item_lower) 
                     if word not in stop_words and len(word) > 2]
        
        # Count how many important words appear in the document
        words_found = sum(1 for word in item_words if word in document_lower)
        
        # Lower the threshold to 65% to catch more matches with different wording
        if len(item_words) > 0 and words_found / len(item_words) >= 0.65:
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
    # Flatten all terms from all concepts for easier checking
    all_concept_terms = []
    for terms in item_concepts.values():
        all_concept_terms.extend(terms)
    
    # Check if a significant number of terms appear in the section content
    terms_found = sum(1 for term in all_concept_terms if term in section_content)
    
    # If at least 60% of the terms are found in this section, consider it a match
    return len(all_concept_terms) > 0 and terms_found / len(all_concept_terms) >= 0.6

def extract_policy_type(item_text):
    """Extract the type of policy from policy-related checklist items."""
    policy_words = ['policy', 'policies', 'guideline', 'guidelines', 'requirement', 
                   'requirements', 'procedure', 'procedures', 'protocol', 'protocols', 'rule', 'rules']
    
    for word in policy_words:
        if word in item_text:
            # Find what kind of policy (e.g., "missed assignment policy" -> "missed assignment")
            pattern = re.compile(r'([\w\s]+)\s+' + word)
            match = pattern.search(item_text)
            if match:
                return match.group(1).strip()
    
    return None

def check_semantic_similarity(item, document, item_concepts):
    """Check for semantic similarity between checklist item and document content."""
    # Try to construct meaningful combinations from the item
    meaningful_combinations = []
    
    # Check specific semantic patterns
    
    # Pattern 1: Course objectives/learning outcomes
    if 'objective' in item_concepts or 'learning' in item or 'outcome' in item:
        patterns = [
            r'(course|learning|student)\s+(objectives|outcomes|goals)',
            r'(by the end|students will|learners will)',
            r'(upon completion|after completing)'
        ]
        for pattern in patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Pattern 2: Textbooks and materials
    if 'textbook' in item_concepts:
        patterns = [
            r'(required|recommended)\s+(textbook|text|reading|material)',
            r'(course|class)\s+(material|resource|text|book)',
            r'(text|book|reading)\s+(list|requirement|required)'
        ]
        for pattern in patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Pattern 3: Grade distribution/assessment
    if 'grade_distribution' in item_concepts:
        patterns = [
            r'(grade|grading|mark)\s+(distribution|breakdown|allocation|scheme)',
            r'(assessment|evaluation)\s+(component|criteria|method|breakdown)',
            r'(final\s+grade|course\s+grade)\s+(determined|calculated|comprised)',
            r'(grade|mark|score)\s+(weighting|weight|percentage|worth)'
        ]
        for pattern in patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
        
        # Also look for grade tables or distributions in list format
        grade_table_pattern = r'(assignment|quiz|exam|test|participation|project).*?(\d+%|\d+\s+percent)'
        if re.search(grade_table_pattern, document, re.IGNORECASE):
            return True
    
    # Additional patterns for checking more specific items
    # Pattern 4: Class participation rules
    if 'participation' in item_concepts:
        if any(term in document for term in ['class participation', 'participation grade', 'participate in class', 'participation will be']):
            return True
    
    # Pattern 5: Assignment details
    if 'assignment' in item_concepts:
        assignment_patterns = [
            r'(assignment|homework|project)\s+(description|detail|instruction)',
            r'(submit|submission|complete)\s+(assignment|homework|project)',
            r'(assignment|homework|project)\s+(due|deadline)'
        ]
        for pattern in assignment_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    return False

def check_special_entity_patterns(item, document):
    """Check for special entity patterns that might be missed by other methods."""
    # Special pattern for missed assignment policies
    if 'missed' in item and ('assignment' in item or 'assessment' in item):
        missed_patterns = [
            r'missed\s+assessment',
            r'missed\s+assignment', 
            r'missing\s+(work|assignment|assessment|exam|quiz)',
            r'absence\s+from\s+(class|exam|assessment|assignment)',
            r'(extension|deferral)\s+for\s+(assignment|assessment|exam)',
            r'(accommodation|consideration)\s+for\s+missed'
        ]
        for pattern in missed_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Special pattern for late policies
    if 'late' in item and ('assignment' in item or 'work' in item or 'policy' in item):
        late_patterns = [
            r'late\s+(assignment|submission|work)',
            r'(late|penalty)\s+policy', 
            r'(submission|work|assignment)\s+after\s+deadline',
            r'(deduction|penalty)\s+for\s+late',
            r'(grade|mark)\s+reduction\s+for\s+late'
        ]
        for pattern in late_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Special pattern for final exam details
    if 'final' in item and ('exam' in item or 'examination' in item):
        final_exam_patterns = [
            r'final\s+(exam|examination)',
            r'(exam|examination)\s+schedule', 
            r'(exam|test)\s+worth\s+\d+%',
            r'(cumulative|comprehensive)\s+final',
            r'(registrar|scheduled)\s+(exam|examination)'
        ]
        for pattern in final_exam_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Special pattern for class schedule
    if 'schedule' in item or 'topic' in item or 'calendar' in item:
        schedule_patterns = [
            r'(class|course|lecture)\s+(schedule|calendar|topic|outline)',
            r'(weekly|daily)\s+(topic|reading|schedule)',
            r'(topic|module|unit)\s+(covered|discussed)',
            r'(schedule|calendar)\s+of\s+(class|topic|reading)'
        ]
        for pattern in schedule_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
    # Special pattern for contacting instructor
    if 'contact' in item or 'instructor' in item or 'professor' in item:
        contact_patterns = [
            r'(contact|email|reach)\s+(instructor|professor|teacher|faculty)',
            r'(instructor|professor|faculty)\s+(contact|information|email)',
            r'(office|email|phone)\s+(hour|location)',
            r'(communicate|contact)\s+with\s+(me|instructor|professor)'
        ]
        for pattern in contact_patterns:
            if re.search(pattern, document, re.IGNORECASE):
                return True
    
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
        
        # Add additional context to outline text if provided
        if additional_context:
            context_header = "\n\n--- ADDITIONAL COURSE CONTEXT ---\n\n"
            outline_text = outline_text + context_header + additional_context
            logging.info(f"Added {len(additional_context)} characters of additional context")
        
        # Extract checklist items (only numbered or bulleted items)
        checklist_items = extract_checklist_items(checklist_text)
        
        # Check if we found any checklist items
        if not checklist_items:
            logging.warning("No numbered or bulleted checklist items found in the document!")
            return [], {}
            
        # Initialize empty results dictionary
        matching_results = {}
        
        # Try using OpenAI for more accurate analysis if available
        # The new implementation attempts to process ALL items individually
        try:
            import openai_helper
            logging.info(f"Using OpenAI for document analysis with {api_attempts} attempts per item")
            
            # Process all items individually through OpenAI (with fallback handling built in)
            ai_results = openai_helper.analyze_checklist_items_batch(
                checklist_items, 
                outline_text, 
                max_attempts=api_attempts
            )
            
            # Add AI results to our matching results
            for item, result in ai_results.items():
                matching_results[item] = result
                
        except ImportError:
            logging.warning("OpenAI helper module not available, using only traditional methods")
        except Exception as ai_error:
            logging.warning(f"OpenAI analysis failed: {str(ai_error)}")
        
        # Check if there are any items not processed yet
        unprocessed_items = [item for item in checklist_items if item not in matching_results]
        
        if unprocessed_items:
            logging.info(f"Using traditional NLP for {len(unprocessed_items)} remaining items")
            for item in unprocessed_items:
                is_present = check_item_in_document(item, outline_text)
                # Format the result to match the OpenAI structure for consistency
                matching_results[item] = {
                    "present": is_present,
                    "confidence": 0.8 if is_present else 0.2,
                    "explanation": "Detected using pattern matching" if is_present else "Not found in document",
                    "method": "traditional"  # Mark which method was used
                }
        
        # Count methods used for detailed logging
        ai_count = sum(1 for result in matching_results.values() if result.get("method", "").startswith("openai"))
        traditional_count = sum(1 for result in matching_results.values() if result.get("method", "").startswith("traditional"))
        
        logging.info(f"Analysis complete: {ai_count} items processed with OpenAI, {traditional_count} with traditional methods")
        
        return checklist_items, matching_results
        
    except Exception as e:
        logging.error(f"Error processing documents: {str(e)}")
        raise
