#!/usr/bin/env python3
"""
Test script to verify OpenAI API integration with proper timeout handling
and no pattern matching fallbacks.
"""

import os
import time
import sys
import socket
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check OpenAI API key
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    logger.error("No OpenAI API key found in environment variables")
    sys.exit(1)

if not openai_api_key.startswith("sk-"):
    logger.error("Invalid OpenAI API key format (should start with 'sk-')")
    sys.exit(1)

logger.info("OpenAI API key is present with valid format")

try:
    import openai
    from openai import OpenAI
    logger.info("OpenAI library is installed")
except ImportError:
    logger.error("OpenAI library is not installed")
    sys.exit(1)

# Test function
def test_openai_api_with_timeout() -> Dict[str, Any]:
    """
    Test OpenAI API with proper timeout handling.
    Uses the exact same approach as our application.
    """
    try:
        # Initialize client
        client = OpenAI(api_key=openai_api_key)
        
        # Create a short prompt for testing that includes "json" for json_object response format
        prompt = "Analyze this checklist item for a university course outline and provide the result as JSON: 'Instructor email is included and contains ucalgary.ca domain'"
        
        # Store original socket timeout to restore later
        original_timeout = socket.getdefaulttimeout()
        
        try:
            # Set socket timeout to prevent hanging connections
            socket.setdefaulttimeout(40)
            logger.info(f"Set socket timeout to 40 seconds")
            
            logger.info("Making OpenAI API request with 35 second timeout...")
            start_time = time.time()
            
            # Make the API request
            response = client.chat.completions.create(
                model="gpt-3.5-turbo-0125",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=200,
                timeout=35  # API request timeout
            )
            
            end_time = time.time()
            
            # Get response content
            response_content = response.choices[0].message.content
            
            return {
                "success": True,
                "elapsed_time": end_time - start_time,
                "response": response_content[:100] + "..." if len(response_content) > 100 else response_content
            }
            
        except Exception as e:
            logger.error(f"API error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            # Always reset socket timeout
            socket.setdefaulttimeout(original_timeout)
            logger.info(f"Reset socket timeout to original value")
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    logger.info("Testing OpenAI API integration...")
    result = test_openai_api_with_timeout()
    
    if result["success"]:
        logger.info(f"SUCCESS: API call completed in {result['elapsed_time']:.2f} seconds")
        logger.info(f"Response: {result['response']}")
        logger.info("The OpenAI API integration is working correctly")
    else:
        logger.error(f"FAILED: {result['error']}")
        logger.error("The OpenAI API integration is NOT working correctly")
        
    sys.exit(0 if result["success"] else 1)