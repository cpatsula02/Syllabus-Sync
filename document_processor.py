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
    """Extract checklist items from the checklist document."""
    # Split text into lines and clean them
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Look for patterns like numbering, bullet points, or similar indicators
    checklist_items = []
    
    # Common bullet point and numbering patterns
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
            
        # If line is relatively short and looks like a checklist item
        # (not too short, not too long)
        if 10 <= len(line) <= 200 and not line.endswith(':'):
            checklist_items.append(line)
    
    # If no items found using patterns, fall back to sentences
    if not checklist_items:
        sentences = sent_tokenize(text)
        for sentence in sentences:
            clean_sentence = sentence.strip()
            if 10 <= len(clean_sentence) <= 200:
                checklist_items.append(clean_sentence)
    
    return checklist_items

def check_item_in_document(item: str, document_text: str) -> bool:
    """
    Check if a checklist item is present in the document text.
    Uses a more sophisticated matching approach beyond simple string matching.
    """
    # Clean and normalize text for comparison
    item_lower = item.lower()
    document_lower = document_text.lower()
    
    # Direct match - if the exact phrase appears
    if item_lower in document_lower:
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
    
    return False

def process_documents(checklist_path: str, outline_path: str) -> Tuple[List[str], Dict[str, bool]]:
    """Process both documents and return checklist items and matching results."""
    try:
        # Extract text from both documents
        checklist_text = extract_text(checklist_path)
        outline_text = extract_text(outline_path)
        
        # Extract checklist items
        checklist_items = extract_checklist_items(checklist_text)
        
        # Check each item against the course outline
        matching_results = {}
        for item in checklist_items:
            matching_results[item] = check_item_in_document(item, outline_text)
        
        return checklist_items, matching_results
        
    except Exception as e:
        logging.error(f"Error processing documents: {str(e)}")
        raise
