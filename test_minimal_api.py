#!/usr/bin/env python3
"""
Minimal test client for the course outline compliance API

This script sends a tiny sample course outline to the API and prints
the structure of the response to verify that it conforms to the required format.
"""

import requests
import json
from typing import Dict, Any
import time
import sys

# Very minimal sample course outline for testing
SAMPLE_OUTLINE = """
INSTRUCTOR EMAIL: john.smith@ucalgary.ca
COURSE OBJECTIVES: 1. Learn concepts
TEXTBOOK: Sample textbook
"""

def test_api(url: str = "http://localhost:5000/api/analyze-course-outline") -> None:
    """
    Test the API with a minimal document and print the response structure.
    
    Args:
        url: The API endpoint URL
    """
    print(f"Testing API endpoint: {url}")
    print("Sending minimal sample course outline...")
    
    payload = {"document_text": SAMPLE_OUTLINE}
    headers = {"Content-Type": "application/json"}
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        elapsed = time.time() - start_time
        print(f"Request completed in {elapsed:.2f} seconds")
        
        print(f"Response status: {response.status_code}")
        
        # Parse response data
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Check if we got expected number of items
                if not isinstance(data, list):
                    print(f"ERROR: Expected list response, got {type(data)}")
                    return
                
                print(f"Response contains {len(data)} items")
                
                # Count present/missing items
                present_count = sum(1 for item in data if item.get("present", False))
                missing_count = len(data) - present_count
                
                print(f"Present items: {present_count}")
                print(f"Missing items: {missing_count}")
                
                # Print field counts to verify structure
                field_counts = {}
                for field in ["present", "confidence", "explanation", "evidence", "method"]:
                    field_counts[field] = sum(1 for item in data if field in item)
                
                print("\nField presence statistics:")
                for field, count in field_counts.items():
                    print(f"  {field}: {count}/{len(data)} items ({count/len(data)*100:.1f}%)")
                
                # Verify "method" field content
                method_values = {}
                for item in data:
                    method = item.get("method", "")
                    if method in method_values:
                        method_values[method] += 1
                    else:
                        method_values[method] = 1
                
                print("\nValues for 'method' field:")
                for method, count in method_values.items():
                    print(f"  {method}: {count} items")
                
                # Print first few items as samples
                print("\nSample response items:")
                for i in range(min(3, len(data))):
                    print(f"Item {i+1}:")
                    item = data[i]
                    for key, value in item.items():
                        # Truncate long values for display
                        if isinstance(value, str) and len(value) > 50:
                            print(f"  {key}: {value[:50]}...")
                        else:
                            print(f"  {key}: {value}")
                    print()
                    
            except json.JSONDecodeError:
                print("ERROR: Response is not valid JSON")
                print(f"Raw response: {response.text[:500]}...")
        else:
            print(f"ERROR: Request failed with status code {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request exception: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")

if __name__ == "__main__":
    # Allow specifying a custom URL
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000/api/analyze-course-outline"
    test_api(api_url)