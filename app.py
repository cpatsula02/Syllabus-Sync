import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import document_processor

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
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
    
    # Save files
    try:
        checklist_filename = secure_filename(checklist_file.filename)
        outline_filename = secure_filename(outline_file.filename)
        
        checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], checklist_filename)
        outline_path = os.path.join(app.config['UPLOAD_FOLDER'], outline_filename)
        
        checklist_file.save(checklist_path)
        outline_file.save(outline_path)
        
        # Process the files and get results
        checklist_items, matching_results = document_processor.process_documents(
            checklist_path, outline_path)
        
        # Store results in session for the results page
        session['checklist_items'] = checklist_items
        session['matching_results'] = matching_results
        
        # Clean up files after processing
        os.remove(checklist_path)
        os.remove(outline_path)
        
        return redirect(url_for('results'))
        
    except Exception as e:
        logging.error(f"Error processing files: {str(e)}")
        flash(f'Error processing files: {str(e)}')
        return redirect(request.url)

@app.route('/results')
def results():
    # Get results from session
    checklist_items = session.get('checklist_items', [])
    matching_results = session.get('matching_results', {})
    
    if not checklist_items or not matching_results:
        flash('No results found. Please upload files again.')
        return redirect(url_for('index'))
    
    return render_template('results.html', 
                          checklist_items=checklist_items,
                          matching_results=matching_results)

# Error handlers
@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 16 MB.')
    return redirect(url_for('index'))

@app.errorhandler(500)
def server_error(e):
    flash('An unexpected error occurred. Please try again.')
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
