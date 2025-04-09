#!/usr/bin/env python3
"""
Test script for the course outline analysis API.

This script sends a sample course outline to the API and validates 
the response format according to the requirements.
"""

import json
import requests
from typing import Dict, Any, List
import sys

# Sample minimal course outline for testing
SAMPLE_OUTLINE = """
COURSE OUTLINE
PSYC 201 - Introduction to Psychology

Instructor: Dr. John Smith
Email: john.smith@ucalgary.ca
Office: EDT 123

Learning Objectives:
1. Understand psychology concepts

Required Textbook: Psychology Basics

Evaluation:
Midterm: 30%
Final: 70%
"""

def validate_response(response_data: List[Dict[str, Any]]) -> bool:
    """
    Validate the API response against the requirements.
    
    Args:
        response_data: The response data from the API
        
    Returns:
        True if valid, False otherwise
    """
    # Check if we have exactly 26 items
    if len(response_data) != 26:
        print(f"ERROR: Expected 26 items, got {len(response_data)}")
        return False
    
    # Check each item for required fields
    for i, item in enumerate(response_data):
        # Check required fields
        required_fields = ["present", "confidence", "explanation", "evidence", "method"]
        for field in required_fields:
            if field not in item:
                print(f"ERROR: Item {i+1} missing required field '{field}'")
                return False
        
        # Check field types
        if not isinstance(item["present"], bool):
            print(f"ERROR: Item {i+1} 'present' field is not a boolean: {type(item['present'])}")
            return False
            
        if not isinstance(item["confidence"], (int, float)) or item["confidence"] < 0 or item["confidence"] > 1:
            print(f"ERROR: Item {i+1} 'confidence' field is not a float between 0-1: {item['confidence']}")
            return False
            
        if not isinstance(item["explanation"], str):
            print(f"ERROR: Item {i+1} 'explanation' field is not a string: {type(item['explanation'])}")
            return False
            
        if len(item["explanation"]) > 150:
            print(f"ERROR: Item {i+1} 'explanation' field exceeds 150 chars: {len(item['explanation'])}")
            return False
            
        if not isinstance(item["evidence"], str):
            print(f"ERROR: Item {i+1} 'evidence' field is not a string: {type(item['evidence'])}")
            return False
            
        if not isinstance(item["method"], str):
            print(f"ERROR: Item {i+1} 'method' field is not a string: {type(item['method'])}")
            return False
            
        if item["method"] != "ai_general_analysis":
            print(f"ERROR: Item {i+1} 'method' field is not 'ai_general_analysis': {item['method']}")
            return False
    
    # All checks passed
    return True

def test_api(url: str = "http://localhost:5000/api/analyze-course-outline") -> None:
    """
    Test the API by sending a sample outline and validating the response.
    
    Args:
        url: The API endpoint URL
    """
    print(f"Testing API endpoint: {url}")
    print("Sending sample course outline...")
    
    payload = {"document_text": SAMPLE_OUTLINE}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        print(f"Response status: {response.status_code}")
        
        # Parse response JSON
        data = response.json()
        
        # Validate response format
        if validate_response(data):
            print("SUCCESS: Response format is valid")
            print(f"Response contains {len(data)} items")
            
            # Count present/missing items
            present_count = sum(1 for item in data if item["present"])
            missing_count = len(data) - present_count
            
            print(f"Present items: {present_count}")
            print(f"Missing items: {missing_count}")
            
            # Sample response data
            print("\nSample response items:")
            for i in range(min(3, len(data))):
                print(f"Item {i+1}:")
                print(f"  Present: {data[i]['present']}")
                print(f"  Confidence: {data[i]['confidence']}")
                print(f"  Explanation: {data[i]['explanation']}")
                print(f"  Evidence: {data[i]['evidence'][:50]}..." if data[i]['evidence'] else "  Evidence: None")
                print(f"  Method: {data[i]['method']}")
                print()
        else:
            print("ERROR: Response format validation failed")
            
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON response: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")

if __name__ == "__main__":
    # Allow specifying a custom URL
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000/api/analyze-course-outline"
    test_api(api_url)