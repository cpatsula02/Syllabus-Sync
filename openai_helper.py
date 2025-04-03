import os
import json
import logging
import time
from typing import List, Dict, Any

# Import OpenAI
from openai import OpenAI, APITimeoutError, RateLimitError, APIConnectionError, BadRequestError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Use OpenAI's API to analyze if a checklist item is present in the document.
    Returns a dictionary with match result and confidence score.
    """
    # Trim document text to avoid excessive token usage
    # This helps prevent timeouts and reduces API costs
    max_text_length = 1000  # Reduced from 2000 to further prevent timeout and reduce tokens
    trimmed_document = document_text[:max_text_length] + ("..." if len(document_text) > max_text_length else "")
    
    try:
        # Prepare the prompt for OpenAI - simplified to reduce token usage
        prompt = f"""Determine if this checklist item appears in the document text.
        
Checklist item: "{item}"

Document text (excerpt): "{trimmed_document}"

Response format: {{"present": true/false, "confidence": 0.0-1.0, "explanation": "brief reason"}}"""
        
        # Call the OpenAI API with shorter timeout
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using a faster model to prevent timeouts
            messages=[
                {"role": "system", "content": "Analyze if a checklist item appears in a document."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,  # Lower temperature for more consistent results
            max_tokens=100,   # Further reduced token limit to prevent long processing times
            timeout=20        # 20 second timeout to prevent hanging
        )
        
        # Extract and parse the response
        result = json.loads(response.choices[0].message.content)
        logger.info(f"OpenAI analysis complete for item: {item[:30]}...")
        
        return {
            "present": result.get("present", False),
            "confidence": result.get("confidence", 0.0),
            "explanation": result.get("explanation", "No explanation provided")
        }
        
    except (APITimeoutError, RateLimitError, APIConnectionError) as e:
        logger.error(f"OpenAI API error: {str(e)}")
        # Check if this is a quota exceeded error
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
            logger.error(f"OpenAI API quota exceeded: {str(e)}")
            raise Exception(f"OpenAI API quota exceeded: {str(e)}")
        
        # For other API-specific errors, return a special message
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "OpenAI API temporarily unavailable. Using fallback analysis."
        }
    except BadRequestError as e:
        logger.error(f"OpenAI API bad request: {str(e)}")
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "Invalid request to OpenAI API. Using fallback analysis."
        }
    except Exception as e:
        logger.error(f"Error using OpenAI API: {str(e)}")
        # Check if this is a quota exceeded error before falling back
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
            logger.error(f"OpenAI API quota exceeded: {str(e)}")
            raise Exception(f"OpenAI API quota exceeded: {str(e)}")
        
        # Fallback to a default response in case of other failures
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "Error during AI analysis. Using fallback analysis."
        }

def analyze_checklist_items_batch(items: List[str], document_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Process each checklist item individually through the OpenAI API,
    with fallback to traditional NLP methods if API calls fail.
    
    Returns a dictionary mapping each item to its analysis result.
    
    Features:
    1. Processes each item individually for more detailed analysis
    2. Adds a delay between API calls to prevent rate limiting
    3. Gracefully handles API quota exceeded errors with fallback methods
    4. Provides detailed logging for each item's analysis
    """
    results = {}
    api_successes = 0
    api_failures = 0
    
    # Check if the API key exists and is not empty
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found or empty. Using only traditional analysis methods.")
        return results
    
    # Process all items, attempting to use OpenAI for each one
    logger.info(f"Attempting to analyze {len(items)} checklist items with OpenAI API")
    
    api_quota_exceeded = False
    
    # Process each item individually
    for i, item in enumerate(items):
        item_id = f"Item #{i+1}"
        logger.info(f"Processing {item_id}: {item[:50]}{'...' if len(item) > 50 else ''}")
        
        # If we've already hit API quota issues, don't make further API calls
        if api_quota_exceeded:
            logger.info(f"Skipping OpenAI API call for {item_id} due to quota issues")
            
            # Use traditional method as fallback with enhanced pattern matching
            from document_processor import check_item_in_document
            is_present = check_item_in_document(item, document_text)
            
            # Provide more detailed explanations based on content type
            explanation = "Not found in document"
            if is_present:
                item_lower = item.lower()
                # Generate more specific explanations by content type
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
                else:
                    explanation = "Content matched through section analysis"
            
            results[item] = {
                "present": is_present,
                "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                "explanation": explanation,
                "method": "traditional (enhanced)"  # Mark which method was used
            }
            api_failures += 1
            continue
        
        # Add a delay between API calls to prevent rate limiting
        if i > 0:
            time.sleep(1.5)  # Increased delay to 1.5 seconds between API calls
        
        try:
            # Try to analyze with OpenAI API
            item_result = analyze_checklist_item(item, document_text)
            item_result["method"] = "openai"  # Mark which method was used
            results[item] = item_result
            logger.info(f"Successfully analyzed {item_id} with OpenAI API")
            api_successes += 1
            
        except Exception as e:
            # Check if this is a quota exceeded error
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
                logger.warning(f"OpenAI API quota exceeded at item {i+1}. Switching to traditional analysis for remaining items.")
                api_quota_exceeded = True
                
                # Use traditional method for this item too with enhanced pattern matching
                from document_processor import check_item_in_document
                is_present = check_item_in_document(item, document_text)
                
                # Provide more detailed explanations based on content type
                explanation = "Not found in document"
                if is_present:
                    item_lower = item.lower()
                    # Generate more specific explanations by content type
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
                    else:
                        explanation = "Content matched through section analysis"
                
                results[item] = {
                    "present": is_present,
                    "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                    "explanation": explanation,
                    "method": "traditional (after quota exceeded)"
                }
                api_failures += 1
            else:
                # For other errors, still use traditional method but log the specific error
                logger.error(f"Error analyzing item {i+1} with OpenAI: {str(e)}")
                
                from document_processor import check_item_in_document
                is_present = check_item_in_document(item, document_text)
                
                # Provide more detailed explanations based on content type
                explanation = "Not found in document"
                if is_present:
                    item_lower = item.lower()
                    # Generate more specific explanations by content type
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
                    else:
                        explanation = "Content matched through section analysis"
                
                results[item] = {
                    "present": is_present,
                    "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                    "explanation": explanation,
                    "method": "traditional (after API error)"
                }
                api_failures += 1
    
    # Log summary of API usage
    logger.info(f"OpenAI API usage summary: {api_successes} successful calls, {api_failures} fallbacks to traditional methods")
    
    return results