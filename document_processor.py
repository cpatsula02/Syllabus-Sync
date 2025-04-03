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
    Uses a more sophisticated matching approach beyond simple string matching.
    Enhanced for policy-related content detection.
    """
    # Clean and normalize text for comparison
    item_lower = item.lower()
    document_lower = document_text.lower()
    
    # Direct match - if the exact phrase appears
    if item_lower in document_lower:
        return True
    
    # Special policy-related pattern detection
    # Look for policy headers and content related to the item
    if 'policy' in item_lower or 'policies' in item_lower or 'requirements' in item_lower:
        # For specific policy items, generate variations to check
        policy_words = ['policy', 'policies', 'guideline', 'guidelines', 'requirement', 'requirements', 'procedure', 'protocol']
        
        # Extract the policy type from the item
        policy_type = ''
        for word in policy_words:
            if word in item_lower:
                # Find what kind of policy (e.g., "missed assignment policy" -> "missed assignment")
                pattern = re.compile(r'([\w\s]+)\s+' + word)
                match = pattern.search(item_lower)
                if match:
                    policy_type = match.group(1).strip()
                    break
        
        # If we found a policy type, check for its presence in any form
        if policy_type:
            # Check if the policy type appears near policy-related words
            policy_sections = re.findall(r'([^.!?]*(?:policy|policies|guidelines|procedures|protocols)[^.!?]*[.!?])', document_lower)
            
            for section in policy_sections:
                # Check if this policy section contains our type
                if policy_type in section or any(word in section for word in policy_type.split()):
                    return True
            
            # Also check for headers that might match the policy type
            # Headers often have special formatting (e.g., "Missed Assessment Policy:")
            header_pattern = re.compile(r'(^|\n)([^.!?\n]*' + re.escape(policy_type) + r'[^.!?\n]*(?:policy|policies|guidelines|procedures|protocols)[^.!?\n]*)', re.IGNORECASE)
            if header_pattern.search(document_lower):
                return True
    
    # Extract important keywords from the item (remove stopwords)
    try:
        stop_words = set(stopwords.words('english'))
        item_words = [word for word in re.findall(r'\b\w+\b', item_lower) 
                     if word not in stop_words and len(word) > 2]
        
        # Count how many important words appear in the document
        words_found = sum(1 for word in item_words if word in document_lower)
        
        # If more than 70% of important words are found, consider it a match
        if len(item_words) > 0 and words_found / len(item_words) >= 0.7:
            return True
    except:
        # Fall back to simple matching if NLP processing fails
        pass
    
    # Check for sentence similarity with fuzzy matching
    # Split item into words and check if most of them appear close together
    item_parts = item_lower.split()
    if len(item_parts) >= 3:
        # Check for at least 3/4 of consecutive words appearing
        min_required = max(3, len(item_parts) * 3 // 4)
        for i in range(len(item_parts) - min_required + 1):
            phrase = ' '.join(item_parts[i:i+min_required])
            if phrase in document_lower:
                return True
    
    # Check for semantic equivalents (especially for policies)
    # This checks for cases where policy content exists but with different wording
    if 'miss' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower) and 'policy' in item_lower:
        # Look for sections that talk about missed assignments/assessments
        missed_terms = ['miss', 'missed', 'missing', 'absence', 'absent']
        assignment_terms = ['assignment', 'assessment', 'work', 'quiz', 'exam', 'test']
        policy_terms = ['policy', 'policies', 'procedure', 'guideline', 'rule', 'requirement', 'deferral', 'defer']
        
        # Check for proximity of these terms
        for m_term in missed_terms:
            for a_term in assignment_terms:
                # Check if these terms appear within a reasonable distance
                for p_term in policy_terms:
                    pattern = re.compile(r'[^.!?]*' + m_term + r'[^.!?]*' + a_term + r'[^.!?]*' + p_term + r'[^.!?]*[.!?]', re.IGNORECASE)
                    if pattern.search(document_lower):
                        return True
                    
                    # Try reverse order too (policy term first, then missed term)
                    pattern = re.compile(r'[^.!?]*' + p_term + r'[^.!?]*' + m_term + r'[^.!?]*' + a_term + r'[^.!?]*[.!?]', re.IGNORECASE)
                    if pattern.search(document_lower):
                        return True
    
    return False

def process_documents(checklist_path: str, outline_path: str) -> Tuple[List[str], Dict[str, Any]]:
    """Process both documents and return checklist items and matching results with detailed breakdown."""
    try:
        # Extract text from both documents
        checklist_text = extract_text(checklist_path)
        outline_text = extract_text(outline_path)
        
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
            logging.info("Using OpenAI for document analysis")
            
            # Process all items individually through OpenAI (with fallback handling built in)
            ai_results = openai_helper.analyze_checklist_items_batch(checklist_items, outline_text)
            
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
