#!/usr/bin/env python3
"""
Script to verify that OpenAI is used exclusively for all checklist items.
This does not make API calls, but instead examines the code structure.
"""

import re
import os
import sys

def check_file_for_pattern_matching(filepath):
    """
    Check if a file contains pattern matching code that isn't properly disabled.
    Returns (has_pattern_matching, details)
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Look for pattern matching that isn't enclosed in an if False block
    total_lines = content.count('\n')
    
    # Find if False blocks
    if_false_blocks = []
    for match in re.finditer(r'if\s+False\s*:', content):
        block_start = content[:match.end()].count('\n')
        
        # Find the end of this block (very basic indent detection)
        lines_after = content[match.end():].split('\n')
        indent_level = None
        block_end = block_start
        
        for i, line in enumerate(lines_after):
            stripped = line.lstrip()
            if not stripped:  # Empty line
                continue
                
            current_indent = len(line) - len(stripped)
            
            if indent_level is None:
                indent_level = current_indent
                continue
            
            if current_indent <= indent_level and stripped:
                block_end = block_start + i
                break
        
        if_false_blocks.append((block_start, block_end))
    
    # Look for pattern matching methods outside of if False blocks
    pattern_matching_indicators = [
        'pattern_matching',
        'check_item_in_document',
        'find_matching_excerpt',
        'improved_pattern_matching',
        'enhanced_check_item_in_document'
    ]
    
    # Find all lines with these indicators
    pattern_matching_lines = []
    for i, line in enumerate(content.split('\n')):
        line_num = i + 1
        if any(indicator in line for indicator in pattern_matching_indicators):
            pattern_matching_lines.append((line_num, line.strip()))
    
    # Check if these lines are inside if False blocks
    active_pattern_matching = []
    for line_num, line_text in pattern_matching_lines:
        inside_if_false = False
        for start, end in if_false_blocks:
            if start < line_num <= end:
                inside_if_false = True
                break
        
        if not inside_if_false:
            active_pattern_matching.append((line_num, line_text))
    
    # Determine if there's active pattern matching code
    has_active_pattern_matching = len(active_pattern_matching) > 0
    
    # Output details
    details = []
    if has_active_pattern_matching:
        details.append(f"!!! FOUND PATTERN MATCHING CODE that is not in an 'if False' block in {filepath}")
        details.append(f"Found {len(active_pattern_matching)} instances:")
        for line_num, line_text in active_pattern_matching[:10]:  # Only show first 10
            details.append(f"Line {line_num}: {line_text}")
        if len(active_pattern_matching) > 10:
            details.append(f"... and {len(active_pattern_matching) - 10} more instances")
    else:
        details.append(f"No active pattern matching found in {filepath}")
    
    return has_active_pattern_matching, "\n".join(details)

def check_method_field_consistency(filepath):
    """
    Check if 'method' field is always set to 'ai_general_analysis'
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find all method field assignments
    method_assignments = []
    pattern = r"['\"](method)['\"]:\s*['\"]([^'\"]+)['\"]"
    
    for match in re.finditer(pattern, content):
        method_value = match.group(2)
        line_num = content[:match.start()].count('\n') + 1
        method_assignments.append((line_num, method_value))
    
    # Check for non-ai_general_analysis methods that aren't in if False blocks
    if_false_blocks = []
    for match in re.finditer(r'if\s+False\s*:', content):
        block_start = content[:match.end()].count('\n')
        
        # Find the end of this block (basic indent detection)
        lines_after = content[match.end():].split('\n')
        indent_level = None
        block_end = block_start
        
        for i, line in enumerate(lines_after):
            stripped = line.lstrip()
            if not stripped:  # Empty line
                continue
                
            current_indent = len(line) - len(stripped)
            
            if indent_level is None:
                indent_level = current_indent
                continue
            
            if current_indent <= indent_level and stripped:
                block_end = block_start + i
                break
        
        if_false_blocks.append((block_start, block_end))
    
    # Check methods outside if False blocks
    incorrect_methods = []
    for line_num, method_value in method_assignments:
        if method_value != 'ai_general_analysis' and method_value != 'openai_api_error' and method_value != 'initialization':
            inside_if_false = False
            for start, end in if_false_blocks:
                if start < line_num <= end:
                    inside_if_false = True
                    break
            
            if not inside_if_false:
                incorrect_methods.append((line_num, method_value))
    
    # Determine if there are inconsistent methods
    has_inconsistent_methods = len(incorrect_methods) > 0
    
    # Output details
    details = []
    if has_inconsistent_methods:
        details.append(f"!!! FOUND INCONSISTENT METHOD FIELD VALUES in {filepath}")
        details.append(f"Expected 'ai_general_analysis' but found {len(incorrect_methods)} other values:")
        for line_num, method_value in incorrect_methods:
            details.append(f"Line {line_num}: '{method_value}'")
    else:
        details.append(f"All method fields in {filepath} are properly set to 'ai_general_analysis' (or allowed values)")
    
    return has_inconsistent_methods, "\n".join(details)

def main():
    print("Checking implementation for pattern matching code outside of 'if False' blocks...")
    print("=" * 80)
    
    files_to_check = [
        'document_processor.py',
        'api_analysis.py',
        'app.py',
        'openai_helper.py'
    ]
    
    has_pattern_matching = False
    has_inconsistent_methods = False
    
    # Check for pattern matching
    for file in files_to_check:
        file_has_pattern, details = check_file_for_pattern_matching(file)
        if file_has_pattern:
            has_pattern_matching = True
        
        print(details)
        print("-" * 80)
    
    # Check for inconsistent method values
    for file in files_to_check:
        file_has_inconsistent, details = check_method_field_consistency(file)
        if file_has_inconsistent:
            has_inconsistent_methods = True
        
        print(details)
        print("-" * 80)
    
    # Summary
    print("\nSUMMARY:")
    print("=" * 80)
    if has_pattern_matching:
        print("❌ FOUND ACTIVE PATTERN MATCHING CODE - This must be fixed!")
    else:
        print("✓ No active pattern matching code found")
        
    if has_inconsistent_methods:
        print("❌ FOUND INCONSISTENT METHOD FIELD VALUES - Should be 'ai_general_analysis'")
    else:
        print("✓ All method fields consistently use 'ai_general_analysis'")
    
    if not has_pattern_matching and not has_inconsistent_methods:
        print("\n✓✓✓ IMPLEMENTATION LOOKS GOOD - Using OpenAI exclusively!")
        return 0
    else:
        print("\n❌❌❌ IMPLEMENTATION NEEDS FIXES - See details above")
        return 1

if __name__ == "__main__":
    sys.exit(main())