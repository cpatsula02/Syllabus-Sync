#!/usr/bin/env python3
"""
Test script to verify that the app is getting to the results page
with the API key working correctly.
"""

import os
import sys
import requests
import logging
from urllib.parse import urljoin
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set base URL for the app (running locally)
BASE_URL = "http://0.0.0.0:5000"

def test_upload():
    """
    Test uploading a sample checklist and course outline to the app
    and verify it reaches the results page.
    """
    try:
        # Sample checklist content
        checklist_content = """
1. Instructor email is included and contains the domain "ucalgary.ca" (including subdomains like haskayne.ucalgary.ca).
2. Course objectives or learning outcomes are listed and structured, even if not labeled "objectives."
3. Readings, textbooks, or other materials are listed anywhere in the document.
        """
        
        # Get sample document path
        sample_doc_path = Path("attached_assets/W25%20ENTI%20674%20L01-L02%20-%20Course%20Outline%20-%20Mohammad%20Keyhani1.docx.pdf")
        
        if not sample_doc_path.exists():
            logger.error(f"Sample document not found at {sample_doc_path}")
            return False
        
        logger.info(f"Using sample document: {sample_doc_path}")
        
        # Prepare form data
        files = {
            'outline': open(sample_doc_path, 'rb')
        }
        data = {
            'checklist': checklist_content,
            'additional_context': "This is a test upload with only 3 checklist items for performance testing.",
            'api_attempts': '1'  # Only try once to speed up processing
        }
        
        # Add a shorter timeout
        url = urljoin(BASE_URL, "/")
        
        logger.info(f"Sending request to {url}")
        response = requests.post(url, files=files, data=data, timeout=60)
        
        # Log the response
        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response size: {len(response.text)} bytes")
        
        # Check if we got the results page
        is_success = response.status_code == 200 and "Analysis Results" in response.text
        
        if is_success:
            logger.info("SUCCESS: Got to the results page!")
            return True
        else:
            logger.error("FAILED: Did not get to the results page")
            # Log error details if available
            if "error" in response.text.lower():
                error_start = response.text.lower().find("error")
                error_text = response.text[error_start:error_start+100]
                logger.error(f"Error found in response: {error_text}...")
            return False
            
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        return False
    finally:
        # Close any open files
        for f in files.values():
            f.close()

if __name__ == "__main__":
    logger.info("Starting app upload test...")
    success = test_upload()
    logger.info(f"Test {'succeeded' if success else 'failed'}!")
    sys.exit(0 if success else 1)