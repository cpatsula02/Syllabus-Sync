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
    Returns lists of valid and invalid links.
    Used for checking the 26th checklist item about functional web links.
    """
    # Safety check - ensure text is a string
    if not isinstance(text, str):
        logger.warning(f"validate_links received non-string input: {type(text)}")
        return [], []

    # Improved URL pattern to catch more variants
    url_pattern = r"(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})"
    urls = re.findall(url_pattern, text)
    
    # Remove duplicates while preserving order
    unique_urls = []
    for url in urls:
        if url not in unique_urls:
            unique_urls.append(url)
    
    valid_links = []
    invalid_links = []

    # Limit to first 10 links to prevent timeouts
    max_links_to_check = 10
    for url in unique_urls[:max_links_to_check]:
        # Make sure URL starts with http:// or https://
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        try:
            # Set a short timeout to prevent long waits
            urllib.request.urlopen(url, timeout=3)
            valid_links.append(url)
            logger.info(f"Valid link found: {url}")
        except Exception as e:
            logger.warning(f"Invalid link {url}: {str(e)}")
            invalid_links.append(url)

    # If there are more links than we checked, log it
    if len(unique_urls) > max_links_to_check:
        logger.info(f"Only checked {max_links_to_check} out of {len(unique_urls)} unique links")

    logger.info(f"Link validation complete: {len(valid_links)} valid, {len(invalid_links)} invalid links")
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
                    
                    # Check if any results have an error method
                    api_errors = [item for item, result in results.items() 
                                 if result.get('method') == 'ai_general_analysis' and 'error' in result.get('explanation', '').lower()]
                    
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
                                    'method': 'ai_general_analysis'
                                }
                            else:
                                results[item] = {
                                    'present': True,
                                    'confidence': 0.9,
                                    'explanation': 'All links in document are valid',
                                    'evidence': "Valid links found: " + ", ".join(valid_links[:3]),
                                    'method': 'ai_general_analysis'
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
                        "method": result.get("method", "ai_general_analysis"),
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
                    method = result.get("method", "ai_general_analysis")

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
            'method': result.get('method', 'ai_general_analysis'),
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
    """Generate a professional PDF report of the analysis results"""
    try:
        # Get session data
        logger.info("Starting professional PDF generation...")
        analysis_data = session.get('analysis_data', {})

        if not analysis_data or not analysis_data.get('checklist_items'):
            logger.warning("No analysis data found in session")
            flash("No analysis data found. Please analyze a document first.")
            return redirect('/')

        # Import the professional PDF generator
        from professional_pdf_generator import generate_pdf_report
        
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
      - explanation: brief explanation (prefixed with "[2nd Analysis]" if from second-chance analysis)
      - evidence: direct quote from the outline, or empty string if not found
      - method: always "ai_general_analysis"
      - triple_checked: boolean indicating if the item was analyzed using multiple passes (always true)
      - second_chance: boolean indicating if this result came from a second-chance analysis after an initial failure
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