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
    Process multiple checklist items against a document text using OpenAI.
    Returns a dictionary mapping each item to its analysis result.
    
    To prevent rate limiting and timeouts:
    1. Adds a small delay between API calls
    2. Limits the number of items processed with OpenAI
    3. Falls back to traditional NLP for the rest
    4. Gracefully handles API quota exceeded errors
    """
    results = {}
    
    # Check if the API key exists and is not empty
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found or empty. Using only traditional analysis methods.")
        return results
    
    # Limit the number of OpenAI API calls to prevent timeouts and quota issues
    MAX_API_CALLS = 3  # Reduced to 3 to minimize quota usage
    
    # Only analyze items with a meaningful length to save API calls
    filtered_items = [item for item in items if len(item) > 10]
    
    # If too many items, prioritize a subset (first N items)
    api_items = filtered_items[:MAX_API_CALLS] if len(filtered_items) > MAX_API_CALLS else filtered_items
    
    logger.info(f"Analyzing {len(api_items)} items with OpenAI API (out of {len(items)} total items)")
    
    api_quota_exceeded = False
    
    # Process the selected items with OpenAI
    for i, item in enumerate(api_items):
        # If we've already hit API quota issues, don't make further calls
        if api_quota_exceeded:
            logger.info(f"Skipping OpenAI API call for item {i+1} due to quota issues")
            continue
        
        # Add a small delay between API calls to prevent rate limiting
        if i > 0:
            time.sleep(1.0)  # Increased delay to 1 second
        
        try:
            results[item] = analyze_checklist_item(item, document_text)
        except Exception as e:
            # Check if this is a quota exceeded error
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
                logger.warning("OpenAI API quota exceeded. Switching to traditional analysis for remaining items.")
                api_quota_exceeded = True
            else:
                logger.error(f"Error analyzing item with OpenAI: {str(e)}")
    
    # For the remaining items (if we limited API calls), use a fallback method
    # This will be handled by the process_documents function
    
    return results