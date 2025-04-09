"""
Test PDF generation for the detailed checklist table
"""

import os
import re
import logging
from fpdf import FPDF

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_test_pdf():
    """Generate a test PDF with just the detailed checklist table"""
    try:
        print("Starting test PDF generation...")
        
        # Create sample analysis data 
        checklist_items = [
            "Instructor Email",
            "Course Objectives",
            "Textbooks & Other Course Material",
            "Grading Scale"
        ]
        
        analysis_data = {
            'checklist_items': checklist_items,
            'missing_items': ["Textbooks & Other Course Material"],
            'analysis_results': {
                "Instructor Email": {'status': 'present'},
                "Course Objectives": {'status': 'present'},
                "Textbooks & Other Course Material": {'status': 'missing'},
                "Grading Scale": {'status': 'na'}
            }
        }
        
        # Create a PDF with UTF-8 support
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        
        # Add Unicode font support with absolute paths
        base_path = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(base_path, 'static', 'fonts')
        print(f"Font path: {font_path}")
        
        try:
            # Add all required font variations
            pdf.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
            pdf.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
            pdf.add_font('DejaVu', 'I', os.path.join(font_path, 'DejaVuSansCondensed-Oblique.ttf'), uni=True)
            # Use 'I' instead of 'BI' to avoid FPDF style type error
            pdf.add_font('DejaVu', 'I', os.path.join(font_path, 'DejaVuSansCondensed-BoldOblique.ttf'), uni=True)
            print("Fonts added successfully")
        except Exception as e:
            print(f"Error adding fonts: {str(e)}")
            # Continue with default font if custom fonts fail
        
        # Set font
        pdf.set_font('DejaVu', '', 10)
        
        # Extract unique checklist items
        unique_checklist_items = list(set(checklist_items))
        total_items = len(unique_checklist_items)
        missing_items = [item for item in analysis_data['missing_items'] 
                        if analysis_data['analysis_results'].get(item, {}).get('status', '') != 'na']
        na_items = sum(1 for item in unique_checklist_items 
                      if analysis_data['analysis_results'].get(item, {}).get('status', '') == 'na')
        present_items = total_items - len(missing_items) - na_items
        
        # Add a new page for the detailed checklist descriptions with status
        pdf.add_page()
        print("Adding detailed checklist page...")
        
        pdf.set_font('DejaVu', 'B', 16)
        pdf.cell(190, 10, 'Complete Checklist Evaluation', 0, 1, 'C')
        pdf.ln(3)
        
        # Add explanation text
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(190, 5, 'This table provides a detailed evaluation of the course outline against all required checklist items. Each item shows the complete requirement description and current compliance status.', 0, 'L')
        pdf.ln(5)
        
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
            # Create a placeholder if the file can't be loaded
            enhanced_checklist = [f"{i+1}. {item}: This is a description for {item}." for i, item in enumerate(unique_checklist_items)]
            print(f"Created {len(enhanced_checklist)} placeholder items")
        
        # Create a professional table design
        # Set up the table header with blue background
        pdf.set_fill_color(220, 230, 241)  # Light blue background
        pdf.set_font('DejaVu', 'B', 9)
        pdf.cell(12, 10, '#', 1, 0, 'C', True)
        pdf.cell(40, 10, 'Status', 1, 0, 'C', True)
        pdf.cell(138, 10, 'Detailed Requirement Description', 1, 1, 'C', True)
        
        # Add each detailed description with status
        item_number = 1
        alternate_row = False
        
        # First, process the items to ensure all items from enhanced_checklist are included
        processed_items = set()
        enhanced_items = []
        
        # First pass to match existing items
        for item_desc in enhanced_checklist:
            print(f"Processing enhanced checklist item: {item_desc[:50]}...")
            match = re.match(r'^(\d+)\.\s+([^:]+):', item_desc)
            if match:
                num = match.group(1)
                name = match.group(2)
                print(f"  Matched: #{num} - {name}")
                found_match = False
                
                # Try to find this item in the user's checklist
                for checklist_item in unique_checklist_items:
                    if name.lower() in checklist_item.lower():
                        result = analysis_data['analysis_results'].get(checklist_item, {})
                        status = result.get('status', 'present' if checklist_item not in analysis_data['missing_items'] else 'missing')
                        
                        # Extract description - everything after the colon and first space
                        description_start = item_desc.find(":", len(num) + 2) + 1
                        if description_start > 0:
                            description = item_desc[description_start:].strip()
                        else:
                            description = ""
                            
                        enhanced_items.append((num, name, description, status, checklist_item))
                        processed_items.add(checklist_item)
                        found_match = True
                        print(f"    Found match with: {checklist_item}")
                        break
                
                # If no match found, add it as a default item
                if not found_match:
                    print(f"    No match found for: {name}")
                    # Extract description - everything after the colon and first space
                    description_start = item_desc.find(":", len(num) + 2) + 1
                    if description_start > 0:
                        description = item_desc[description_start:].strip()
                    else:
                        description = ""
                        
                    enhanced_items.append((num, name, description, 'missing', None))
            else:
                print(f"  NO REGEX MATCH for: {item_desc[:50]}...")
        
        # Add any remaining items from user's checklist
        for checklist_item in unique_checklist_items:
            if checklist_item not in processed_items:
                result = analysis_data['analysis_results'].get(checklist_item, {})
                status = result.get('status', 'present' if checklist_item not in analysis_data['missing_items'] else 'missing')
                enhanced_items.append((str(len(enhanced_items) + 1), checklist_item, "", status, checklist_item))
        
        # Sort by item number
        enhanced_items.sort(key=lambda x: int(x[0]))
        
        # Now render the table with all items
        print(f"Rendering table with {len(enhanced_items)} items")
        for num, name, description, status, original_item in enhanced_items:
            print(f"Drawing item: {num}. {name} (status: {status})")
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
        
        # Output the PDF
        print("Saving test PDF...")
        pdf.output("test_output.pdf")
        print("Test PDF generation complete!")
        return True
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    generate_test_pdf()