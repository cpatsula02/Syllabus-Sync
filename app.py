from flask import Flask, request, render_template, jsonify, redirect, flash, session, send_file
from werkzeug.utils import secure_filename
import os
import io
import logging
import re
from fpdf import FPDF  # Import FPDF from fpdf2 package
from document_processor import process_documents

# Configure logging with more detailed output
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if OpenAI API key is available
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    logger.info("OpenAI API key is configured. Advanced AI analysis is available.")
else:
    logger.warning("OpenAI API key is not configured. Fallback to traditional analysis only.")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get('SESSION_SECRET', 'dev_secret_key')

@app.errorhandler(Exception)
def handle_error(e):
    app.logger.error(f"Unhandled error: {str(e)}")
    return render_template(
        'index.html',
        error="An error occurred while processing your request. Please try again with a smaller file or contact support."
    ), 500

# In-memory storage for last analysis
analysis_data = {
    'checklist_items': [],
    'analysis_results': {},
    'missing_items': [],
    'grade_table_items': []
}

def identify_grade_table_items(checklist_items):
    """
    Identify items related to grade distribution table for special handling.
    These items often need more focused analysis.
    """
    grade_items = []
    for item in checklist_items:
        item_lower = item.lower()
        # Check for grade distribution table related keywords
        if any(term in item_lower for term in [
            'grade distribution table', 
            'weight', 
            'assessment',
            'due date',
            'participation',
            'group project',
            'final exam',
            'take home',
            'class schedule',
            'missed assessment policy',
            'late policy'
        ]):
            grade_items.append(item)
    return grade_items

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'checklist' not in request.files or 'outline' not in request.files:
            return jsonify({'error': 'Both files are required'}), 400

        checklist = request.files['checklist']
        outline = request.files['outline']

        if checklist.filename == '' or outline.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(checklist.filename))
        outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline.filename))

        try:
            checklist.save(checklist_path)
            outline.save(outline_path)

            # Get additional context if provided
            additional_context = request.form.get('additional_context', '').strip()
            
            # Add specific guidance for grade table analysis if not already present
            if additional_context and not any(term in additional_context.lower() for term in 
                                             ['grade distribution', 'grade table', 'assessment weight']):
                additional_context += "\n\nPay special attention to the Grade Distribution Table items, " + \
                                    "including assessment weights, due dates, missed assessment policy, " + \
                                    "late policy, and class participation details. These are critical " + \
                                    "components that need precise identification in the document."

            # Get number of API attempts
            try:
                api_attempts = int(request.form.get('api_attempts', 3))
            except ValueError:
                api_attempts = 3  # Default to 3 attempts if invalid value

            try:
                # Process files with specified API attempts and context
                logger.info(f"Starting document processing with {api_attempts} API attempts")
                logger.info(f"Checklist path: {checklist_path}")
                logger.info(f"Outline path: {outline_path}")
                
                checklist_items, analysis_results = process_documents(
                    checklist_path, 
                    outline_path, 
                    api_attempts=api_attempts, 
                    additional_context=additional_context
                )
                
                logger.info(f"Document processing complete. Found {len(checklist_items)} checklist items.")
                if not checklist_items or len(checklist_items) == 0:
                    logger.error("No checklist items were extracted! This will cause issues.")
                    flash("Error: No checklist items could be extracted from the document. Please check the file format.")
                    return redirect(request.url)
                    
            except Exception as api_error:
                logger.exception(f"API error during document processing: {str(api_error)}")
                error_message = str(api_error)
                
                # Check if this is likely an API error
                if "openai" in error_message.lower() or "api" in error_message.lower():
                    flash("There was an issue connecting to the OpenAI API. Retrying with traditional pattern matching...")
                    # Retry with no API calls (force fallback methods)
                    checklist_items, analysis_results = process_documents(
                        checklist_path, 
                        outline_path, 
                        api_attempts=0,  # Force fallback methods 
                        additional_context=additional_context
                    )
                else:
                    # Re-raise for other types of errors
                    raise

            if "error" in analysis_results:
                flash(analysis_results["error"])
                return redirect(request.url)

            # Identify grade table related items for special handling
            grade_table_items = identify_grade_table_items(checklist_items)
            logger.info(f"Identified {len(grade_table_items)} grade table related items")
            
            # Format results for template with enhanced data and duplicate prevention
            results = []
            present_count = 0
            missing_count = 0
            missing_items = []
            processed_items = set()  # Track processed items to prevent duplicates

            for item in checklist_items:
                # Skip if this item has already been processed
                if item in processed_items:
                    continue
                    
                processed_items.add(item)  # Mark as processed
                result = analysis_results.get(item, {})
                is_present = result.get("present", False)
                is_grade_item = item in grade_table_items
                
                # Set higher minimum confidence threshold for grade table items
                if is_grade_item and result.get("confidence", 0) < 0.6:
                    # For borderline grade table items, double-check with more specific criteria
                    item_lower = item.lower()
                    
                    # This helps catch cases where normal pattern matching might fail
                    if is_present and (
                        ('distribution' in item_lower and not 'table' in result.get("evidence", "").lower()) or
                        ('due date' in item_lower and not any(w in result.get("evidence", "").lower() for w in ['due', 'deadline', 'submit'])) or
                        ('missed assessment' in item_lower and not any(w in result.get("evidence", "").lower() for w in ['miss', 'absent', 'policy'])) or
                        ('late policy' in item_lower and not any(w in result.get("evidence", "").lower() for w in ['late', 'policy', 'submission']))
                    ):
                        # Override if we suspect a false positive
                        is_present = False
                        result["present"] = False
                        result["explanation"] = "Not found with sufficient evidence in document"
                        result["confidence"] = 0.2
                        
                if is_present:
                    present_count += 1
                else:
                    missing_count += 1
                    missing_items.append(item)

                results.append({
                    "item": item,
                    "present": is_present,
                    "explanation": result.get("explanation", ""),
                    "evidence": result.get("evidence", ""),
                    "is_grade_item": is_grade_item,
                    "method": result.get("method", "pattern_matching"),
                    "confidence": result.get("confidence", None)
                })
            
            # Store data for other routes
            analysis_data['checklist_items'] = checklist_items
            analysis_data['analysis_results'] = analysis_results
            analysis_data['missing_items'] = missing_items
            analysis_data['grade_table_items'] = grade_table_items
            
            # Calculate analysis method statistics
            analysis_methods = {}
            api_calls_made = 0
            total_verification_calls = 0
            
            for item in checklist_items:
                result = analysis_results.get(item, {})
                method = result.get("method", "pattern_matching")
                
                # Count occurrences of each method
                if method in analysis_methods:
                    analysis_methods[method] += 1
                else:
                    analysis_methods[method] = 1
                    
                # Count verification attempts per item
                verification_attempts = result.get("verification_attempts", 0)
                total_verification_calls += verification_attempts
                
                # Count items that used AI (at least one successful call)
                if verification_attempts > 0:
                    api_calls_made += 1

            return render_template('results.html', 
                                results=results,
                                present_count=present_count,
                                missing_count=missing_count,
                                total_count=len(checklist_items),
                                missing_items=missing_items,
                                grade_table_items=grade_table_items,
                                analysis_methods=analysis_methods,
                                api_calls_made=api_calls_made,
                                max_attempts=api_attempts)

        except Exception as e:
            logger.exception(f"Error processing documents: {str(e)}")
            flash(f'An error occurred: {str(e)}')
            return redirect(request.url)
        finally:
            # Cleanup
            if os.path.exists(checklist_path):
                os.remove(checklist_path)
            if os.path.exists(outline_path):
                os.remove(outline_path)

    return render_template('index.html')

