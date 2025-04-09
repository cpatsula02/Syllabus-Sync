from flask import Flask, request, render_template, jsonify, redirect, flash, session, send_file
from werkzeug.utils import secure_filename
import os
import io
import logging
import re
import socket
from fpdf import FPDF  # Import FPDF from fpdf2 package
from document_processor import process_documents, extract_text
import urllib.request
from api_analysis import analyze_course_outline

# Configure logging with more detailed output
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenAI integration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ENABLE_OPENAI = bool(OPENAI_API_KEY)  # Enable if API key is present

# Log OpenAI integration status
logger.info(f"OpenAI integration {'enabled' if ENABLE_OPENAI else 'disabled - no API key found'}")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get('SESSION_SECRET', 'dev_secret_key')

@app.errorhandler(Exception)
def handle_error(e):
    """
    Enhanced error handler that provides detailed, helpful error messages
    specifically for OpenAI API issues and other common errors.
    """
    error_message = str(e)
    app.logger.error(f"Unhandled error: {error_message}")
    
    # Create a more user-friendly error message based on the error type
    user_message = "An error occurred while processing your request."
    
    # Check for specific API-related errors
    if "openai" in error_message.lower() or "api key" in error_message.lower():
        user_message = "OpenAI API error: The system requires a valid OpenAI API key to function. Please ensure your API key is correctly set in the environment variables."
    elif "timeout" in error_message.lower():
        user_message = "The request timed out. Please try again with a smaller document or fewer checklist items."
    elif "memory" in error_message.lower():
        user_message = "The system ran out of memory while processing your request. Please try a smaller document."
    elif "file format" in error_message.lower() or "parsing" in error_message.lower():
        user_message = "There was an error reading your document. Please ensure it's a valid PDF or Word document and try again."
    
    return render_template(
        'index.html',
        error=user_message
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

def validate_links(text):
    """
    Validates links found in the provided text.
    """
    # Safety check - ensure text is a string
    if not isinstance(text, str):
        logger.warning(f"validate_links received non-string input: {type(text)}")
        return [], []

    url_pattern = r"(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})"
    urls = re.findall(url_pattern, text)
    valid_links = []
    invalid_links = []

    # Limit to first 5 links to prevent timeouts
    for url in urls[:5]:
        # Make sure URL starts with http:// or https://
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        try:
            # Set a short timeout to prevent long waits
            urllib.request.urlopen(url, timeout=3)
            valid_links.append(url)
        except Exception as e:
            logger.warning(f"Invalid link {url}: {str(e)}")
            invalid_links.append(url)

    # If there are more links than we checked, log it
    if len(urls) > 5:
        logger.info(f"Only checked 5 out of {len(urls)} links")

    return valid_links, invalid_links


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
            if 'checklist' not in request.form or 'outline' not in request.files:
                return jsonify({'error': 'Both checklist and outline are required'}), 400

            checklist_text = request.form['checklist']
            outline = request.files['outline']

            if not checklist_text.strip() or outline.filename == '':
                return jsonify({'error': 'Both checklist and outline file are required'}), 400

            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline.filename))

            # Save checklist text to a temporary file
            checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_checklist.txt')
            try:
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

                try:
                    # Process files with specified API attempts and context
                    logger.info(f"Starting document processing with {api_attempts} API attempts")
                    logger.info(f"Checklist path: {checklist_path}")
                    logger.info(f"Outline path: {outline_path}")

                    # Extract text from the document based on file type
                    if outline.filename.lower().endswith('.pdf'):
                        outline_text = extract_text(outline_path)
                    else:
                        with open(outline_path, 'r', encoding='utf-8') as file:
                            outline_text = file.read()

                    checklist_items, analysis_results = process_documents(
                        checklist_path, 
                        outline_path, 
                        api_attempts=api_attempts, 
                        additional_context=additional_context
                    )

                    # Validate links in the document
                    valid_links, invalid_links = validate_links(outline_text)

                    # Add link validation results to context
                    additional_context += f"\n\nDocument contains {len(valid_links)} valid and {len(invalid_links)} invalid links."

                    # Process results from OpenAI API exclusively - no pattern matching
                    results = analysis_results
                    
                    # Debug logging to understand the structure of results
                    app.logger.error(f"DEBUG INFO: Type of results is: {type(results)}")
                    app.logger.error(f"DEBUG INFO: results dict contains {len(results)} items")
                    
                    # Debug the structure of each key-value pair
                    for key, value in results.items():
                        app.logger.error(f"DEBUG: Processing key {key}, value type: {type(value)}")
                        
                        # Debug method field to ensure OpenAI API is being used
                        if isinstance(value, dict) and 'method' in value:
                            method = value.get('method', '')
                            app.logger.error(f"DEBUG: Item '{key}' used method: {method}")
                    
                    # Check if any results have the openai_api_error method
                    api_errors = [item for item, result in results.items() 
                                 if result.get('method') == 'openai_api_error']
                    
                    if api_errors:
                        # Extract the first error message
                        error_msg = results[api_errors[0]].get('explanation', 'Unknown OpenAI API error')
                        logger.error(f"OpenAI API error detected: {error_msg}")
                        flash(f"OpenAI API error: {error_msg}", 'error')
                    else:
                        logger.info("Successfully used OpenAI API for analysis")

                    # Update link validation results
                    for item in checklist_items:
                        if 'link' in item.lower() or 'url' in item.lower():
                            if invalid_links:
                                results[item] = {
                                    'present': False,
                                    'confidence': 0.9,
                                    'explanation': f'Found {len(invalid_links)} invalid links in document',
                                    'evidence': "Invalid links found: " + ", ".join(invalid_links[:3]),
                                    'method': 'link_validation'
                                }
                            else:
                                results[item] = {
                                    'present': True,
                                    'confidence': 0.9,
                                    'explanation': 'All links in document are valid',
                                    'evidence': "Valid links found: " + ", ".join(valid_links[:3]),
                                    'method': 'link_validation'
                                }

                    logger.info(f"Document processing complete. Found {len(checklist_items)} checklist items.")
                    if not checklist_items or len(checklist_items) == 0:
                        logger.error("No checklist items were extracted! This will cause issues.")
                        flash("Error: No checklist items could be extracted from the document. Please check the file format.")
                        return redirect(request.url)

                except Exception as api_error:
                    logger.exception(f"API error during document processing: {str(api_error)}")
                    error_message = str(api_error)

                    # Check if this is likely an API error and display appropriate message
                    if "openai" in error_message.lower() or "api" in error_message.lower():
                        flash(f"OpenAI API Error: {error_message}. Please verify your API key and try again.", "error")
                        return redirect(request.url)
                    else:
                        # Re-raise for other types of errors
                        raise

                if "error" in analysis_results:
                    flash(analysis_results["error"])
                    return redirect(request.url)

                # Identify grade table related items for special handling
                grade_table_items = identify_grade_table_items(checklist_items)
                logger.info(f"Identified {len(grade_table_items)} grade table related items")

                # Format results for template with enhanced data and strict duplicate prevention
                results = []
                present_count = 0
                missing_count = 0
                missing_items = []
                processed_items = set()  # Track processed items to prevent duplicates
                seen_normalized_items = set()  # Track normalized item text to catch near-duplicates

                for item in checklist_items:
                    # Skip if this item has already been processed
                    # Normalize item text for comparison (remove extra spaces, lowercase)
                    normalized_item = ' '.join(item.lower().split())
                    if normalized_item in seen_normalized_items:
                        continue
                    seen_normalized_items.add(normalized_item)

                    processed_items.add(item)  # Mark as processed
                    result = analysis_results.get(item, {})
                    is_present = result.get("present", False)
                    is_grade_item = item in grade_table_items

                    # Set status based on presence
                    status = "present" if is_present else "missing"
                    status = result.get("status", status)  # Allow override from analysis

                    result["status"] = status
                    if status == "present":
                        present_count += 1
                    elif status == "na":
                        # Don't count N/A items in missing or present
                        pass
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
                        "confidence": result.get("confidence", None),
                        "status": status
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
                    if os.path.exists(checklist_path):
                        os.remove(checklist_path)
                    if os.path.exists(outline_path):
                        os.remove(outline_path)
                except Exception as e:
                    app.logger.error(f"Error during cleanup: {str(e)}")

    # For GET requests, simply render the template
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
    try:
        # Get session data
        print("Starting PDF generation with detailed checklist table...")
        analysis_data = session.get('analysis_data', {})

        # Import the detailed checklist table module
        from detailed_checklist_table import add_detailed_checklist_table
        if not analysis_data or not analysis_data.get('checklist_items'):
            print("ERROR: No analysis data found in session")
            flash("No analysis data found. Please analyze a document first.")
            return redirect('/')

        import os
        import re
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
        # We don't need bold-italic font, so we'll skip it to avoid FPDF style type errors
        print("Skipping bold-italic font to avoid FPDF style errors")

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

        # Count the different statuses (present, missing, not applicable)
        total_items = len(analysis_data['checklist_items'])
        missing_items = len(analysis_data['missing_items'])

        # Count not applicable items
        na_items = 0
        for item in analysis_data['checklist_items']:
            result = analysis_data['analysis_results'].get(item, {})
            if result.get('status', '') == 'na':
                na_items += 1

        present_items = total_items - missing_items - na_items

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

        # Quick summary statistics table
        pdf.cell(95, 8, f'Total checklist items: {total_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'Items present: {present_items}', 1, 1, 'L')
        pdf.cell(95, 8, f'Items missing: {missing_items}', 1, 0, 'L')
        pdf.cell(95, 8, f'Items not applicable: {na_items}', 1, 1, 'L')
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
            status = result.get('status', 'present' if is_present else 'missing')

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
            if status == 'na':
                pdf.set_text_color(100, 100, 100)  # Gray for N/A
                status_text = 'N/A'
            elif status == 'present':
                pdf.set_text_color(0, 128, 0)  # Green for present
                status_text = 'Present'
            else:
                pdf.set_text_color(255, 0, 0)  # Red for missing
                status_text = 'Missing'

            pdf.rect(pdf.get_x(), y_position, 50, row_height)

            # Center status text vertically and horizontally
            pdf.set_xy(pdf.get_x() + (50 - pdf.get_string_width(status_text)) / 2, y_position + (row_height - 5) / 2)
            pdf.cell(50, 5, status_text, 1, 1, 'C')
            pdf.set_text_color(0, 0, 0)  # Reset to black

            # Include evidence if present (max 300 chars)
            if is_present or status == 'na':
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

        # Add the detailed checklist table with full item descriptions
        print("Adding detailed checklist table...")

        # Read the detailed checklist file
        detailed_checklist_items = []
        try:
            print("Opening enhanced_checklist.txt file...")
            with open('enhanced_checklist.txt', 'r') as file:
                content = file.read().strip()
                print(f"Read {len(content)} characters from the file")
                # Split by numbered list items (number followed by a period at the start of a line)
                detailed_checklist_items = []
                lines = content.split('\n')
                print(f"Split content into {len(lines)} lines")
                current_item = ""

                for line in lines:
                    # If the line starts with a number and period (item number), it's a new item
                    if re.match(r'^\d+\.', line):
                        # Save the previous item if it exists
                        if current_item:
                            detailed_checklist_items.append(current_item.strip())
                            print(f"Added item: {current_item[:50]}...")
                        current_item = line
                        print(f"Started new item: {line[:50]}...")
                    else:
                        # Continue with the current item
                        current_item += "\n" + line

                # Add the last item
                if current_item:
                    detailed_checklist_items.append(current_item.strip())
                    print(f"Added final item: {current_item[:50]}...")

                print(f"Loaded {len(detailed_checklist_items)} detailed checklist items")
                if detailed_checklist_items:
                    print(f"First item: {detailed_checklist_items[0][:100]}")
                    print(f"Last item: {detailed_checklist_items[-1][:100]}")

            # Add the detailed checklist table to the PDF
            print("Calling add_detailed_checklist_table...")
            add_detailed_checklist_table(pdf, analysis_data, detailed_checklist_items)
            print("Successfully added detailed checklist table")
        except Exception as e:
            print(f"Error adding detailed checklist table: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # Continue with the rest of the PDF even if this fails

        # Add a new page for the Quick Overview
        pdf.add_page()
        pdf.set_font('DejaVu', 'B', 16)
        pdf.cell(190, 10, 'Course Outline Compliance - Quick Overview', 0, 1, 'C')
        pdf.ln(5)

        # Header for items table
        pdf.set_font('DejaVu','B', 10)
        pdf.cell(150, 8, 'Checklist Item', 1, 0, 'L')
        pdf.cell(30, 8, 'Status', 1, 1, 'C')

        # Remove duplicates while preserving order
        seen = set()
        unique_checklist_items = []
        for item in analysis_data['checklist_items']:
            if item not in seen:
                seen.add(item)
                unique_checklist_items.append(item)

        # List items with status
        pdf.set_font('DejaVu', '', 9)
        for item in unique_checklist_items:
            # Get the status from results
            result = analysis_data['analysis_results'].get(item, {})
            status = result.get('status', 'present' if item not in analysis_data['missing_items'] else 'missing')

            # Use a very conservative estimate ofcharacters per line to ensure enough space
            chars_per_line = 60  # Conservative estimate for better readability
            item_length = len(item)
            lines_needed = max(1, item_length / chars_per_line)

            # Increase minimum row height and add padding for multi-line items
            base_height = 8  # Minimum height in mm
            line_height = 5  # Height per line in mm
            padding = 2     # Extra padding in mm

            row_height = max(base_height, (lines_needed * line_height) + padding)

            # Save position for status cell
            x_pos = pdf.get_x()
            y_pos = pdf.get_y()

            # Add box around item with proper spacing
            pdf.rect(x_pos, y_pos, 150, row_height)

            # Print item with padding
            pdf.set_xy(x_pos + 2, y_pos + 2)  # Add internal padding
            pdf.multi_cell(146, line_height, item.strip(), 0, 'L')

            # Print status in its own box
            pdf.set_xy(x_pos + 150, y_pos)

            # Set color based on status
            if status == 'na':
                pdf.set_text_color(100, 100, 100)  # Gray for N/A
                status_text = 'N/A'
            elif status == 'present':
                pdf.set_text_color(0, 128, 0)  # Green for present
                status_text = 'Present'
            else:
                pdf.set_text_color(255, 0, 0)  # Red for missing
                status_text = 'Missing'

            pdf.rect(x_pos + 150, y_pos, 30, row_height)

            # Center status text vertically and horizontally
            pdf.set_xy(x_pos + 150 + (30 - pdf.get_string_width(status_text)) / 2, y_pos + (row_height - 5) / 2)
            pdf.cell(30, 5, status_text, 0, 1, 'C')
            pdf.set_text_color(0, 0, 0)

            # Add spacing between items
            pdf.set_xy(x_pos, y_pos + row_height + 2)

            # Check for new page
            if pdf.get_y() > 250:
                pdf.add_page()
                pdf.set_font('DejaVu', 'B', 10)
                pdf.cell(150, 8, 'Checklist Item', 1, 0, 'L')
                pdf.cell(30, 8, 'Status', 1, 1, 'C')
                pdf.set_font('DejaVu', '', 9)

        # Add summary at bottom of last page
        pdf.ln(10)
        pdf.set_font('DejaVu', 'B', 10)
        total_items = len(unique_checklist_items)
        present_items = sum(1 for item in unique_checklist_items if analysis_data['analysis_results'].get(item, {}).get('status', '') == 'present' or 
                           (item not in analysis_data['missing_items'] and analysis_data['analysis_results'].get(item, {}).get('status', '') != 'na'))
        na_items = sum(1 for item in unique_checklist_items if analysis_data['analysis_results'].get(item, {}).get('status', '') == 'na')
        missing_items = total_items - present_items - na_items

        pdf.cell(63, 8, f'Total Items: {total_items}', 1, 0, 'L')
        pdf.cell(63, 8, f'Present: {present_items}', 1, 0, 'L')
        pdf.cell(64, 8, f'Missing: {missing_items} / N/A: {na_items}', 1, 1, 'L')

        # Add summary at the end
        pdf.add_page()
        pdf.set_font('DejaVu', 'B', 16)
        pdf.cell(190, 10, 'Compliance Summary Report', 0, 1, 'C')
        pdf.ln(3)

        # Add summary explanation
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(190, 5, 'This report summarizes the compliance status of the course outline against the University of Calgary checklist requirements. The compliance rate is calculated only for applicable items, excluding those marked as N/A.', 0, 'L')
        pdf.ln(5)

        # Count different statuses
        present_count = sum(1 for item in unique_checklist_items if analysis_data['analysis_results'].get(item, {}).get('status', '') == 'present' or 
                           (item not in analysis_data['missing_items'] and analysis_data['analysis_results'].get(item, {}).get('status', '') != 'na'))
        na_count = sum(1 for item in unique_checklist_items if analysis_data['analysis_results'].get(item, {}).get('status', '') == 'na')
        missing_count = total_items - present_count - na_count

        # Calculate compliance percentage (excluding N/A items)
        applicable_items = total_items - na_count
        compliance_percentage = (present_count / applicable_items * 100) if applicable_items > 0 else 100

        # Create a professional summary section
        # Draw header
        pdf.set_fill_color(220, 230, 241)  # Light blue background
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(190, 12, 'Course Outline Compliance Statistics', 1, 1, 'C', True)

        # Create a table for statistics
        pdf.set_font('DejaVu', '', 10)

        # Row 1: Total and Applicable
        pdf.set_fill_color(245, 245, 245)  # Light gray
        pdf.cell(95, 10, f'Total Requirements: {total_items}', 1, 0, 'L', True)
        pdf.cell(95, 10, f'Applicable Requirements: {applicable_items}', 1, 1, 'L', True)

        # Row 2: Present and Missing
        pdf.set_fill_color(255, 255, 255)  # White
        pdf.cell(95, 10, f'Requirements Present: {present_count}', 1, 0, 'L', True)
        pdf.cell(95, 10, f'Requirements Missing: {missing_count}', 1, 1, 'L', True)

        # Row 3: N/A and Rate
        pdf.set_fill_color(245, 245, 245)  # Light gray
        pdf.cell(95, 10, f'Requirements N/A: {na_count}', 1, 0, 'L', True)

        # Set compliance rate color based on percentage
        if compliance_percentage >= 90:
            pdf.set_text_color(0, 128, 0)  # Green for high compliance
        elif compliance_percentage >= 70:
            pdf.set_text_color(255, 140, 0)  # Orange for medium compliance
        else:
            pdf.set_text_color(255, 0, 0)  # Red for low compliance

        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(95, 10, f'Compliance Rate: {compliance_percentage:.1f}%', 1, 1, 'L', True)
        pdf.set_text_color(0, 0, 0)  # Reset to black

        # Add visual compliance meter
        pdf.ln(10)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(190, 10, 'Visual Compliance Indicator', 0, 1, 'L')

        # Draw progress bar background
        bar_width = 180
        bar_height = 20
        pdf.set_fill_color(220, 220, 220)  # Light gray background
        pdf.rect(15, pdf.get_y(), bar_width, bar_height, 'F')  # 'F' means filled rectangle

        # Draw progress bar fill based on compliance percentage
        filled_width = min(bar_width * (compliance_percentage / 100), bar_width)

        # Set color based on percentage
        if compliance_percentage >= 90:
            pdf.set_fill_color(0, 180, 0)  # Green for high compliance
        elif compliance_percentage >= 70:
            pdf.set_fill_color(255, 140, 0)  # Orange for medium compliance
        else:
            pdf.set_fill_color(255, 0, 0)  # Red for low compliance

        pdf.rect(15, pdf.get_y(), filled_width, bar_height, 'F')  # 'F' means filled rectangle

        # Add percentage text on top of the bar
        pdf.set_font('DejaVu', 'B', 12)
        pdf.set_text_color(255, 255, 255)  # White text

        # Center the text on the filled portion if it's wide enough
        if filled_width > 40:
            pdf.set_xy(15 + (filled_width / 2) - 20, pdf.get_y() + (bar_height / 2) - 3)
            pdf.cell(40, 6, f'{compliance_percentage:.1f}%', 0, 0, 'C')
        else:
            # Place text after the bar if too narrow
            pdf.set_xy(15 + bar_width + 5, pdf.get_y() + (bar_height / 2) - 3)
            pdf.set_text_color(0, 0, 0)  # Black text
            pdf.cell(40, 6, f'{compliance_percentage:.1f}%', 0, 0, 'L')

        pdf.set_text_color(0, 0, 0)  # Reset to black

        # Add compliance recommendation
        pdf.ln(30)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(190, 10, 'Compliance Recommendation:', 0, 1, 'L')

        recommendation_text = ""
        if compliance_percentage >= 90:
            recommendation_text = "This course outline is highly compliant with the University of Calgary's requirements. Minor improvements may still be beneficial for the few missing items."
        elif compliance_percentage >= 70:
            recommendation_text = "This course outline meets most of the University of Calgary's requirements, but needs attention to several missing items. Please review the missing requirements and update accordingly."
        else:
            recommendation_text = "This course outline requires significant improvements to meet the University of Calgary's requirements. Please carefully review all missing items and update the outline accordingly."

        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(190, 5, recommendation_text, 0, 'L')

        # Add a note about N/A items
        if na_count > 0:
            pdf.ln(5)
            pdf.set_font('DejaVu', 'I', 10)
            pdf.multi_cell(190, 5, f"Note: {na_count} items were marked as Not Applicable and excluded from the compliance rate calculation. These may include requirements that don't apply to this specific course, such as group work or final exam details for courses without these components.", 0, 'L')

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

        # Send the PDF to the browser with download option
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

@app.route('/get-enhanced-checklist')
def get_enhanced_checklist():
    """Serve the simplified checklist items from the file"""
    try:
        with open('simplified_checklist.txt', 'r') as file:
            checklist_content = file.read()
        return checklist_content
    except Exception as e:
        logger.error(f"Error loading simplified checklist: {str(e)}")
        return "Error loading checklist", 500

@app.route('/api/analyze-course-outline', methods=['POST'])
def api_analyze_course_outline():
    """
    API endpoint that analyzes a course outline against the 26 hardcoded checklist items.
    
    Expected request format:
    - multipart/form-data with a file field named 'outline'
    OR
    - application/json with a 'document_text' field containing the text of the course outline
    
    Returns:
    - A JSON array of 26 items, each with:
      - present: boolean indicating if the item is present in the outline
      - confidence: number between 0.0 and 1.0
      - explanation: brief explanation
      - evidence: direct quote from the outline, or empty string if not found
      - method: always "ai_general_analysis"
    """
    try:
        document_text = ""
        
        # Check if the request contains a file
        if 'outline' in request.files:
            outline = request.files['outline']
            
            if outline.filename == '':
                return jsonify({'error': 'No file selected'}), 400
                
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline.filename))
            outline.save(outline_path)
            
            # Extract text from the file
            document_text = extract_text(outline_path)
            
        # Check if the request contains JSON data with document_text
        elif request.is_json and 'document_text' in request.json:
            document_text = request.json['document_text']
        else:
            return jsonify({'error': 'No outline file or document text provided'}), 400
            
        if not document_text.strip():
            return jsonify({'error': 'Empty document text'}), 400
            
        # Perform the analysis
        logger.info("Starting course outline analysis via API")
        results = analyze_course_outline(document_text)
        logger.info(f"Analysis complete, returned {len(results)} results")
        
        return jsonify(results)
        
    except Exception as e:
        logger.exception(f"Error analyzing course outline: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 5000))
        sock.close()
        print("Port 5000 is available")
        print("Starting Flask server on port 5000...")
        app.run(host="0.0.0.0", port=5000, threaded=True)
    except socket.error:
        print("Port 5000 is already in use")
    except Exception as e:
        print(f"Failed to start server: {str(e)}")