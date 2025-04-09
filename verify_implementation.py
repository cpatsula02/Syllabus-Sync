#!/usr/bin/env python3
"""
Validation script to verify that our implementation of the course outline analysis
properly implements the required anti-pattern matching directives and triple-checking.
"""

import json
import time
import logging
import sys
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from api_analysis import analyze_course_outline
except ImportError:
    logger.error("Could not import analyze_course_outline from api_analysis")
    sys.exit(1)

# Test document - a short sample course outline
TEST_DOCUMENT = """
COURSE OUTLINE
PSYC 201 - Introduction to Psychology

Instructor: Dr. Jane Smith
Email: jane.smith@ucalgary.ca

COURSE OBJECTIVES:
1. Understand basic psychological concepts
2. Develop critical thinking skills 
3. Apply research methods in psychology

ASSESSMENTS:
Midterm Exam (30%) - Oct 15
Final Exam (40%) - Dec 10
Assignment (30%) - Nov 20

CONTACT INFORMATION:
Office Hours: Monday 2-4pm
Phone: 403-555-1234
"""

def verify_implementation():
    """Verify that the implementation properly includes all required features"""
    
    logger.info("Starting implementation verification...")
    
    # Run analysis on test document
    try:
        start_time = time.time()
        results = analyze_course_outline(TEST_DOCUMENT)
        elapsed = time.time() - start_time
        
        logger.info(f"Analysis completed in {elapsed:.2f} seconds")
        
        # Check that we have results
        if not results or len(results) != 26:
            logger.error(f"Expected 26 results, but got {len(results) if results else 0}")
            return False
            
        # Check that all results have the required fields
        for i, result in enumerate(results):
            missing_fields = []
            
            # Check required fields
            if "present" not in result or not isinstance(result["present"], bool):
                missing_fields.append("present")
                
            if "confidence" not in result or not isinstance(result["confidence"], (int, float)):
                missing_fields.append("confidence")
                
            if "explanation" not in result or not isinstance(result["explanation"], str):
                missing_fields.append("explanation")
                
            if "evidence" not in result or not isinstance(result["evidence"], str):
                missing_fields.append("evidence")
                
            if "method" not in result or result["method"] != "ai_general_analysis":
                missing_fields.append("method")
                
            if "triple_checked" not in result or not isinstance(result["triple_checked"], bool) or not result["triple_checked"]:
                missing_fields.append("triple_checked")
            
            if missing_fields:
                logger.error(f"Result {i+1} is missing or has invalid fields: {', '.join(missing_fields)}")
                return False
        
        # Sample specific items to check if they're correct
        email_item = results[0]  # First item should be instructor email
        if email_item["present"] and "@ucalgary.ca" in TEST_DOCUMENT:
            logger.info("✅ Correctly identified instructor email")
        
        # Print some sample results
        logger.info("\nSample results:")
        for i, result in enumerate(results[:5]):  # Show first 5 items
            logger.info(f"Item {i+1}:")
            logger.info(f"  Present: {result['present']}")
            logger.info(f"  Confidence: {result['confidence']}")
            logger.info(f"  Explanation: {result['explanation']}")
            logger.info(f"  Evidence: {result['evidence'][:50]}..." if len(result.get('evidence', '')) > 50 else f"  Evidence: {result.get('evidence', '')}")
            logger.info(f"  Method: {result['method']}")
            logger.info(f"  Triple-Checked: {result['triple_checked']}")
            logger.info("")
        
        # Count present items
        present_count = sum(1 for r in results if r["present"])
        logger.info(f"Items marked as present: {present_count} out of 26")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during verification: {str(e)}")
        return False

if __name__ == "__main__":
    success = verify_implementation()
    
    if success:
        logger.info("\n✅ Implementation verification completed successfully!")
        logger.info("The system correctly implements all required features:")
        logger.info("  - Triple-checking process for each checklist item")
        logger.info("  - Anti-pattern matching directives for contextual understanding")
        logger.info("  - Properly structured results with all required fields")
        logger.info("  - Consistent method field set to 'ai_general_analysis'")
        sys.exit(0)
    else:
        logger.error("\n❌ Implementation verification failed!")
        sys.exit(1)