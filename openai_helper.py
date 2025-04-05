import logging
import os
from typing import List, Dict, Any
import re
from openai import OpenAI

# Configure OpenAI with API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Analyze if a checklist item is present in the document using semantic understanding.

    This function acts as a university academic reviewer, focusing on whether the 
    requirement described in the checklist item is meaningfully fulfilled in the 
    course outline.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses the requirement.

    Returns a dictionary with match result and confidence score.
    """
    # Use document_processor's specialized functions to get a more accurate result
    from document_processor import check_item_in_document, find_matching_excerpt

    # First check using the advanced semantic matching in check_item_in_document
    is_present = check_item_in_document(item, document_text)

    # If the item is present, try to find the specific section that matches it
    evidence = ""
    if is_present:
        found, excerpt = find_matching_excerpt(item, document_text)
        if found and excerpt:
            evidence = excerpt

    # Generate a meaningful explanation
    item_lower = item.lower()
    if is_present:
        # Create context-aware explanations
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline contains clearly listed or numbered learning objectives.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'The course outline includes a grade distribution or assessment weighting scheme.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Information about the final exam is provided in the course outline.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'The course outline specifies a policy for late assignments or submissions.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'The course outline addresses procedures for missed assessments or exams.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'The course outline provides instructor contact information and communication procedures.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'The course outline lists required or recommended textbooks or reading materials.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'The course outline includes a statement on academic integrity or misconduct.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'The course outline provides information about accommodations for students with disabilities.'
        else:
            explanation = 'This requirement is addressed in the course outline with relevant content.'
    else:
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline does not appear to have clearly listed or numbered learning objectives.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'A grade distribution or assessment weighting scheme was not found in the course outline.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Specific information about the final exam appears to be missing from the course outline.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'A clear policy for late assignments or submissions was not found in the course outline.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'Procedures for missed assessments or exams were not clearly identified in the course outline.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'Instructor contact information or communication procedures appear to be missing from the course outline.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'Required or recommended textbooks or reading materials were not clearly identified in the course outline.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'A statement on academic integrity or misconduct was not found in the course outline.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'Information about accommodations for students with disabilities appears to be missing from the course outline.'
        else:
            explanation = 'This requirement does not appear to be addressed in the course outline.'

    return {
        'present': is_present,
        'confidence': 0.85 if is_present else 0.15,
        'explanation': explanation,
        'evidence': evidence if is_present else "",
        'method': 'academic_review'
    }

def ai_analyze_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Use OpenAI to analyze if a checklist item is present in the document.

    This function provides advanced semantic understanding of whether
    the requirement in the checklist item is fulfilled in the course outline.
    """
    try:
        prompt = f"""
        As a University of Calgary academic course outline reviewer, analyze if the following checklist item 
        is addressed in the course outline. The same concept may be expressed with different phrasing or formatting.

        CHECKLIST ITEM: {item}

        COURSE OUTLINE TEXT: {document_text[:4000]}...

        Provide a JSON response with the following fields:
        - "present": boolean indicating if the item is addressed in the outline
        - "confidence": number between 0 and 1 indicating confidence in the decision
        - "explanation": detailed explanation of why the item is or is not present
        - "evidence": if present, provide the exact text from the outline that addresses this item
        - "method": should be "ai_analysis"
        """

        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are an expert academic document reviewer for the University of Calgary."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        # Parse the JSON response
        result = eval(response.choices[0].message.content)

        # Ensure all required fields are present
        if not all(key in result for key in ["present", "confidence", "explanation", "evidence", "method"]):
            raise ValueError("API response missing required fields")

        return result
    except Exception as e:
        logger.error(f"Error using AI analysis: {str(e)}")
        # Fall back to traditional analysis
        from document_processor import check_item_in_document, find_matching_excerpt
        is_present = check_item_in_document(item, document_text)
        evidence = ""
        if is_present:
            found, excerpt = find_matching_excerpt(item, document_text)
            if found and excerpt:
                evidence = excerpt

        return {
            'present': is_present,
            'confidence': 0.85 if is_present else 0.15,
            'explanation': f"Fallback analysis after AI error: {'Item is present in document' if is_present else 'Item not found in document'}",
            'evidence': evidence,
            'method': 'fallback_academic_review'
        }

def analyze_checklist_items_batch(items: List[str], document_text: str, max_attempts: int = 3) -> Dict[str, Dict[str, Any]]:
    """
    Process each checklist item using our semantic understanding approach,
    with optional AI-powered analysis for better results.

    This function acts as a university academic reviewer, focusing on whether each requirement 
    described in the checklist items is meaningfully fulfilled in the course outline.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses each requirement.

    Args:
        items: List of checklist items to analyze
        document_text: The full text of the document to check against
        max_attempts: Maximum number of API analysis attempts

    Returns:
        A dictionary mapping each item to its analysis result
    """
    results = {}
    ai_calls_made = 0

    # Decide whether to use AI analysis based on max_attempts
    use_ai = max_attempts > 0 and OPENAI_API_KEY is not None

    if use_ai:
        logger.info(f'Analyzing {len(items)} checklist items with AI-powered semantic understanding')
    else:
        logger.info(f'Analyzing {len(items)} checklist items with traditional semantic understanding')

    # Process all items with AI when available
    for i, item in enumerate(items):
        item_id = f'Item #{i+1}'
        logger.info(f'Processing {item_id}: {item[:50]}{"..." if len(item) > 50 else ""}')

        # Attempt AI analysis if within max attempts
        if use_ai and ai_calls_made < max_attempts:
            try:
                result = ai_analyze_item(item, document_text)
                ai_calls_made += 1
                results[item] = result
                continue
            except Exception as e:
                logger.error(f"Error in AI analysis for {item_id}: {str(e)}")
                # Fall back to traditional analysis if AI fails

        # Use the traditional analyzer for remaining items
        result = analyze_checklist_item(item, document_text)
        results[item] = result

    return results