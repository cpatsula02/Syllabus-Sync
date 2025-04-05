import os
import logging
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, send_file, jsonify
from werkzeug.utils import secure_filename
import document_processor
from fpdf import FPDF
import io
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', year=datetime.datetime.now().year)

@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    # Check if both files were submitted
    if 'checklist' not in request.files or 'outline' not in request.files:
        flash('Both checklist and course outline files are required.')
        return redirect(request.url)
    
    checklist_file = request.files['checklist']
    outline_file = request.files['outline']
    
    # Check if filenames are empty
    if checklist_file.filename == '' or outline_file.filename == '':
        flash('Please select both files')
        return redirect(request.url)
    
    # Check if files are allowed
    if (not allowed_file(checklist_file.filename) or 
        not allowed_file(outline_file.filename)):
        flash('Only PDF and DOCX files are allowed.')
        return redirect(request.url)
    
    # Get additional parameters
    api_attempts = request.form.get('api_attempts', '3')
    additional_context = request.form.get('additional_context', '')
    
    # Validate api_attempts
    try:
        api_attempts = int(api_attempts)
        if api_attempts < 1:
            api_attempts = 1
        elif api_attempts > 10:
            api_attempts = 10
    except ValueError:
        api_attempts = 3  # Default to 3 attempts if invalid
    
    # Log the parameters
    logging.info(f"Analysis with {api_attempts} API attempts")
    if additional_context:
        logging.info(f"Additional context provided: {len(additional_context)} characters")
    
    # Save files
    checklist_path = None
    outline_path = None
    
    try:
        checklist_filename = secure_filename(checklist_file.filename)
        outline_filename = secure_filename(outline_file.filename)
        
        checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], checklist_filename)
        outline_path = os.path.join(app.config['UPLOAD_FOLDER'], outline_filename)
        
        checklist_file.save(checklist_path)
        outline_file.save(outline_path)
        
        # Process the files and get results
        checklist_items, matching_results = document_processor.process_documents(
            checklist_path, outline_path, api_attempts=api_attempts, additional_context=additional_context)
        
        # Check if we have any results
        if not checklist_items:
            flash('No valid checklist items found. Please ensure your checklist document contains numbered or bulleted items.')
            return redirect(url_for('index'))
        
        # Store results in session for the results page
        session['checklist_items'] = checklist_items
        session['matching_results'] = matching_results
        
        # Store outline text for match details functionality
        try:
            outline_text = document_processor.extract_text(outline_path)
            session['outline_text'] = outline_text
        except Exception as text_error:
            logging.error(f"Error extracting outline text: {str(text_error)}")
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logging.error(f"Error processing files: {str(e)}")
        error_msg = str(e).lower()
        
        # Check for specific error messages and provide friendly responses
        if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
            flash('Our AI service is currently experiencing high demand. The analysis will be performed using traditional methods only.')
        elif "timeout" in error_msg:
            flash('Processing took too long. Try with smaller documents or wait a moment and try again.')
        else:
            flash(f'Error processing files: {str(e)}')
        
        return redirect(request.url)
    finally:
        # Clean up files after processing, even if there was an error
        try:
            if checklist_path and os.path.exists(checklist_path):
                os.remove(checklist_path)
            if outline_path and os.path.exists(outline_path):
                os.remove(outline_path)
        except Exception as cleanup_error:
            logging.error(f"Error cleaning up files: {str(cleanup_error)}")

