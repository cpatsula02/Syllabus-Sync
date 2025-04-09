"""
Test script to verify the loading and parsing of the enhanced_checklist.txt file
"""
import re
import os

def test_enhanced_checklist():
    print("Testing enhanced checklist loading and parsing...")
    
    # Load the enhanced checklist descriptions
    enhanced_checklist = []
    print(f"Starting to load enhanced checklist from: {os.path.abspath('enhanced_checklist.txt')}")
    try:
        with open('enhanced_checklist.txt', 'r') as file:
            content = file.read().strip()
            print(f"Read {len(content)} characters from enhanced_checklist.txt")
            enhanced_checklist = content.split('\n\n')
            print(f"Parsed {len(enhanced_checklist)} checklist items")
    except Exception as e:
        print(f"ERROR loading enhanced checklist: {str(e)}")
        return

    # Test the regex pattern
    print("\nTesting regex pattern on each item:")
    for i, item_desc in enumerate(enhanced_checklist):
        print(f"\nItem {i+1}:")
        print(f"Text: {item_desc[:50]}...")
        
        # Try original pattern
        match = re.match(r'^(\d+)\.\s+(.+?):', item_desc)
        if match:
            num = match.group(1)
            name = match.group(2)
            print(f"Original regex: Success! #{num} - {name}")
        else:
            print(f"Original regex: FAILED to match")
        
        # Try modified pattern
        match2 = re.match(r'^(\d+)\.\s+([^:]+):', item_desc)
        if match2:
            num = match2.group(1)
            name = match2.group(2)
            print(f"Modified regex: Success! #{num} - {name}")
            
            # Extract description - everything after the colon and first space
            description_start = item_desc.find(":", len(num) + 2) + 1
            if description_start > 0:
                description = item_desc[description_start:].strip()
                print(f"Description (first 50 chars): {description[:50]}...")
            else:
                print("Description: ERROR - No colon found")
        else:
            print(f"Modified regex: FAILED to match")

if __name__ == "__main__":
    test_enhanced_checklist()