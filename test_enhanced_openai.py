#!/usr/bin/env python3
"""
Test Enhanced OpenAI Integration

This script tests the enhanced OpenAI integration with retry mechanism
to ensure it's more resilient to timeouts and API errors.
"""

import logging
import os
import time
import sys
from openai_helper import analyze_checklist_item_with_retry

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test document text
TEST_DOCUMENT = """
University of Calgary
ENTI 674 L01-L02 - Technology and Innovation Strategy
Fall 2023

COURSE INFORMATION
Instructor Email: mohammad.keyhani@ucalgary.ca
Office Hours: By appointment

COURSE DESCRIPTION
This course covers the critical role of technology and innovation in business strategy.

COURSE MATERIALS
Textbook: "Strategic Management of Technology and Innovation" (Required)

GRADE DISTRIBUTION
Component | Weight
-----------------------
Case Studies     | 30%
Participation    | 10% 
Midterm Exam     | 25%
Final Project    | 35%

LATE ASSIGNMENTS POLICY
Late assignments will be penalized 10% per day.

ACADEMIC INTEGRITY
Students must comply with university regulations regarding academic integrity.

STUDENT ACCOMMODATIONS
The university provides accommodations for students with disabilities.

COURSE SCHEDULE
Week 1: Introduction to Technology Strategy
Week 2: Innovation Fundamentals
Week 3: Technology Acquisition and Development
[...]
Week 13: Final Presentations

TECHNOLOGY RESOURCES
Students will need access to basic spreadsheet software.
For web research, students are encouraged to use the university library resources.
Websites: ucalgary.ca/library, innovation.ca

EMERGENCY EVACUATION
In case of emergency, proceed to the nearest exit and assemble at designated gathering points.
"""

# Test checklist items
TEST_CHECKLIST_ITEMS = [
    "Does the outline include the instructor's email? An acceptable email must end with ucalgary.ca.",
    "Does the outline include office hours or a method for scheduling appointments with the instructor?",
    "Does the outline contain a grade distribution table with assessment weights?",
    "Does the outline contain a late policy for assignments?",
    "Does the outline mention academic integrity?",
    "Does the outline include a course schedule with weekly topics?",
    "Does the outline reference any technology resources, tools, or websites?",
    "Does the outline include emergency evacuation procedures?",
    "Does the outline specify a textbook or learning resources?"
]

def main():
    """Main test function"""
    # Check if we have the OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("No OpenAI API key found in environment. Please set OPENAI_API_KEY.")
        return 1
    
    logger.info("Testing enhanced OpenAI integration with retry mechanism...")
    
    # Process each test item
    results = []
    start_time = time.time()
    
    for i, item in enumerate(TEST_CHECKLIST_ITEMS):
        logger.info(f"Processing item {i+1}/{len(TEST_CHECKLIST_ITEMS)}: {item[:50]}...")
        
        try:
            # Use our new retry-based approach
            result = analyze_checklist_item_with_retry(
                item, 
                TEST_DOCUMENT, 
                max_attempts=3
            )
            
            # Add item info to result
            result["item_number"] = i + 1
            result["item_text"] = item
            
            results.append(result)
            logger.info(f"✓ Result: {'PRESENT' if result.get('present') else 'NOT PRESENT'} "
                       f"(confidence: {result.get('confidence', 0):.2f})")
            
        except Exception as e:
            logger.error(f"Error processing item {i+1}: {str(e)}")
            results.append({
                "item_number": i + 1,
                "item_text": item,
                "present": False,
                "confidence": 0,
                "explanation": f"Error: {str(e)}",
                "evidence": "",
                "method": "error"
            })
    
    # Calculate timing
    end_time = time.time()
    total_time = end_time - start_time
    avg_time = total_time / len(TEST_CHECKLIST_ITEMS)
    
    # Print summary
    logger.info("=" * 80)
    logger.info(f"Test completed in {total_time:.2f} seconds (avg {avg_time:.2f}s per item)")
    logger.info(f"Total items: {len(TEST_CHECKLIST_ITEMS)}")
    
    present_count = sum(1 for r in results if r.get('present', False))
    logger.info(f"Items found PRESENT: {present_count}/{len(TEST_CHECKLIST_ITEMS)}")
    
    # Print detailed results
    logger.info("=" * 80)
    logger.info("DETAILED RESULTS:")
    for result in results:
        status = "✓ PRESENT" if result.get('present', False) else "✗ NOT PRESENT"
        confidence = result.get('confidence', 0)
        item_num = result.get('item_number', 0)
        item_text = result.get('item_text', '')
        explanation = result.get('explanation', '')
        
        logger.info(f"Item #{item_num}: {status} (confidence: {confidence:.2f})")
        logger.info(f"  Question: {item_text}")
        logger.info(f"  Explanation: {explanation}")
        logger.info("-" * 40)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())