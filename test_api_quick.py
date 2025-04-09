#!/usr/bin/env python3
"""Quick test script to verify the API works correctly"""

import requests
import json
import time

def test_api():
    """Test the API with a simple document and write results to file"""
    print("Testing API...")
    start_time = time.time()
    
    response = requests.post(
        'http://localhost:5000/api/analyze-course-outline',
        json={'document_text': 'COURSE OUTLINE\nInstructor: Dr. Smith\nEmail: smith@ucalgary.ca'},
        timeout=300  # 5 minute timeout
    )
    
    elapsed = time.time() - start_time
    print(f"Got response in {elapsed:.2f} seconds")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success! Got {len(data)} items")
        print(f"Items marked as present: {sum(1 for item in data if item.get('present'))}")
        
        # Write results to file for inspection
        with open('api_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Response saved to api_response.json")
        
        # Validate format - simple checks
        if len(data) != 26:
            print(f"ERROR: Expected 26 items, got {len(data)}")
        
        # Check a few items for required fields
        for item in data[:3]:
            for field in ["present", "confidence", "explanation", "evidence", "method"]:
                if field not in item:
                    print(f"ERROR: Item missing required field '{field}'")
            
            if item.get("method") != "ai_general_analysis":
                print(f"ERROR: Method field is not 'ai_general_analysis', got: {item.get('method')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_api()