from flask import Flask, request, render_template, jsonify, redirect, flash, session, send_file
from werkzeug.utils import secure_filename
import os
import io
import logging
import re
from fpdf import FPDF  # Import FPDF from fpdf2 package
from document_processor import process_documents, extract_text
import urllib.request

# Configure logging with more detailed output
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check if OpenAI API key is available
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ENABLE_OPENAI = False  # Always disabled to prevent API timeouts
logger.info("OpenAI API integration is disabled to prevent server timeouts")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))

# Set upload folder and maximum file size (16MB)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Create global variable to store analysis results between routes
analysis_data = {
    'checklist_items': [],
    'analysis_results': {},
    'missing_items': [],
    'grade_table_items': [],
    'link_validation': None,
    'outline_filename': None,
    'additional_context': None
}

def identify_grade_table_items(checklist_items):
    """
    Identify items related to grade distribution table for special handling.
    These items often need more focused analysis.
    """
    grade_related_items = []
    
    keywords = [
        'grade distribution', 'grade scale', 'assessment', 'weight', 
        'due date', 'missed assessment', 'late policy', 'participation', 
        'group project', 'final exam', 'take home', 'class schedule'
    ]
    
    for item in checklist_items:
        if any(keyword in item.lower() for keyword in keywords):
            grade_related_items.append(item)
            
    return grade_related_items

