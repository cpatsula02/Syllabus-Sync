#!/usr/bin/env python3
"""
Test script to verify the triple-checking process is working correctly
by analyzing a small sample document.
"""

import requests
import json
import time

def test_triple_checker():
    """Test the triple-checking process with a simple document"""
    print("Testing triple-checker process...")
    
    # Sample document with enough text to test proper triple-checking
    sample_doc = """
    COURSE OUTLINE
    PSYC 201 - Introduction to Psychology
    
    Instructor: Dr. John Smith
    Email: john.smith@ucalgary.ca
    
    Course Description:
    This course provides an introduction to the field of psychology, including major theories,
    research methods, and applications in various domains of human behavior and cognition.
    
    Learning Objectives:
    1. Understand the basic psychological theories and concepts.
    2. Apply critical thinking to psychological research methods and findings.
    3. Analyze real-world situations from multiple psychological perspectives.
    4. Develop communication skills in discussing psychological phenomena.
    
    Grade Distribution:
    - Midterm Exam 1: 25% (October 10, 2025)
    - Midterm Exam 2: 25% (November 14, 2025)
    - Final Paper: 30% (December 5, 2025)
    - Weekly Quizzes: 20% (Throughout the term)
    
    Grading Scale:
    A+ (96-100%)
    A (90-95%)
    A- (85-89%)
    B+ (80-84%)
    B (75-79%)
    B- (70-74%)
    C+ (67-69%)
    C (64-66%)
    C- (60-63%)
    D+ (55-59%)
    D (50-54%)
    F (<50%)
    """
    
    start_time = time.time()
    
    # Make the API request
    response = requests.post(
        'http://localhost:5000/api/analyze-course-outline',
        json={'document_text': sample_doc},
        timeout=300  # 5 minute timeout
    )
    
    elapsed = time.time() - start_time
    print(f"Got response in {elapsed:.2f} seconds")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success! Got {len(data)} items")
        print(f"Items marked as present: {sum(1 for item in data if item.get('present'))}")
        
        # Write results to file for inspection
        with open('triple_checker_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Response saved to triple_checker_response.json")
        
        # Check for evidence of triple-checking in explanations
        # (Look for comprehensive analysis in item explanations)
        for i, item in enumerate(data[:5]):  # Check first 5 items
            print(f"Item {i+1}: {item.get('explanation')[:50]}... (Present: {item.get('present')})")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_triple_checker()