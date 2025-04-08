#!/usr/bin/env python3
"""
Extract Checklist Items

This script extracts the 25 checklist items from the provided text file
and outputs them in a clean numbered format.
"""

import re
import sys

def extract_checklist_items(file_path):
    """
    Extract checklist items from the specified file.
    
    Args:
        file_path: Path to the file containing checklist items
        
    Returns:
        List of extracted checklist items
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for the section with checklist items
        match = re.search(r'### Checklist Items:(.*?)###', content, re.DOTALL)
        if not match:
            # Try alternative pattern
            match = re.search(r'Checklist Items:(.*?)Output Format:', content, re.DOTALL)
        
        if not match:
            print("Error: Could not find checklist items section in the file.")
            return []
        
        checklist_section = match.group(1).strip()
        
        # Extract numbered items
        items = []
        lines = checklist_section.split('\n')
        for line in lines:
            # Look for numbered items (e.g., "1. Item text")
            match = re.match(r'^\s*(\d+)\.\s*(.*?)\s*$', line)
            if match:
                item_num = int(match.group(1))
                item_text = match.group(2).strip()
                items.append((item_num, item_text))
        
        # Sort by item number
        items.sort(key=lambda x: x[0])
        return items
    
    except Exception as e:
        print(f"Error extracting checklist items: {str(e)}")
        return []

def main():
    """Main function to extract and display checklist items."""
    # Define the file path
    file_path = "attached_assets/Pasted-You-are-reviewing-a-university-course-outline-to-evaluate-whether-it-meets-institutional-standards-b-1744082496300.txt"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    # Extract items
    items = extract_checklist_items(file_path)
    
    if not items:
        print("No checklist items found.")
        sys.exit(1)
    
    # Display items
    print(f"Found {len(items)} checklist items:\n")
    for num, text in items:
        print(f"{num}. {text}")

if __name__ == "__main__":
    main()