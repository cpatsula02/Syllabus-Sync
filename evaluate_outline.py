#!/usr/bin/env python3
"""
Course Outline Evaluation Script

This script evaluates a university course outline against a checklist of required elements.
It uses the existing document processing functionality in the application to perform the evaluation.

Usage:
    python evaluate_outline.py <checklist_file_path> <outline_file_path>

Output:
    Evaluation results in the format specified by the checklist.
"""

import os
import sys
import logging
from typing import Dict, List, Any, Tuple
import re
from document_processor import extract_text, extract_checklist_items_strict
from openai_helper import analyze_checklist_items_batch, analyze_checklist_item

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_links(text: str) -> Tuple[List[str], List[str]]:
    """
    Validates links found in the provided text.
    Returns lists of valid and invalid links.
    """
    url_pattern = r"(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})"
    urls = re.findall(url_pattern, text)
    valid_links = []
    invalid_links = []

    for url in urls:
        try:
            import urllib.request
            urllib.request.urlopen(url)
            valid_links.append(url)
        except Exception as e:
            invalid_links.append(url)

    return valid_links, invalid_links

def process_and_evaluate(checklist_path: str, outline_path: str) -> Dict[str, Any]:
    """
    Process and evaluate a course outline against a checklist.
    
    Args:
        checklist_path: Path to the checklist file
        outline_path: Path to the course outline file
        
    Returns:
        Dictionary with evaluation results
    """
    try:
        # Validate file paths
        if not os.path.exists(checklist_path):
            raise FileNotFoundError(f"Checklist file not found: {checklist_path}")
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"Course outline file not found: {outline_path}")

        # Extract text from both documents
        checklist_text = extract_text(checklist_path)
        outline_text = extract_text(outline_path)
        
        # Extract checklist items
        checklist_items = extract_checklist_items_strict(checklist_text)
        if not checklist_items:
            # Fallback: Try to parse the checklist directly
            checklist_items = checklist_text.strip().split('\n')
            checklist_items = [item.strip() for item in checklist_items if item.strip()]
        
        # Validate links in the outline
        valid_links, invalid_links = validate_links(outline_text)
        
        # Process using AI with optimized parameters
        additional_context = f"Document contains {len(valid_links)} valid and {len(invalid_links)} invalid links."
        analysis_results = analyze_checklist_items_batch(
            checklist_items, 
            outline_text,
            max_attempts=2,
            additional_context=additional_context
        )
        
        # Update link validation results
        for item in checklist_items:
            if 'link' in item.lower() or 'url' in item.lower():
                if invalid_links:
                    analysis_results[item] = {
                        'present': False,
                        'confidence': 0.9,
                        'explanation': f'Found {len(invalid_links)} invalid links in document',
                        'evidence': "Invalid links found: " + ", ".join(invalid_links[:3]),
                        'method': 'link_validation'
                    }
                else:
                    analysis_results[item] = {
                        'present': True,
                        'confidence': 0.9,
                        'explanation': 'All links in document are valid',
                        'evidence': "Valid links found: " + ", ".join(valid_links[:3]),
                        'method': 'link_validation'
                    }
        
        return {
            'checklist_items': checklist_items,
            'analysis_results': analysis_results
        }
        
    except Exception as e:
        logger.exception(f"Error in process_and_evaluate: {str(e)}")
        return {
            'error': str(e)
        }

def format_results_for_output(results: Dict[str, Any]) -> str:
    """
    Format results according to the specified output format.
    
    Args:
        results: The analysis results
        
    Returns:
        Formatted string for display
    """
    if 'error' in results:
        return f"Error: {results['error']}"
    
    checklist_items = results.get('checklist_items', [])
    analysis_results = results.get('analysis_results', {})
    
    output = []
    
    for idx, item in enumerate(checklist_items, 1):
        result = analysis_results.get(item, {})
        is_present = result.get('present', False)
        explanation = result.get('explanation', '')
        evidence = result.get('evidence', '')
        
        # Determine status (Yes/No/N/A)
        status = "N/A"
        if "n/a" in str(explanation).lower() or "not applicable" in str(explanation).lower():
            status = "N/A"
        elif is_present:
            status = "Yes"
        else:
            status = "No"
        
        # Format justification
        justification = explanation
        if len(justification) > 200:
            justification = justification[:197] + "..."
        
        # Add to output
        output.append(f"**Checklist Item #{idx}:** {item}")
        output.append(f"**Status:** {status}")
        output.append(f"**Justification:** {justification}")
        output.append("")  # Empty line for readability
    
    return "\n".join(output)

def main():
    """Main entry point for the script."""
    # Check command line arguments
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <checklist_file_path> <outline_file_path>")
        sys.exit(1)
    
    checklist_path = sys.argv[1]
    outline_path = sys.argv[2]
    
    # Process and evaluate
    results = process_and_evaluate(checklist_path, outline_path)
    
    # Format and display results
    output = format_results_for_output(results)
    print(output)

if __name__ == "__main__":
    main()