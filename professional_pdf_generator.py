#!/usr/bin/env python3
"""
Professional PDF Report Generator for Course Outline Analysis

This module provides enhanced PDF generation with a clean, professional design
for the course outline analysis reports.
"""

import os
import io
import logging
from fpdf import FPDF
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfessionalReportPDF(FPDF):
    """Enhanced PDF class with professional styling and header/footer"""
    
    def __init__(self, title="Course Outline Analysis Report", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.set_author("Syllabus Sync - University of Calgary")
        self.set_creator("Syllabus Sync AI Analysis Tool")
        self.set_title(title)
        
        # Set default margin
        self.set_margins(15, 15, 15)
        
        # Set up fonts
        base_path = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(base_path, 'static', 'fonts')
        
        # Add all required font variations
        self.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
        self.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
        self.add_font('DejaVu', 'I', os.path.join(font_path, 'DejaVuSansCondensed-Oblique.ttf'), uni=True)
    
    def header(self):
        """Add professional header to each page"""
        # Logo - if available
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'uofc_logo.svg')
        if os.path.exists(logo_path):
            self.image(logo_path, 15, 8, 25)
        
        # Title and date
        self.set_font('DejaVu', 'B', 15)
        self.set_xy(50, 10)
        self.cell(140, 10, self.title, 0, 0, 'R')
        
        # Date
        self.set_font('DejaVu', '', 8)
        self.set_xy(50, 20)
        self.cell(140, 5, f"Generated on: {datetime.now().strftime('%B %d, %Y')}", 0, 0, 'R')
        
        # Horizontal line
        self.set_draw_color(41, 105, 176)  # UofC Blue
        self.line(15, 28, 195, 28)
        self.ln(20)
    
    def footer(self):
        """Add professional footer to each page"""
        self.set_y(-15)
        self.set_font('DejaVu', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        
        # Horizontal line
        self.set_draw_color(41, 105, 176)  # UofC Blue
        self.line(15, 282, 195, 282)

def generate_pdf_report(analysis_data: Dict[str, Any], detailed_checklist_items: List[str] = []) -> bytes:
    """
    Generate a professional PDF report from analysis data.
    
    Args:
        analysis_data: Dictionary containing analysis results and checklist items
        detailed_checklist_items: List of detailed checklist descriptions
        
    Returns:
        PDF file content as bytes
    """
    try:
        # Create PDF instance with professional styling
        pdf = ProfessionalReportPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        # Executive Summary Section
        pdf.set_font('DejaVu', 'B', 14)
        pdf.set_fill_color(240, 240, 240)  # Light gray background
        pdf.cell(180, 10, 'Executive Summary', 0, 1, 'L', True)
        pdf.ln(2)
        
        # Count items by status
        total_items = len(analysis_data.get('checklist_items', []))
        present_count = 0
        missing_count = 0
        na_count = 0
        
        for item in analysis_data.get('checklist_items', []):
            result = analysis_data.get('analysis_results', {}).get(item, {})
            status = 'missing'
            
            if result.get('status') == 'na':
                na_count += 1
            elif result.get('present', False) or item not in analysis_data.get('missing_items', []):
                present_count += 1
            else:
                missing_count += 1
        
        # Overall compliance score
        compliance_score = present_count / (total_items - na_count) * 100 if (total_items - na_count) > 0 else 0
        
        # Summary statistics
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(180, 6, 'This report provides a comprehensive analysis of the course outline against University of Calgary institutional requirements.', 0, 'L')
        pdf.ln(2)
        
        # Data table for summary
        pdf.set_fill_color(245, 245, 245)  # Lighter gray for alternating rows
        
        # Overall score with graphical indicator
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(110, 10, 'Overall Compliance Score:', 0, 0, 'L')
        
        # Set color based on score
        if compliance_score >= 90:
            pdf.set_text_color(0, 128, 0)  # Green for high compliance
        elif compliance_score >= 70:
            pdf.set_text_color(255, 140, 0)  # Orange for medium compliance
        else:
            pdf.set_text_color(220, 0, 0)  # Red for low compliance
            
        pdf.cell(70, 10, f"{compliance_score:.1f}%", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)  # Reset to black
        
        # Statistics table
        pdf.set_font('DejaVu', '', 10)
        pdf.ln(2)
        
        # Table header
        pdf.set_fill_color(41, 105, 176)  # UofC Blue
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.cell(60, 8, 'Category', 1, 0, 'C', True)
        pdf.cell(60, 8, 'Count', 1, 0, 'C', True)
        pdf.cell(60, 8, 'Percentage', 1, 1, 'C', True)
        pdf.set_text_color(0, 0, 0)  # Reset to black
        
        # Present items
        pdf.set_fill_color(245, 245, 245)  # Light gray for alternating rows
        pdf.cell(60, 8, 'Present', 1, 0, 'L', True)
        pdf.cell(60, 8, str(present_count), 1, 0, 'C', True)
        pdf.cell(60, 8, f"{present_count/total_items*100:.1f}%" if total_items > 0 else "0.0%", 1, 1, 'C', True)
        
        # Missing items
        pdf.set_fill_color(255, 255, 255)  # White
        pdf.cell(60, 8, 'Missing', 1, 0, 'L')
        pdf.cell(60, 8, str(missing_count), 1, 0, 'C')
        pdf.cell(60, 8, f"{missing_count/total_items*100:.1f}%" if total_items > 0 else "0.0%", 1, 1, 'C')
        
        # Not applicable items
        pdf.set_fill_color(245, 245, 245)  # Light gray for alternating rows
        pdf.cell(60, 8, 'Not Applicable', 1, 0, 'L', True)
        pdf.cell(60, 8, str(na_count), 1, 0, 'C', True)
        pdf.cell(60, 8, f"{na_count/total_items*100:.1f}%" if total_items > 0 else "0.0%", 1, 1, 'C', True)
        
        # Total
        pdf.set_fill_color(220, 230, 241)  # Lighter blue for total row
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(60, 8, 'Total Items', 1, 0, 'L', True)
        pdf.cell(60, 8, str(total_items), 1, 0, 'C', True)
        pdf.cell(60, 8, "100.0%", 1, 1, 'C', True)
        
        pdf.ln(6)
        
        # Missing Items Section (if any)
        if missing_count > 0:
            pdf.set_font('DejaVu', 'B', 14)
            pdf.set_fill_color(240, 240, 240)  # Light gray background
            pdf.cell(180, 10, 'Missing Requirements', 0, 1, 'L', True)
            pdf.ln(2)
            
            pdf.set_font('DejaVu', '', 10)
            pdf.multi_cell(180, 6, 'The following required elements were not found in the course outline:', 0, 'L')
            pdf.ln(2)
            
            # Table for missing items
            pdf.set_fill_color(41, 105, 176)  # UofC Blue
            pdf.set_text_color(255, 255, 255)  # White text
            pdf.set_font('DejaVu', 'B', 10)
            pdf.cell(15, 8, '#', 1, 0, 'C', True)
            pdf.cell(165, 8, 'Requirement', 1, 1, 'C', True)
            pdf.set_text_color(0, 0, 0)  # Reset to black
            
            # List missing items
            pdf.set_font('DejaVu', '', 10)
            missing_items = analysis_data.get('missing_items', [])
            
            for i, item in enumerate(missing_items):
                # Alternate row colors
                if i % 2 == 0:
                    pdf.set_fill_color(245, 245, 245)  # Light gray
                else:
                    pdf.set_fill_color(255, 255, 255)  # White
                
                pdf.cell(15, 8, str(i+1), 1, 0, 'C', True)
                pdf.cell(165, 8, item, 1, 1, 'L', True)
            
            pdf.ln(6)
        
        # Add detailed checklist evaluation if available
        if detailed_checklist_items:
            pdf.add_page()
            
            pdf.set_font('DejaVu', 'B', 14)
            pdf.set_fill_color(240, 240, 240)  # Light gray background
            pdf.cell(180, 10, 'Detailed Compliance Analysis', 0, 1, 'L', True)
            pdf.ln(2)
            
            pdf.set_font('DejaVu', '', 10)
            pdf.multi_cell(180, 6, 'This section provides a detailed evaluation of each requirement against the course outline.', 0, 'L')
            pdf.ln(2)
            
            # Table header for detailed analysis
            pdf.set_fill_color(41, 105, 176)  # UofC Blue
            pdf.set_text_color(255, 255, 255)  # White text
            pdf.set_font('DejaVu', 'B', 9)
            pdf.cell(10, 10, '#', 1, 0, 'C', True)
            pdf.cell(40, 10, 'Status', 1, 0, 'C', True)
            pdf.cell(130, 10, 'Requirement', 1, 1, 'C', True)
            pdf.set_text_color(0, 0, 0)  # Reset to black
            
            # Parse and display detailed items
            for i, item_desc in enumerate(detailed_checklist_items):
                # Extract item number and name
                import re
                match = re.match(r'^(\d+)\.\s+([^:]+):', item_desc)
                
                if match:
                    num = match.group(1)
                    name = match.group(2).strip()
                    
                    # Find item status
                    status = 'missing'
                    for checklist_item in analysis_data.get('checklist_items', []):
                        if name.lower() in checklist_item.lower():
                            result = analysis_data.get('analysis_results', {}).get(checklist_item, {})
                            if result.get('status') == 'na':
                                status = 'na'
                            elif checklist_item not in analysis_data.get('missing_items', []) or result.get('present', False):
                                status = 'present'
                            break
                    
                    # Set colors for alternating rows
                    if i % 2 == 0:
                        pdf.set_fill_color(245, 245, 245)  # Light gray
                    else:
                        pdf.set_fill_color(255, 255, 255)  # White
                    
                    # Draw cells
                    pdf.set_font('DejaVu', 'B', 9)
                    pdf.cell(10, 10, num, 1, 0, 'C', True)
                    
                    # Set color based on status
                    if status == 'na':
                        pdf.set_text_color(128, 128, 128)  # Gray for N/A
                        status_text = 'N/A'
                    elif status == 'present':
                        pdf.set_text_color(0, 128, 0)  # Green for present
                        status_text = 'PRESENT'
                    else:
                        pdf.set_text_color(220, 0, 0)  # Red for missing
                        status_text = 'MISSING'
                    
                    pdf.cell(40, 10, status_text, 1, 0, 'C', True)
                    pdf.set_text_color(0, 0, 0)  # Reset to black
                    
                    # Item name with line wrapping
                    pdf.set_font('DejaVu', '', 9)
                    
                    # Calculate height based on text length
                    if len(name) > 70:  # If name is too long
                        pdf.cell(130, 10, name[:67] + "...", 1, 1, 'L', True)
                    else:
                        pdf.cell(130, 10, name, 1, 1, 'L', True)
                    
                    # Check for page break
                    if pdf.get_y() > 270:
                        pdf.add_page()
                        
                        # Repeat table header
                        pdf.set_fill_color(41, 105, 176)  # UofC Blue
                        pdf.set_text_color(255, 255, 255)  # White text
                        pdf.set_font('DejaVu', 'B', 9)
                        pdf.cell(10, 10, '#', 1, 0, 'C', True)
                        pdf.cell(40, 10, 'Status', 1, 0, 'C', True)
                        pdf.cell(130, 10, 'Requirement', 1, 1, 'C', True)
                        pdf.set_text_color(0, 0, 0)  # Reset to black
        
        # Generate PDF as bytes
        output = pdf.output(dest='S')
        if isinstance(output, str):
            return output.encode('latin1')
        return output
        
    except Exception as e:
        logger.error(f"Error generating professional PDF report: {str(e)}")
        raise

def replace_pdf_generator():
    """Replace the default PDF generator with the professional version"""
    import app
    
    # Store the original function for reference
    original_download_pdf = app.download_pdf
    
    # Define the replacement function
    def enhanced_download_pdf():
        """Generate a professional PDF report of the analysis results"""
        try:
            # Import Flask objects from app module
            from app import session, send_file, flash, redirect
            import io
            
            # Get session data
            analysis_data = session.get('analysis_data', {})
            
            if not analysis_data or not analysis_data.get('checklist_items'):
                flash("No analysis data found. Please analyze a document first.")
                return redirect('/')
                
            # Load detailed checklist items
            detailed_items = []
            try:
                with open('enhanced_checklist.txt', 'r') as f:
                    content = f.read()
                    # Extract numbered items with their detailed descriptions
                    import re
                    pattern = r'(\d+)\.\s+(.*?)(?=\n\n\d+\.|\Z)'
                    matches = re.findall(pattern, content, re.DOTALL)
                    
                    # Sort by item number to ensure correct order
                    matches.sort(key=lambda x: int(x[0]))
                    for num, desc in matches:
                        detailed_items.append(f"{num}. {desc.strip()}")
            except Exception as e:
                logger.warning(f"Could not load detailed checklist items: {str(e)}")
            
            # Generate the professional PDF
            pdf_bytes = generate_pdf_report(analysis_data, detailed_items)
            
            # Send the PDF to the browser
            return send_file(
                io.BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=False,
                download_name='course_outline_analysis.pdf'
            )
            
        except Exception as e:
            logger.exception(f"Error generating professional PDF: {str(e)}")
            flash(f"Error generating PDF report: {str(e)}")
            return redirect('/')
    
    # Replace the function
    app.download_pdf = enhanced_download_pdf
    
    return True

if __name__ == "__main__":
    # Test the PDF generator
    test_data = {
        'checklist_items': ['Item 1', 'Item 2', 'Item 3'],
        'missing_items': ['Item 2'],
        'analysis_results': {
            'Item 1': {'status': 'present'},
            'Item 2': {'status': 'missing'},
            'Item 3': {'status': 'na'}
        }
    }
    
    pdf_bytes = generate_pdf_report(test_data)
    
    # Save to file for testing
    with open('test_professional_report.pdf', 'wb') as f:
        f.write(pdf_bytes)
        
    logger.info("Test PDF generated successfully")