#!/usr/bin/env python3
"""
Process Checklist Script

This script processes the specific checklist provided in the attached_assets directory.
It converts the checklist to the required output format for the university course outline evaluation.
"""

import os
import re
import sys
from typing import Dict, List, Tuple

def parse_checklist_items(input_text: str) -> List[str]:
    """
    Parse checklist items from the provided text.
    
    Args:
        input_text: The text containing checklist items
        
    Returns:
        List of parsed checklist items
    """
    # Extract numbered items from the text
    pattern = r'(\d+)\.\s+(.*?)(?=\n\d+\.|$)'
    matches = re.findall(pattern, input_text, re.DOTALL)
    
    checklist_items = []
    for match in matches:
        number, item_text = match
        # Clean up the item text
        item_text = re.sub(r'\s+', ' ', item_text).strip()
        checklist_items.append(item_text)
    
    return checklist_items

def analyze_item(item: str, outline_text: str) -> Tuple[str, str]:
    """
    Simple analysis of whether an item is present in the outline.
    
    Args:
        item: The checklist item to analyze
        outline_text: The outline text to search in
        
    Returns:
        Tuple of (status, justification)
    """
    # This is a placeholder. In a real scenario, we would use the 
    # more sophisticated analysis from the application.
    item_lower = item.lower()
    outline_lower = outline_text.lower()
    
    # Simple keyword matching for demonstration
    keywords = [word for word in re.findall(r'\b\w+\b', item_lower) 
                if len(word) > 3 and word not in ['this', 'that', 'with', 'from', 'have', 'does', 'each']]
    
    # Count matches
    match_count = sum(1 for keyword in keywords if keyword in outline_lower)
    match_ratio = match_count / len(keywords) if keywords else 0
    
    # Determine status based on match ratio
    if match_ratio > 0.6:
        status = "Yes"
        justification = f"Found relevant content in the outline ({match_ratio:.2f} match ratio)."
    else:
        status = "No"
        justification = f"Could not find sufficient relevant content in the outline ({match_ratio:.2f} match ratio)."
    
    # Special cases for N/A
    if any(term in item_lower for term in ["if applicable", "if present", "if mentioned"]):
        if match_ratio < 0.3:
            status = "N/A"
            justification = "This requirement does not appear to be applicable to this course."
    
    return status, justification

def format_output(checklist_items: List[str], outline_text: str) -> str:
    """
    Format the output according to the specified format.
    
    Args:
        checklist_items: List of checklist items
        outline_text: The outline text for analysis
        
    Returns:
        Formatted output string
    """
    output = []
    
    for idx, item in enumerate(checklist_items, 1):
        status, justification = analyze_item(item, outline_text)
        
        output.append(f"**Checklist Item #{idx}:** {item}")
        output.append(f"**Status:** {status}")
        output.append(f"**Justification:** {justification}")
        output.append("")  # Empty line for readability
    
    return "\n".join(output)

def main():
    """Main function to process the checklist."""
    # Define paths to the checklist and course outline
    checklist_path = "attached_assets/Pasted-You-are-reviewing-a-university-course-outline-to-evaluate-whether-it-meets-institutional-standards-b-1744082496300.txt"
    
    # Check if the files exist
    if not os.path.exists(checklist_path):
        print(f"Error: Checklist file not found: {checklist_path}")
        sys.exit(1)
    
    # Read the checklist
    with open(checklist_path, 'r') as f:
        checklist_text = f.read()
    
    # Parse the checklist items
    checklist_items = parse_checklist_items(checklist_text)
    
    if not checklist_items:
        print("Error: No checklist items found in the provided file.")
        sys.exit(1)
    
    # Output the checklist items in the required format
    print(f"Found {len(checklist_items)} checklist items.")
    for idx, item in enumerate(checklist_items, 1):
        print(f"{idx}. {item}")
    
    print("\nTo evaluate a course outline against this checklist, use the following command:")
    print("python evaluate_outline.py <path_to_course_outline>")

if __name__ == "__main__":
    main()