import os
import re
from fpdf import FPDF

def add_detailed_checklist_table(pdf, analysis_data, detailed_checklist_items):
    """
    Add a detailed checklist table to the PDF with complete descriptions
    
    Args:
        pdf: The FPDF object
        analysis_data: The analysis data dictionary
        detailed_checklist_items: List of detailed checklist items with full descriptions
    """
    # Add a new page for the detailed checklist evaluation
    pdf.add_page()
    pdf.set_font('DejaVu', 'B', 16)
    pdf.cell(190, 10, 'Complete Checklist Evaluation', 0, 1, 'C')
    pdf.ln(5)
    
    # Add explanation about the detailed checklist
    pdf.set_font('DejaVu', '', 10)
    pdf.multi_cell(190, 6, 'The following table provides a detailed evaluation of the course outline against each checklist item, including comprehensive descriptions of the requirements.', 0, 'L')
    pdf.ln(8)
    
    # Create a professional table design
    # Set up the table header with blue background
    pdf.set_fill_color(220, 230, 241)  # Light blue background
    pdf.set_font('DejaVu', 'B', 9)
    pdf.cell(12, 10, '#', 1, 0, 'C', True)
    pdf.cell(40, 10, 'Status', 1, 0, 'C', True)
    pdf.cell(138, 10, 'Detailed Requirement Description', 1, 1, 'C', True)
    
    # Parse the detailed checklist items
    enhanced_items = []
    
    # Extract item numbers and titles
    for item_desc in detailed_checklist_items:
        # Match the item number and name (everything before the first colon)
        match = re.match(r'^(\d+)\.\s+([^:]+):', item_desc)
        if match:
            num = match.group(1)
            name = match.group(2).strip()
            
            # Extract the description (everything after the first colon)
            description_start = item_desc.find(':') + 1
            if description_start > 0:
                description = item_desc[description_start:].strip()
            else:
                description = ""
                
            # Find corresponding checklist item in the analysis data
            status = 'missing'  # Default status
            for checklist_item in analysis_data.get('checklist_items', []):
                if name.lower() in checklist_item.lower():
                    result = analysis_data.get('analysis_results', {}).get(checklist_item, {})
                    status = result.get('status', 'present' if checklist_item not in analysis_data.get('missing_items', []) else 'missing')
                    break
            
            enhanced_items.append((num, name, description, status))
        else:
            print(f"No match found for item: {item_desc[:50]}...")
    
    # Sort by item number
    enhanced_items.sort(key=lambda x: int(x[0]))
    
    # Add each detailed description with status
    alternate_row = False
    
    for num, name, description, status in enhanced_items:
        # Set alternating row background
        alternate_row = not alternate_row
        if alternate_row:
            pdf.set_fill_color(245, 245, 245)  # Light gray for alternating rows
        else:
            pdf.set_fill_color(255, 255, 255)  # White
            
        # Calculate row height based on content
        # For description, calculate based on text length
        full_description = f"{name}: {description}"
        description_length = len(full_description)
        chars_per_line = 40  # Characters per line estimate (conservative)
        desc_lines = max(1, description_length / chars_per_line)
        row_height = max(12, desc_lines * 5)  # At least 12mm, 5mm per line
        
        # Add extra padding for longer descriptions
        if desc_lines > 4:
            row_height += 5
        if desc_lines > 8:
            row_height += 5
        
        # Save current position for drawing cells of equal height
        y_position = pdf.get_y()
            
        # Draw item number cell
        pdf.set_font('DejaVu', 'B', 9)
        
        # Draw the rectangle for item number with fill
        x_pos = pdf.get_x()
        # Set fill color based on alternating rows
        if alternate_row:
            pdf.set_fill_color(245, 245, 245)  # Light gray
        else:
            pdf.set_fill_color(255, 255, 255)  # White
        pdf.rect(x_pos, y_position, 12, row_height, 'F')  # 'F' means filled rectangle
        
        # Center item number text
        pdf.set_xy(x_pos + (12 - pdf.get_string_width(num)) / 2, y_position + 2)
        pdf.cell(12, 5, num, 0, 0, 'C')
        
        # Move to status cell position
        pdf.set_xy(x_pos + 12, y_position)
        
        # Set color based on status
        if status == 'na':
            pdf.set_text_color(100, 100, 100)  # Gray for N/A
            status_text = 'NOT APPLICABLE'
        elif status == 'present':
            pdf.set_text_color(0, 128, 0)  # Green for present
            status_text = 'PRESENT'
        else:
            pdf.set_text_color(255, 0, 0)  # Red for missing
            status_text = 'MISSING'
        
        # Draw the status cell rectangle with fill
        status_x = pdf.get_x()
        # Set fill color based on alternating rows
        if alternate_row:
            pdf.set_fill_color(245, 245, 245)  # Light gray
        else:
            pdf.set_fill_color(255, 255, 255)  # White
        pdf.rect(status_x, y_position, 40, row_height, 'F')  # 'F' means filled rectangle
        
        # Draw status cell border
        pdf.rect(status_x, y_position, 40, row_height)
        
        # Center status text vertically
        pdf.set_xy(status_x + (40 - pdf.get_string_width(status_text)) / 2, y_position + row_height/2 - 2)
        pdf.set_font('DejaVu', 'B', 9)
        pdf.cell(40, 5, status_text, 0, 0, 'C')
        pdf.set_text_color(0, 0, 0)  # Reset to black
        
        # Move to description cell position
        pdf.set_xy(status_x + 40, y_position)
        
        # Draw description cell rectangle with fill
        desc_x = pdf.get_x()
        # Set fill color based on alternating rows
        if alternate_row:
            pdf.set_fill_color(245, 245, 245)  # Light gray
        else:
            pdf.set_fill_color(255, 255, 255)  # White
        pdf.rect(desc_x, y_position, 138, row_height, 'F')  # 'F' means filled rectangle
        
        # Draw description cell border
        pdf.rect(desc_x, y_position, 138, row_height)
        
        # Format description text - Item name in bold, then details
        pdf.set_xy(pdf.get_x() + 3, y_position + 2)  # Add internal padding
        pdf.set_font('DejaVu', 'B', 9)
        pdf.cell(132, 5, name, 0, 1, 'L')
        
        # Add the description text
        pdf.set_xy(pdf.get_x() + 3, pdf.get_y())
        pdf.set_font('DejaVu', '', 8)
        
        # Format the description to fit the cell width with proper wrapping
        if description:
            words = description.split()
            line = ""
            wrapped_text = ""
            for word in words:
                test_line = line + word + " "
                if pdf.get_string_width(test_line) < 132:
                    line = test_line
                else:
                    wrapped_text += line + "\n"
                    line = word + " "
            wrapped_text += line
            
            # Write the wrapped text
            pdf.multi_cell(132, 4, wrapped_text, 0, 'L')
        
        # Move to next row position
        pdf.set_xy(pdf.get_x(), y_position + row_height)
        
        # Check for page break if needed
        if pdf.get_y() > 270:
            pdf.add_page()
            # Repeat the table header with blue background
            pdf.set_fill_color(220, 230, 241)  # Light blue background
            pdf.set_font('DejaVu', 'B', 9)
            pdf.cell(12, 10, '#', 1, 0, 'C', True)
            pdf.cell(40, 10, 'Status', 1, 0, 'C', True)
            pdf.cell(138, 10, 'Detailed Requirement Description', 1, 1, 'C', True)
            # Reset alternating row counter
            alternate_row = False