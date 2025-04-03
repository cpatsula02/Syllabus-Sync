import os
import json
import logging
from typing import List, Dict, Any

# Import OpenAI
from openai import OpenAI

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
    try:
        # Prepare the prompt for OpenAI
        prompt = f"""
        Task: Determine if the checklist item is present in the document text.
        
        Checklist item: "{item}"
        
        Document text excerpt (truncated for brevity): "{document_text[:4000]}..."
        
        Instructions:
        1. Analyze whether the concept or requirement in the checklist item appears in the document.
        2. The match doesn't need to be exact wording - focus on the meaning and requirements.
        3. Respond with JSON in this format: {{"present": true/false, "confidence": 0.0-1.0, "explanation": "brief explanation"}}
        4. Where "present" is true/false, "confidence" is a score between 0 and 1, and "explanation" briefly explains your reasoning.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            messages=[
                {"role": "system", "content": "You are an assistant that specializes in document analysis for educational institutions."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2  # Lower temperature for more consistent results
        )
        
        # Extract and parse the response
        result = json.loads(response.choices[0].message.content)
        logger.info(f"OpenAI analysis complete for item: {item[:30]}...")
        
        return {
            "present": result.get("present", False),
            "confidence": result.get("confidence", 0.0),
            "explanation": result.get("explanation", "No explanation provided")
        }
        
    except Exception as e:
        logger.error(f"Error using OpenAI API: {str(e)}")
        # Fallback to a default response in case of failure
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": f"Error analyzing with AI: {str(e)}"
        }

def analyze_checklist_items_batch(items: List[str], document_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Process multiple checklist items against a document text using OpenAI.
    Returns a dictionary mapping each item to its analysis result.
    """
    results = {}
    
    for item in items:
        results[item] = analyze_checklist_item(item, document_text)
        
    return results