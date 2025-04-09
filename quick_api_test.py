#!/usr/bin/env python3
"""
Quick test client for the course outline compliance API
with a shorter timeout to quickly verify functionality
"""

import requests
import json
import time

# Very minimal sample course outline for testing - using even smaller sample
SAMPLE_OUTLINE = """
INSTRUCTOR EMAIL: john.smith@ucalgary.ca
"""

def quick_test_api():
    """Quick test of the API endpoint"""
    url = "http://localhost:5000/api/analyze-course-outline"
    payload = {"document_text": SAMPLE_OUTLINE}
    headers = {"Content-Type": "application/json"}
    
    try:
        print(f"Testing API endpoint with quick test...")
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=30)  # shorter timeout
        elapsed = time.time() - start_time
        print(f"Request completed in {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            
            # Basic structure validation
            if not isinstance(data, list):
                print(f"ERROR: Expected list response, got {type(data)}")
                return
            
            print(f"Success! Response contains {len(data)} items")
            
            # Count by method type
            method_counts = {}
            for item in data:
                method = item.get("method", "unknown")
                method_counts[method] = method_counts.get(method, 0) + 1
            
            print("Method counts in response:")
            for method, count in method_counts.items():
                print(f"  - {method}: {count} items")
            
            # Check for pattern_matching methods - which should NOT exist
            pattern_methods = sum(1 for item in data if "pattern" in item.get("method", "").lower())
            if pattern_methods > 0:
                print(f"ERROR: Found {pattern_methods} items using pattern matching!")
            else:
                print("SUCCESS: No pattern matching methods used in the response")
                
        else:
            print(f"ERROR: Request failed with status code {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    quick_test_api()