def generate_pdf_report(checklist_items, matching_results):
    """Generate a PDF report with the analysis results"""
    pdf = FPDF()
    pdf.add_page()
    
    # Add University of Calgary logo
    # pdf.image("static/images/uofc_logo.png", x=10, y=8, w=30)
    
    # Set up fonts
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Syllabus Sync", ln=True, align="C")
    pdf.cell(0, 10, "University of Calgary", ln=True, align="C")
    pdf.cell(0, 10, "Course Outline Analysis Report", ln=True, align="C")
    
    # Add date
    pdf.set_font("Arial", "", 10)
    today = datetime.datetime.now().strftime("%B %d, %Y")
    pdf.cell(0, 10, f"Generated on: {today}", ln=True, align="R")
    
    # Calculate completion rate
    total_items = len(checklist_items)
    present_items = sum(1 for item in checklist_items 
                      if isinstance(matching_results.get(item), dict) and matching_results[item].get('present') 
                      or isinstance(matching_results.get(item), bool) and matching_results[item])
    missing_items = total_items - present_items
    completion_rate = int((present_items / total_items * 100) if total_items > 0 else 0)
    
    # Add summary info
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Analysis Summary", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Total Checklist Items: {total_items}", ln=True)
    pdf.cell(0, 8, f"Items Present: {present_items}", ln=True)
    pdf.cell(0, 8, f"Items Missing: {missing_items}", ln=True)
    pdf.cell(0, 8, f"Completion Rate: {completion_rate}%", ln=True)
    
    # Detailed checklist
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Detailed Analysis", ln=True)
    
    # Iterate through checklist items
    for i, item in enumerate(checklist_items, 1):
        # Determine if item is present
        is_present = False
        explanation = ""
        method = "traditional"
        
        if isinstance(matching_results.get(item), dict):
            is_present = matching_results[item].get('present', False)
            explanation = matching_results[item].get('explanation', '')
            method = matching_results[item].get('method', 'traditional')
        elif isinstance(matching_results.get(item), bool):
            is_present = matching_results[item]
            explanation = "Found in document" if is_present else "Not found in document"
        
        # Add item with status - use ASCII characters to avoid UTF-8 encoding issues
        status = "Present" if is_present else "Missing"
        status_marker = "+" if is_present else "X"
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 8, f"Item {i}: [{status_marker}] {status}", ln=True)
        
        # Word wrap for longer items
        pdf.set_font("Arial", "", 10)
        
        # Handle line wrapping for long text
        item_text = item
        lines = []
        
        while len(item_text) > 80:
            # Find a good breaking point
            break_point = item_text[:80].rfind(' ')
            if break_point == -1:
                break_point = 80
            
            lines.append(item_text[:break_point])
            item_text = item_text[break_point+1:]
        
        if item_text:
            lines.append(item_text)
        
        # Print the wrapped text
        for line in lines:
            # Ensure text is ASCII-compatible for FPDF
            safe_line = line.encode('ascii', 'replace').decode('ascii')
            pdf.cell(0, 6, f"    {safe_line}", ln=True)
        
        # Add explanation if available
        if explanation:
            # Ensure explanation is ASCII-compatible for FPDF
            safe_explanation = explanation.encode('ascii', 'replace').decode('ascii')
            pdf.set_font("Arial", "I", 9)
            pdf.cell(0, 6, f"    Note: {safe_explanation}", ln=True)
        
        pdf.ln(2)
    
    # Add recommendations
    if missing_items > 0:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Recommendations", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 8, "The course outline is missing some required items. Please review the items marked as missing above and include them in your revised outline to ensure compliance with university requirements.")
    else:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Recommendations", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 8, "The course outline meets all checklist requirements. No further action is needed.")
    
    # Return the PDF as bytes
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

@app.route('/results', methods=['GET'])
def results():
    # Get results from session
    checklist_items = session.get('checklist_items', [])
    matching_results = session.get('matching_results', {})
    
    if not checklist_items or not matching_results:
        flash('No results found. Please upload files again.')
        return redirect(url_for('index'))
    
    return render_template('results.html', 
                          checklist_items=checklist_items,
                          matching_results=matching_results,
                          year=datetime.datetime.now().year)
                          
# PDF download route
@app.route('/download-pdf')
def download_pdf():
    # Get results from session
    checklist_items = session.get('checklist_items', [])
    matching_results = session.get('matching_results', {})
    
    if not checklist_items or not matching_results:
        flash('No results found. Please upload files again.')
        return redirect(url_for('index'))
    
    # Generate the PDF
    pdf_output = generate_pdf_report(checklist_items, matching_results)
    
    # Return the PDF as a downloadable file
    return send_file(
        pdf_output, 
        as_attachment=True,
        download_name='course_outline_analysis.pdf',
        mimetype='application/pdf'
    )

# Error handlers
@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 16 MB.')
    return redirect(url_for('index'))

@app.route('/get-match-details')
def get_match_details():
    """Get match details for a checklist item in the document"""
    item = request.args.get('item', '')
    
    if not item:
        return jsonify({"found": False, "error": "No checklist item provided"})
    
    # Get the document text from the session
    outline_text = session.get('outline_text', '')
    if not outline_text:
        return jsonify({"found": False, "error": "No document text available"})
    
    # Use the find_matching_excerpt function to find a relevant excerpt
    try:
        from document_processor import find_matching_excerpt
        found, excerpt = find_matching_excerpt(item, outline_text)
        return jsonify({"found": found, "excerpt": excerpt})
    except Exception as e:
        return jsonify({"found": False, "error": str(e)})

@app.errorhandler(500)
def server_error(e):
    flash('An unexpected error occurred. Please try again.')
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