@app.route('/get-match-details', methods=['GET'])
def get_match_details():
    """Get the matching excerpt for a checklist item"""
    item = request.args.get('item')
    
    if not item or not analysis_data['analysis_results']:
        return jsonify({'found': False, 'error': 'No analysis results available'})
    
    # Check if this is a grade table item for special handling
    is_grade_item = item in analysis_data['grade_table_items']
    
    # Get the details from our stored analysis
    result = analysis_data['analysis_results'].get(item, {})
    
    if result.get('present', False) and result.get('evidence'):
        excerpt = result['evidence']
        
        # For grade table items, enhance the highlighting to make matches more visible
        if is_grade_item:
            # Extract key terms from the item
            item_lower = item.lower()
            key_terms = []
            
            # Add general grade table terms
            key_terms.extend(['grade', 'distribution', 'weight', 'assessment', 'percent', '%'])
            
            # Add specific terms based on item content
            if 'due date' in item_lower:
                key_terms.extend(['due', 'deadline', 'submit', 'date'])
            elif 'missed assessment' in item_lower:
                key_terms.extend(['missed', 'miss', 'absence', 'policy', 'procedure'])
            elif 'late policy' in item_lower:
                key_terms.extend(['late', 'policy', 'penalty', 'submission'])
            elif 'participation' in item_lower:
                key_terms.extend(['participation', 'engage', 'discussion', 'class'])
            elif 'group project' in item_lower:
                key_terms.extend(['group', 'project', 'team', 'collaborative'])
            elif 'final exam' in item_lower:
                key_terms.extend(['final', 'exam', 'examination', 'test'])
            elif 'take home' in item_lower:
                key_terms.extend(['take', 'home', 'assignment'])
            elif 'class schedule' in item_lower:
                key_terms.extend(['schedule', 'timetable', 'calendar', 'weekly'])
                
            # Apply highlighting to make matches more visible
            for term in key_terms:
                # Only highlight if the term is at least 3 chars to avoid highlighting too much
                if len(term) >= 3:
                    pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                    excerpt = pattern.sub(f'<span style="background-color: #c2f0c2; font-weight: bold;">{term}</span>', excerpt)
        
        response_data = {
            'found': True,
            'excerpt': excerpt,
            'is_grade_item': is_grade_item,
            'method': result.get('method', 'pattern_matching'),
            'confidence': result.get('confidence', None)
        }
        
        # Add verification metadata if available
        if 'verification_attempts' in result:
            response_data['verification_attempts'] = result['verification_attempts']
        if 'verification_present_votes' in result:
            response_data['verification_present_votes'] = result['verification_present_votes']
        
        return jsonify(response_data)
    
    return jsonify({'found': False})

