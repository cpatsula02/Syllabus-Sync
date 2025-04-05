import logging
from typing import List, Dict, Any
import re

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Analyze if a checklist item is present in the document using traditional methods.
    This is a fallback version that doesn't use OpenAI API.
    
    Returns a dictionary with match result and confidence score.
    """
    # Simple keyword matching for testing
    item_lower = item.lower()
    document_lower = document_text.lower()
    
    # Check if the item appears directly in the document
    direct_match = item_lower in document_lower
    
    # Split the item into key terms and check how many appear in the document
    terms = re.findall(r'\b\w+\b', item_lower)
    significant_terms = [term for term in terms if len(term) > 3]
    
    # Count how many significant terms appear in the document
    matching_terms = sum(1 for term in significant_terms if term in document_lower)
    match_ratio = matching_terms / len(significant_terms) if significant_terms else 0
    
    is_present = direct_match or match_ratio > 0.7
    
    # Generate an explanation based on the item type
    explanation = 'Not found in document'
    if is_present:
        explanation = 'Found match in document through pattern analysis'
    
    return {
        'present': is_present,
        'confidence': 0.8 if is_present else 0.2,
        'explanation': explanation,
        'method': 'traditional'
    }

def analyze_checklist_items_batch(items: List[str], document_text: str, max_attempts: int = 3) -> Dict[str, Dict[str, Any]]:
    """
    Process each checklist item using traditional methods.
    OpenAI API calls have been removed to prevent rate limiting.
    
    Args:
        items: List of checklist items to analyze
        document_text: The full text of the document to check against
        max_attempts: Maximum number of API analysis attempts (ignored in this version)
    
    Returns:
        A dictionary mapping each item to its analysis result
    """
    results = {}
    
    # Process each item with traditional method
    logger.info(f'Analyzing {len(items)} checklist items with traditional methods')
    
    for i, item in enumerate(items):
        item_id = f'Item #{i+1}'
        logger.info(f'Processing {item_id}: {item[:50]}{"..." if len(item) > 50 else ""}')
        
        # Use traditional method
        from document_processor import check_item_in_document
        is_present = check_item_in_document(item, document_text)
        
        # Create more detailed explanation based on item content
        item_lower = item.lower()
        
        # Generate useful explanations based on content type
        if is_present:
            if 'policy' in item_lower or 'policies' in item_lower:
                explanation = 'Policy content detected in document sections'
            elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                explanation = 'Found missed assignment/assessment policy content'
            elif 'assignment' in item_lower or 'assessment' in item_lower:
                explanation = 'Assignment/assessment details detected in document'
            elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                explanation = 'Grade information found in document sections'
            elif 'participation' in item_lower:
                explanation = 'Class participation information detected'
            elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                explanation = 'Course materials/textbook information found'
            elif 'objective' in item_lower or 'outcome' in item_lower:
                explanation = 'Course objectives/outcomes detected'
            elif 'schedule' in item_lower or 'calendar' in item_lower:
                explanation = 'Course schedule/calendar information found'
            elif 'contact' in item_lower or 'instructor' in item_lower:
                explanation = 'Instructor contact information detected'
            elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                explanation = 'Exam/assessment information found'
            elif 'late' in item_lower and ('submission' in item_lower or 'assignment' in item_lower):
                explanation = 'Late submission policy information found'
            elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
                explanation = 'Academic integrity policy information found'
            elif 'disability' in item_lower or 'accommodation' in item_lower:
                explanation = 'Accommodation information detected'
            elif 'prerequisite' in item_lower:
                explanation = 'Course prerequisite information found'
            else:
                explanation = 'Content matched through document analysis'
        else:
            explanation = 'Not found in document'
        
        results[item] = {
            'present': is_present,
            'confidence': 0.85 if is_present else 0.2,
            'explanation': explanation,
            'method': 'traditional'
        }
    
    return results