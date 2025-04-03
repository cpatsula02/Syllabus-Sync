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
    max_text_length = 2000  # Reduced from 4000 to prevent timeout
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
            max_tokens=150,   # Limit response size to prevent long processing times
            timeout=30        # 30 second timeout to prevent hanging
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
        # For API-specific errors, return a special message
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
        # Fallback to a default response in case of failure
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
    """
    results = {}
    
    # Limit the number of OpenAI API calls to prevent timeouts
    MAX_API_CALLS = 5
    
    # Only analyze items with a meaningful length to save API calls
    filtered_items = [item for item in items if len(item) > 10]
    
    # If too many items, prioritize a subset (first N items)
    api_items = filtered_items[:MAX_API_CALLS] if len(filtered_items) > MAX_API_CALLS else filtered_items
    
    logger.info(f"Analyzing {len(api_items)} items with OpenAI API (out of {len(items)} total items)")
    
    # Process the selected items with OpenAI
    for i, item in enumerate(api_items):
        # Add a small delay between API calls to prevent rate limiting
        if i > 0:
            time.sleep(0.5)
            
        results[item] = analyze_checklist_item(item, document_text)
    
    # For the remaining items (if we limited API calls), use a fallback method
    # This will be handled by the process_documents function
    
    return results