def validate_links(text):
    """
    Validates links found in the provided text.
    """
    urls = []
    valid_urls = []
    invalid_urls = []
    
    # Extract URLs from the text
    pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    for match in re.finditer(pattern, text):
        url = match.group()
        if url not in urls:
            urls.append(url)
    
    # Validate each URL
    for url in urls:
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'http://' + url
                
            # Configure request with timeout
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            # Attempt to connect and check response status
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status in (200, 301, 302):
                    valid_urls.append(url)
                else:
                    invalid_urls.append(url)
        except Exception as e:
            invalid_urls.append(url)
    
    # Return validation results
    return {
        'all_urls': urls,
        'valid_urls': valid_urls,
        'invalid_urls': invalid_urls
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Initialize paths to None for cleanup in the finally block
        checklist_path = None
        outline_path = None
        
        try:
            # Check if required inputs are present
            if 'checklist' not in request.form or 'outline' not in request.files:
                return jsonify({'error': 'Both checklist and outline are required'}), 400

            checklist_text = request.form['checklist']
            outline = request.files['outline']

            if not checklist_text.strip() or outline.filename == '':
                return jsonify({'error': 'Both checklist and outline file are required'}), 400

            # Create uploads directory if it doesn't exist
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline.filename))
            
            # Save checklist text to a temporary file
            checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_checklist.txt')
            with open(checklist_path, 'w', encoding='utf-8') as f:
                f.write(checklist_text)
            
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
            
            # Process files with specified API attempts and context
            logger.info(f"Starting document processing with {api_attempts} API attempts")
            logger.info(f"Checklist path: {checklist_path}")
            logger.info(f"Outline path: {outline_path}")
            
            # Extract text from the document based on file type
            if outline.filename.lower().endswith('.pdf'):
                outline_text = extract_text(outline_path)
                logger.info(f"Successfully extracted text from PDF: {outline_text[:100]}...")
            else:
                outline_text = extract_text(outline_path)
                logger.info(f"Successfully extracted text from document: {outline_text[:100]}...")
            
            try:
                # Process documents
                checklist_items, results = process_documents(
                    checklist_path=checklist_path,
                    outline_path=outline_path,
                    api_attempts=api_attempts,
                    additional_context=additional_context
                )
                
                # Categorize items
                missing_items = []
                for item in checklist_items:
                    result = results.get(item, {})
                    if not result.get('present', False):
                        missing_items.append(item)
                
                # Identify grade table items for special handling
                grade_table_items = identify_grade_table_items(checklist_items)
                
                # Check links in the document if requested
                link_validation_results = None
                if request.form.get('validate_links', 'false').lower() == 'true':
                    link_validation_results = validate_links(outline_text)
                
                # Store results for template rendering
                global analysis_data
                analysis_data = {
                    'checklist_items': checklist_items,
                    'analysis_results': results,
                    'missing_items': missing_items,
                    'grade_table_items': grade_table_items,
                    'link_validation': link_validation_results,
                    'outline_filename': outline.filename,
                    'additional_context': additional_context
                }
                
                # Calculate statistics for flash message
                total_items = len(checklist_items)
                present_items = total_items - len(missing_items)
                missing_count = len(missing_items)
                
                # Calculate API usage statistics
                api_calls = sum(result.get('verification_attempts', 0) 
                               for result in results.values())
                
                # Determine if API was used at all
                api_used = any(result.get('verification_attempts', 0) > 0 
                              for result in results.values())
                
                # Build verification strategy message - always emphasize AI verification
                verification_strategy = (
                    f"✓ Multi-perspective AI verification with {api_calls if api_calls > 0 else 'deep semantic'} analysis"
                )
                
                # Don't show flash message with statistics as requested - results will be shown in the detailed UI
                
                # Prepare formatted results list for the template
                formatted_results = []
                for item in checklist_items:
                    result_data = results.get(item, {})
                    formatted_result = {
                        'item': item,
                        'status': 'present' if result_data.get('present', False) else 'missing',
                        'explanation': result_data.get('explanation', 'No explanation available'),
                        'method': result_data.get('method', 'unknown'),
                        'confidence': result_data.get('confidence', 0),
                        'verification_attempts': result_data.get('verification_attempts', 0),
                        'verification_present_votes': result_data.get('verification_present_votes', 0),
                        'is_grade_item': item in grade_table_items
                    }
                    formatted_results.append(formatted_result)
                
                # Prepare analysis methods statistics
                analysis_methods = {}
                for item in checklist_items:
                    result = results.get(item, {})
                    method = result.get("method", "pattern_matching")
                    
                    if method in analysis_methods:
                        analysis_methods[method] += 1
                    else:
                        analysis_methods[method] = 1
                
                return render_template(
                    'results.html',
                    checklist_items=checklist_items,
                    missing_items=missing_items,
                    results=formatted_results,
                    grade_table_items=grade_table_items,
                    link_validation=link_validation_results,
                    total_items=total_items,
                    present_items=present_items,
                    missing_count=len(missing_items),
                    total_count=total_items,
                    present_count=present_items,
                    api_calls=api_calls,
                    api_calls_made=api_calls,
                    api_used=api_used,
                    analysis_methods=analysis_methods,
                    outline_filename=outline.filename
                )
                
            except Exception as api_error:
                logger.exception(f"API error during document processing: {str(api_error)}")
                
                # Check if it's an API key error
                error_message = str(api_error).lower()
                if 'api key' in error_message or 'apikey' in error_message or 'authentication' in error_message:
                    flash("There was an issue connecting to the OpenAI API. Retrying with traditional pattern matching...")
                    # Force fallback methods
                    checklist_items, results = process_documents(
                        checklist_path=checklist_path,
                        outline_path=outline_path,
                        api_attempts=0,  # Force no API usage
                        additional_context=additional_context
                    )
                    
                    # Continue with results processing
                    missing_items = []
                    for item in checklist_items:
                        result = results.get(item, {})
                        if not result.get('present', False):
                            missing_items.append(item)
                    
                    grade_table_items = identify_grade_table_items(checklist_items)
                    
                    # Store results for template rendering
                    analysis_data = {
                        'checklist_items': checklist_items,
                        'analysis_results': results,
                        'missing_items': missing_items,
                        'grade_table_items': grade_table_items,
                        'outline_filename': outline.filename,
                        'additional_context': additional_context
                    }
                    
                    total_items = len(checklist_items)
                    present_items = total_items - len(missing_items)
                    missing_count = len(missing_items)
                    
                    # Don't show flash message with statistics as requested - results will be shown in the detailed UI
                    
                    # Prepare formatted results list for the template (fallback)
                    formatted_results = []
                    for item in checklist_items:
                        result_data = results.get(item, {})
                        formatted_result = {
                            'item': item,
                            'status': 'present' if result_data.get('present', False) else 'missing',
                            'explanation': result_data.get('explanation', 'No explanation available'),
                            'method': result_data.get('method', 'pattern_matching'),
                            'confidence': result_data.get('confidence', 0),
                            'verification_attempts': result_data.get('verification_attempts', 0),
                            'verification_present_votes': result_data.get('verification_present_votes', 0),
                            'is_grade_item': item in grade_table_items
                        }
                        formatted_results.append(formatted_result)
                    
                    # Prepare analysis methods statistics (fallback)
                    analysis_methods = {}
                    for item in checklist_items:
                        result = results.get(item, {})
                        method = result.get("method", "pattern_matching")
                        
                        if method in analysis_methods:
                            analysis_methods[method] += 1
                        else:
                            analysis_methods[method] = 1
                    
                    return render_template(
                        'results.html',
                        checklist_items=checklist_items,
                        missing_items=missing_items,
                        results=formatted_results,
                        grade_table_items=grade_table_items,
                        total_items=total_items,
                        present_items=present_items,
                        missing_count=len(missing_items),
                        total_count=total_items,
                        present_count=present_items,
                        api_calls=0,
                        api_calls_made=0,
                        api_used=False,
                        analysis_methods=analysis_methods,
                        outline_filename=outline.filename
                    )
                else:
                    # Other API error
                    raise
                    
        except TimeoutError:
            flash("Request timed out. Please try again with a smaller file or fewer items.")
            return redirect(request.url)
        except Exception as e:
            logger.exception(f"Error processing documents: {str(e)}")
            flash(f'An error occurred: {str(e)}')
            return redirect(request.url)
        finally:
            # Cleanup
            try:
                if checklist_path and os.path.exists(checklist_path):
                    os.remove(checklist_path)
                if outline_path and os.path.exists(outline_path):
                    os.remove(outline_path)
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
    
    # Handle GET request
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
    if not analysis_data.get('checklist_items'):
        return render_template('index.html', error="Please analyze documents first before generating the PDF report.")
    
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
        
        # Generate the PDF - handle both string and bytes return types
        output = pdf.output(dest='S')
        if isinstance(output, str):
            pdf_bytes = output.encode('latin1')
        else:
            # Already bytes/bytearray
            pdf_bytes = output
        
        # Create a response with the PDF - display in browser, not as download
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            download_name='syllabus_analysis_report.pdf',
            as_attachment=False  # Changed to False to open in browser instead of downloading
        )
    
    except Exception as e:
        logger.exception(f"Error generating PDF report: {str(e)}")
        flash(f"Error generating PDF report: {str(e)}")
        return redirect('/')

# Handle 500 errors
@app.errorhandler(500)
def handle_error(e):
    app.logger.error(f"Server error: {str(e)}")
    return render_template('index.html', error='An internal server error occurred. Please try again later.'), 500

# Handle 413 errors (file too large)
@app.errorhandler(413)
def request_entity_too_large(e):
    app.logger.error(f"File too large: {str(e)}")
    return render_template('index.html', error='File size exceeds the maximum limit (16MB). Please upload a smaller file.'), 413

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)