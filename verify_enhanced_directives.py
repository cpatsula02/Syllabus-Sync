#!/usr/bin/env python3
"""
Enhanced verification script that checks for both the triple-checking process
and the anti-pattern matching directives in the system prompt.
"""

import re
import sys

def check_for_enhanced_features():
    """Check for enhanced features in api_analysis.py"""
    try:
        with open('api_analysis.py', 'r') as f:
            content = f.read()
        
        # Check for triple-checking implementation
        triple_check_pattern = r"THREE-PASS ANALYSIS REQUIREMENT[\s\S]+?FIRST PASS[\s\S]+?SECOND PASS[\s\S]+?THIRD PASS"
        triple_match = re.search(triple_check_pattern, content)
        
        # Check for anti-pattern matching directives
        anti_pattern_match_pattern = r"do not rely on exact keyword matches|never assume presence based on headers alone|analyze the actual CONTENT for compliance"
        anti_pattern_match = re.search(anti_pattern_match_pattern, content, re.IGNORECASE)
        
        if triple_match:
            print("✅ Triple-checking implementation found!")
        else:
            print("❌ Triple-checking implementation NOT found")
            
        if anti_pattern_match:
            print("✅ Anti-pattern matching directives found!")
            
            # Count the number of distinct anti-pattern matching directives
            anti_pattern_directives = [
                "do not rely on exact keyword matches",
                "never assume presence based on headers alone",
                "analyze the actual CONTENT for compliance",
                "evaluate whether the substance/meaning of each checklist item is present",
                "verify that the content substantially fulfills the requirement",
                "focus on compliance with the requirement's purpose"
            ]
            
            count = 0
            for directive in anti_pattern_directives:
                if re.search(directive, content, re.IGNORECASE):
                    count += 1
                    print(f"  - Found directive: '{directive}'")
            
            print(f"  Total anti-pattern matching directives found: {count}/{len(anti_pattern_directives)}")
        else:
            print("❌ Anti-pattern matching directives NOT found")
            
        # Examine the triple_checked field implementation
        triple_checked_field_pattern = r"[\"']triple_checked[\"']: True"
        triple_checked_field = re.search(triple_checked_field_pattern, content)
        
        if triple_checked_field:
            print("✅ triple_checked field implementation found!")
        else:
            print("❌ triple_checked field implementation NOT found")
        
        return triple_match is not None and anti_pattern_match is not None and triple_checked_field is not None
    
    except Exception as e:
        print(f"Error checking implementation: {e}")
        return False

if __name__ == "__main__":
    print("Verifying enhanced implementation...")
    success = check_for_enhanced_features()
    
    if success:
        print("\n✅ All enhanced features have been successfully implemented!")
        sys.exit(0)
    else:
        print("\n❌ Not all enhanced features were found. Please check the implementation.")
        sys.exit(1)