#!/usr/bin/env python3
"""
Quick verification of triple-checking implementation
"""

import os
import sys
import re
import json

def check_prompt_for_triple_checking():
    """Check api_analysis.py for triple-checking implementation"""
    try:
        with open('api_analysis.py', 'r') as f:
            content = f.read()
        
        # Look for the triple checking pattern
        triple_check_pattern = r"THREE-PASS ANALYSIS REQUIREMENT[\s\S]+?FIRST PASS[\s\S]+?SECOND PASS[\s\S]+?THIRD PASS"
        match = re.search(triple_check_pattern, content)
        
        if match:
            print("✅ Triple-checking implementation found in api_analysis.py!")
            print("Excerpt:")
            excerpt = match.group(0)[:300] + "..." if len(match.group(0)) > 300 else match.group(0)
            print(excerpt)
        else:
            print("❌ Triple-checking implementation NOT found in api_analysis.py")
        
        # Check API documentation
        with open('API_DOCUMENTATION.md', 'r') as f:
            doc_content = f.read()
        
        doc_pattern = r"triple-checking process|three passes|First pass.*Second pass.*Third pass"
        doc_match = re.search(doc_pattern, doc_content, re.IGNORECASE)
        
        if doc_match:
            print("\n✅ Triple-checking documentation found in API_DOCUMENTATION.md!")
        else:
            print("\n❌ Triple-checking documentation NOT found in API_DOCUMENTATION.md")
        
        return True
    except Exception as e:
        print(f"Error checking implementation: {e}")
        return False

if __name__ == "__main__":
    print("Verifying triple-checking implementation...")
    check_prompt_for_triple_checking()