@app.route('/download_pdf', methods=['GET'])
def download_pdf():
    """Generate a PDF report of the analysis results"""
    if not analysis_data['checklist_items']:
        flash('No analysis results available. Please analyze documents first.')
        return redirect('/')
    
    import os
    try:
        # Create PDF with UTF-8 support
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        # Add Unicode font support with absolute paths
        base_path = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(base_path, 'static', 'fonts')
        
        # Add all required font variations
        pdf.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
        pdf.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
        pdf.add_font('DejaVu', 'I', os.path.join(font_path, 'DejaVuSansCondensed-Oblique.ttf'), uni=True)
        pdf.add_font('DejaVu', 'BI', os.path.join(font_path, 'DejaVuSansCondensed-BoldOblique.ttf'), uni=True)
        
        # Set up document
        pdf.set_font('DejaVu', 'B', 16)
        pdf.cell(190, 10, 'Syllabus Sync Analysis Report', 0, 1, 'C')
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(190, 10, 'University of Calgary', 0, 1, 'C')
        pdf.ln(5)
        
        # Summary section
        pdf.set_font('DejaVu', 'B', 14)
        pdf.cell(190, 10, 'Summary', 0, 1, 'L')
        pdf.set_font('DejaVu', '', 10)
        
        total_items = len(analysis_data['checklist_items'])
        missing_items = len(analysis_data['missing_items'])
        present_items = total_items - missing_items
        
        # Calculate API usage statistics for the PDF report
        analysis_methods = {}
        ai_analyzed_items = 0
        total_verification_calls = 0
        
        for item in analysis_data['checklist_items']:
            result = analysis_data['analysis_results'].get(item, {})
            method = result.get("method", "pattern_matching")
            
            # Count occurrences of each method
            if method in analysis_methods:
                analysis_methods[method] += 1
            else:
                analysis_methods[method] = 1
                
            # Count verification attempts per item
            verification_attempts = result.get("verification_attempts", 0)
            total_verification_calls += verification_attempts
            
            # Count items that used AI (at least one successful verification)
            if verification_attempts > 0:
                ai_analyzed_items += 1
        
        pdf.cell(95, 8, f'Total checklist items: {total_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'Items present: {present_items}', 1, 1, 'L')
        pdf.cell(95, 8, f'Items missing: {missing_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'AI verifications: {total_verification_calls}', 1, 1, 'L')
        pdf.ln(5)
        
        # Add analysis method statistics
        if len(analysis_methods) > 1:  # Only add if we have different methods
            pdf.set_font('DejaVu', 'B', 9)
            pdf.cell(190, 8, 'Analysis Methods Used:', 0, 1, 'L')
            
            for method, count in analysis_methods.items():
                method_name = method.replace('_', ' ').title()
                pdf.cell(190, 6, f'- {method_name}: {count} items', 0, 1, 'L')
                
            pdf.ln(3)
            pdf.set_font('DejaVu', '', 10)  # Reset font
        
        # Missing items section
        if missing_items > 0:
            pdf.set_font('DejaVu', 'B', 12)
            pdf.cell(190, 10, 'Missing Items:', 0, 1, 'L')
            pdf.set_font('DejaVu', '', 10)
            
            for item in analysis_data['missing_items']:
                # Highlight grade table items in the missing list
                is_grade_item = item in analysis_data['grade_table_items']
                if is_grade_item:
                    pdf.set_text_color(200, 0, 0)  # Red for important missing items
                
                # Calculate required height for the missing item text
                item_length = len(item)
                chars_per_line = 60  # Conservative estimate
                item_lines = max(1, item_length / chars_per_line)
                item_height = max(7, item_lines * 5)  # Minimum 7mm, 5mm per line
                
                # Format the missing item text with generous spacing
                pdf.multi_cell(190, item_height, f"- {item}", 0, 'L')
                
                # Add rationale for why the item is missing
                result = analysis_data['analysis_results'].get(item, {})
                explanation = result.get('explanation', '')
                if explanation:
                    pdf.set_text_color(100, 100, 100)  # Gray
                    pdf.set_font('DejaVu', 'I', 9)  # Italic, smaller font
                    
                    # Calculate height needed for explanation text with generous spacing
                    explanation_text = f"   Rationale: {explanation}"
                    explanation_length = len(explanation_text)
                    
                    # More conservative estimate for font size 9 - use fewer chars per line to ensure enough space
                    explanation_chars_per_line = 40  # Very conservative estimate for font size 9
                    explanation_lines = max(1, explanation_length / explanation_chars_per_line)
                    
                    # Use even more generous line height for rationales
                    explanation_height = max(7, explanation_lines * 6)  # At least 7mm, 6mm per line
                    
                    # Add extra padding for longer explanations
                    if explanation_lines > 2:
                        explanation_height += 4  # Add 4mm extra padding for longer explanations
                    if explanation_lines > 4:
                        explanation_height += 4  # Additional padding for very long explanations
                    
                    # Add a small space before the explanation
                    pdf.ln(1)
                    
                    # Write the explanation with calculated height
                    pdf.multi_cell(180, explanation_height, explanation_text, 0, 'L')
                    pdf.set_font('DejaVu', '', 10)  # Reset font
                    pdf.ln(3)  # Add more space after the rationale
                
                if is_grade_item:
                    pdf.set_text_color(0, 0, 0)  # Reset to black
                else:
                    pdf.set_text_color(0, 0, 0)  # Reset to black
                    
            pdf.ln(5)
        
        # Detailed analysis section
        pdf.set_font('DejaVu', 'B', 14)
        pdf.cell(190, 10, 'Detailed Checklist Analysis', 0, 1, 'L')
        
        # Table header
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(140, 8, 'Checklist Item', 1, 0, 'L')
        pdf.cell(50, 8, 'Status', 1, 1, 'C')
        
        # Table content
        pdf.set_font('DejaVu', '', 10)
        for item in analysis_data['checklist_items']:
            # Get result details
            result = analysis_data['analysis_results'].get(item, {})
            is_present = result.get('present', False)
            is_grade_item = item in analysis_data['grade_table_items']
            
            # Improved cell height calculation for checklist items with better text wrapping
            y_position = pdf.get_y()
            
            # Calculate required height for the item text with more accurate estimation
            font_size = 10
            
            # Highlight grade table items with slightly different formatting
            if is_grade_item:
                pdf.set_font('DejaVu', 'B', font_size)
            else:
                pdf.set_font('DejaVu', '', font_size)
            
            # A simpler and more reliable approach: use a fixed character per line estimate,
            # but be generous with space allocation to prevent overlapping
            item_length = len(item)
            chars_per_line = 50  # Conservative estimate to ensure enough space
            estimated_lines = max(1, item_length / chars_per_line)
            
            # Set a generous row height based on the estimated number of lines
            # Use a larger multiplier to ensure enough space
            line_height = 5  # mm per line - generous spacing
            row_height = max(8, estimated_lines * line_height)  # Minimum 8mm
            
            # For very long items, add extra space to be safe
            if estimated_lines > 3:
                row_height += 5  # Add 5mm extra padding for long items
            
            # Draw the checklist item cell
            pdf.multi_cell(140, row_height, item, 1, 'L')
            
            # Position cursor for the status cell
            pdf.set_xy(pdf.get_x() + 140, y_position)
            
            # Color-code status
            if is_present:
                pdf.set_text_color(0, 128, 0)  # Green
            else:
                pdf.set_text_color(200, 0, 0)  # Red
                
            # Calculate the height that was actually used for the item
            status_height = pdf.get_y() - y_position
            
            # Make sure the status cell matches the height of the item cell
            pdf.cell(50, status_height, 'Present' if is_present else 'Missing', 1, 1, 'C')
            pdf.set_text_color(0, 0, 0)  # Reset to black
            
            # Include evidence if present (max 300 chars)
            if is_present:
                evidence = result.get('evidence', '')
                if evidence:
                    # Strip HTML tags for clean PDF text
                    evidence = re.sub(r'<[^>]*>', '', evidence)
                    if len(evidence) > 300:
                        evidence = evidence[:297] + '...'
                    
                    pdf.set_font('DejaVu', '', 8)
                    pdf.set_text_color(100, 100, 100)  # Gray
                    
                    # Add method information
                    method = result.get('method', 'pattern_matching').replace('_', ' ').title()
                    confidence = result.get('confidence', None)
                    confidence_str = f" (Confidence: {int(confidence * 100)}%)" if confidence else ""
                    
                    # Calculate height needed for evidence text to prevent overlap
                    evidence_text = f"Match via {method}{confidence_str}: {evidence}"
                    evidence_length = len(evidence_text)
                    
                    # Use a very conservative estimate of characters per line to ensure enough space
                    chars_per_line = 60  # Conservative estimate for font size 8
                    evidence_lines = max(1, evidence_length / chars_per_line)
                    
                    # Use generous line height for evidence text
                    line_height = 4  # mm per line for font size 8
                    evidence_height = max(6, evidence_lines * line_height)  # At least 6mm height
                    
                    # Add extra padding for longer evidence text
                    if evidence_lines > 4:
                        evidence_height += 4  # Add 4mm extra padding for long evidence
                    
                    # Write the evidence with calculated height
                    pdf.multi_cell(190, evidence_height, evidence_text, 0, 'L')
                    pdf.set_text_color(0, 0, 0)  # Reset to black
            
            # Add space between items
            pdf.ln(2)
        
        # Create one-page summary
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        # Add fonts
        base_path = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(base_path, 'static', 'fonts')
        pdf.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
        pdf.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
        
        # Title
        pdf.set_font('DejaVu', 'B', 16)
        pdf.cell(190, 10, 'Syllabus Sync Analysis Summary', 0, 1, 'C')
        
        # Overall Stats
        pdf.set_font('DejaVu', 'B', 12)
        pdf.ln(5)
        pdf.cell(190, 8, 'Overall Compliance', 0, 1, 'L')
        pdf.set_font('DejaVu', '', 10)
        
        total_items = len(analysis_data['checklist_items'])
        missing_items = len(analysis_data['missing_items'])
        present_items = total_items - missing_items
        compliance_rate = (present_items / total_items) * 100
        
        pdf.cell(95, 8, f'Total Items: {total_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'Compliance Rate: {compliance_rate:.1f}%', 1, 1, 'L')
        pdf.cell(95, 8, f'Items Present: {present_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'Items Missing: {missing_items}', 1, 1, 'L')
        
        # Critical Missing Items
        if missing_items > 0:
            pdf.ln(5)
            pdf.set_font('DejaVu', 'B', 12)
            pdf.cell(190, 8, 'Critical Missing Items', 0, 1, 'L')
            pdf.set_font('DejaVu', '', 10)
            
            # Focus on grade-related and policy-related missing items
            critical_items = [item for item in analysis_data['missing_items'] 
                            if any(term in item.lower() for term in ['grade', 'policy', 'exam', 'assessment'])]
            
            for item in critical_items[:5]:  # Show top 5 critical items
                pdf.multi_cell(190, 6, f"• {item}", 0, 'L')
        
        # Major Sections Analysis
        pdf.ln(5)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(190, 8, 'Major Sections Analysis', 0, 1, 'L')
        pdf.set_font('DejaVu', '', 10)
        
        sections = {
            'Grade Distribution': any('grade' in item.lower() for item in analysis_data['checklist_items']),
            'Course Policies': any('policy' in item.lower() for item in analysis_data['checklist_items']),
            'Learning Outcomes': any('outcome' in item.lower() for item in analysis_data['checklist_items']),
            'Contact Information': any('contact' in item.lower() for item in analysis_data['checklist_items'])
        }
        
        for section, present in sections.items():
            status = 'Complete' if present else 'Missing'
            color = 0 if present else 255
            pdf.set_text_color(color, 0 if present else 0, 0)
            pdf.cell(190, 8, f"{section}: {status}", 1, 1, 'L')
        
        pdf.set_text_color(0, 0, 0)
        
        # Recommendations
        if missing_items > 0:
            pdf.ln(5)
            pdf.set_font('DejaVu', 'B', 12)
            pdf.cell(190, 8, 'Key Recommendations', 0, 1, 'L')
            pdf.set_font('DejaVu', '', 10)
            pdf.multi_cell(190, 6, "1. Review and add all missing grade distribution components\n" +
                         "2. Ensure all course policies are clearly stated\n" +
                         "3. Add specific due dates and assessment details\n" +
                         "4. Include complete instructor contact information", 0, 'L')
        
        # Create temporary file and save
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_filename = temp_file.name
        temp_file.close()
        
        # Save PDF to temporary file
        pdf.output(temp_filename)
        
        # Read the PDF file into a BytesIO object
        pdf_buffer = io.BytesIO()
        with open(temp_filename, 'rb') as f:
            pdf_buffer.write(f.read())
        
        # Delete the temporary file
        os.unlink(temp_filename)
        
        # Reset the buffer position
        pdf_buffer.seek(0)
        
        # Send the PDF to the browser for viewing rather than downloading
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=False,
            download_name='syllabus_sync_report.pdf'
        )
        
    except Exception as e:
        logger.exception(f"Error generating PDF: {str(e)}")
        flash(f"Error generating PDF: {str(e)}")
        return redirect('/')

if __name__ == "__main__":
    # Configure server timeouts
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    
    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True,
        request_handler=WSGIRequestHandler
    )