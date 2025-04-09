from flask import Flask, request, render_template, jsonify, redirect, flash, session, send_file, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import io
import json
import logging
import re
import urllib.request
from datetime import datetime

# Import custom modules
from document_processor import process_documents, extract_text
from api_analysis import analyze_course_outline
from models import db, User, Document, Collaboration, Annotation, ChatMessage, AnalysisResult

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenAI integration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ENABLE_OPENAI = bool(OPENAI_API_KEY)  # Enable if API key is present

# Log OpenAI integration status
logger.info(f"OpenAI integration {'enabled' if ENABLE_OPENAI else 'disabled - no API key found'}")

# Initialize Flask app
app = Flask(__name__)

# App configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get('SESSION_SECRET', os.urandom(24))

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Global variables for analysis data
analysis_data = {
    'checklist_items': [],
    'analysis_results': {},
    'missing_items': [],
    'grade_table_items': [],
    'link_validation': None,
    'outline_filename': None,
    'additional_context': None
}

# Error handler for all exceptions
@app.errorhandler(Exception)
def handle_error(e):
    """
    Enhanced error handler that provides detailed, helpful error messages
    specifically for OpenAI API issues and other common errors.
    """
    error_message = str(e)
    error_type = type(e).__name__
    
    # Log detailed error information for debugging
    try:
        app.logger.error(f"CRITICAL ERROR: {error_type}: {error_message}")
        app.logger.error(f"Error handling request: {request.path} Method: {request.method}")
        
        if request.form:
            app.logger.error(f"Form data keys: {list(request.form.keys())}")
        if request.files:
            app.logger.error(f"Uploaded files: {list(request.files.keys())}")
        
        import traceback
        app.logger.error(f"Traceback: {traceback.format_exc()}")
    except Exception as logging_error:
        # Fail silently if we can't log - don't compound the error
        print(f"Unable to log error details: {str(logging_error)}")
    
    # Create a more user-friendly error message based on the error type
    user_message = "An error occurred while processing your request."
    
    try:
        # Check for specific API-related errors with improved detection
        if any(term in error_message.lower() for term in ["openai", "api key", "api error", "api call", "api request"]):
            user_message = "OpenAI API error: The system encountered an issue with the AI analysis. This could be due to connection problems or API limitations. Please try again with a smaller document."
        elif "format" in error_message.lower() and any(term in error_message.lower() for term in ["specifier", "string format", "f-string"]):
            user_message = "There was an internal formatting error in the analysis. The development team has been notified."
        elif any(term in error_message.lower() for term in ["timeout", "timed out", "time limit", "deadline", "read timeout", "socket timeout", "asyncio", "worker", "gunicorn", "worker timeout"]):
            user_message = "Analysis timeout error: The in-depth AI analysis is taking longer than expected. The system timeout has been increased to 5 minutes. Please try again - the system should now process your document properly. For very large documents, consider breaking them into smaller sections for better processing."
        elif any(term in error_message.lower() for term in ["memory", "ram", "buffer"]):
            user_message = "The system ran out of memory while processing your request. Please try a smaller document."
        elif any(term in error_message.lower() for term in ["file format", "parsing", "invalid file", "corrupt"]):
            user_message = "There was an error reading your document. Please ensure it's a valid PDF or Word document and try again."
        elif "json" in error_message.lower():
            user_message = "There was an error processing the AI response. Please try again or upload a different document."
        elif "socket" in error_message.lower() or "connection" in error_message.lower():
            user_message = "Connection error: The system experienced a network issue while processing your request. We've increased connection timeouts to 5 minutes. Please try again."
    except Exception as error_handling_error:
        # If error analysis itself fails, use a simple generic message
        print(f"Error during error analysis: {str(error_handling_error)}")
        user_message = "An unexpected error occurred. Please try again with a smaller document."
    
    try:
        # Safe template rendering with explicit defaults for all variables
        logger.info("Attempting to render index.html template with error message")
        return render_template(
            'index.html',
            error=user_message,
            checklist_items=[],  # Ensure required template variables are defined
            analysis_results={},
            missing_items=[],
            grade_table_items=[],
            valid_links=[],
            invalid_links=[],
            document_path="",
            document_text="",
            show_results=False
        ), 500
    except Exception as template_error:
        # Log detailed information about the template error
        logger.error(f"Template rendering failed: {str(template_error)}")
        logger.error(f"Template error traceback: {traceback.format_exc()}")
        
        # If even rendering the template fails, return a simple plain text response
        return f"Error: {user_message}", 500

# Utility Functions
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

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Input validation
        if not username or not email or not password:
            flash('Please fill in all fields')
            return redirect(url_for('register'))
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registering user: {str(e)}")
            flash('An error occurred during registration')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login successful!')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('login'))

# Collaboration Routes
@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's owned documents
    owned_documents = Document.query.filter_by(owner_id=current_user.id).all()
    
    # Get documents the user has access to (collaborations)
    collaborations = Collaboration.query.filter_by(user_id=current_user.id).all()
    collaboration_documents = [collab.document for collab in collaborations]
    
    return render_template(
        'dashboard.html',
        owned_documents=owned_documents,
        collaboration_documents=collaboration_documents
    )

@app.route('/document/<int:document_id>')
@login_required
def view_document(document_id):
    document = Document.query.get_or_404(document_id)
    
    # Check if user has access to this document
    if document.owner_id != current_user.id and not Collaboration.query.filter_by(
        document_id=document_id, user_id=current_user.id).first():
        flash('You do not have access to this document')
        return redirect(url_for('dashboard'))
    
    # Get annotations
    annotations = Annotation.query.filter_by(document_id=document_id).all()
    
    # Get analysis results if they exist
    analysis_result = AnalysisResult.query.filter_by(document_id=document_id).first()
    analysis_data = json.loads(analysis_result.results_json) if analysis_result else None
    
    # Get collaborators
    collaborators = Collaboration.query.filter_by(document_id=document_id).all()
    
    return render_template(
        'document.html',
        document=document,
        annotations=annotations,
        analysis_data=analysis_data,
        collaborators=collaborators
    )

@app.route('/document/<int:document_id>/add_collaborator', methods=['POST'])
@login_required
def add_collaborator(document_id):
    document = Document.query.get_or_404(document_id)
    
    # Check if user is the owner
    if document.owner_id != current_user.id:
        flash('Only the document owner can add collaborators')
        return redirect(url_for('view_document', document_id=document_id))
    
    username = request.form.get('username')
    access_level = request.form.get('access_level', 'viewer')
    
    # Find user by username
    user = User.query.filter_by(username=username).first()
    if not user:
        flash(f'User {username} not found')
        return redirect(url_for('view_document', document_id=document_id))
    
    # Check if already a collaborator
    existing_collab = Collaboration.query.filter_by(
        document_id=document_id, user_id=user.id).first()
    
    if existing_collab:
        # Update access level if different
        if existing_collab.access_level != access_level:
            existing_collab.access_level = access_level
            db.session.commit()
            flash(f'Updated access level for {username} to {access_level}')
    else:
        # Add new collaborator
        new_collab = Collaboration(
            document_id=document_id,
            user_id=user.id,
            access_level=access_level
        )
        db.session.add(new_collab)
        db.session.commit()
        flash(f'Added {username} as a collaborator with {access_level} access')
    
    return redirect(url_for('view_document', document_id=document_id))

@app.route('/document/<int:document_id>/remove_collaborator/<int:collab_id>', methods=['POST'])
@login_required
def remove_collaborator(document_id, collab_id):
    document = Document.query.get_or_404(document_id)
    
    # Check if user is the owner
    if document.owner_id != current_user.id:
        flash('Only the document owner can remove collaborators')
        return redirect(url_for('view_document', document_id=document_id))
    
    collaboration = Collaboration.query.get_or_404(collab_id)
    
    # Make sure the collaboration is for this document
    if collaboration.document_id != document_id:
        flash('Invalid collaboration')
        return redirect(url_for('view_document', document_id=document_id))
    
    removed_username = collaboration.user.username
    db.session.delete(collaboration)
    db.session.commit()
    
    flash(f'Removed {removed_username} as a collaborator')
    return redirect(url_for('view_document', document_id=document_id))

@app.route('/document/<int:document_id>/add_annotation', methods=['POST'])
@login_required
def add_annotation(document_id):
    document = Document.query.get_or_404(document_id)
    
    # Check if user has access to add annotations
    if document.owner_id != current_user.id:
        collab = Collaboration.query.filter_by(
            document_id=document_id, user_id=current_user.id).first()
        if not collab or collab.access_level not in ['annotator', 'editor']:
            flash('You do not have permission to add annotations')
            return redirect(url_for('view_document', document_id=document_id))
    
    text = request.form.get('text')
    position = request.form.get('position')  # JSON string with selection positions
    
    if not text or not position:
        flash('Annotation text and position are required')
        return redirect(url_for('view_document', document_id=document_id))
    
    # Create new annotation
    new_annotation = Annotation(
        document_id=document_id,
        user_id=current_user.id,
        text=text,
        position=position
    )
    
    db.session.add(new_annotation)
    db.session.commit()
    
    # Emit event to all users viewing this document
    socketio.emit(
        'new_annotation',
        {
            'id': new_annotation.id,
            'user_id': current_user.id,
            'username': current_user.username,
            'text': text,
            'position': position,
            'created_at': new_annotation.created_at.isoformat()
        },
        room=f'document_{document_id}'
    )
    
    return redirect(url_for('view_document', document_id=document_id))

# Original application routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
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
                        'is_grade_item': item in grade_table_items,
                        'triple_checked': result_data.get('triple_checked', False),
                        'second_chance': result_data.get('second_chance', False)
                    }
                    formatted_results.append(formatted_result)
                
                # Prepare analysis methods statistics
                analysis_methods = {}
                for item in checklist_items:
                    result = results.get(item, {})
                    method = result.get("method", "ai_general_analysis")
                    
                    if method in analysis_methods:
                        analysis_methods[method] += 1
                    else:
                        analysis_methods[method] = 1
                
                # Save document if user is logged in
                if current_user.is_authenticated:
                    # Create a new document
                    new_document = Document(
                        title=outline.filename,
                        file_path=outline_path,
                        content_text=outline_text,
                        owner_id=current_user.id,
                        checklist_text=checklist_text
                    )
                    db.session.add(new_document)
                    db.session.flush()  # Get the ID without committing
                    
                    # Save analysis results
                    analysis_json = json.dumps({
                        'checklist_items': checklist_items,
                        'results': results,
                        'missing_items': missing_items,
                        'grade_table_items': grade_table_items
                    })
                    
                    new_analysis = AnalysisResult(
                        document_id=new_document.id,
                        results_json=analysis_json
                    )
                    
                    db.session.add(new_analysis)
                    db.session.commit()
                    
                    flash(f'Document "{outline.filename}" analyzed and saved')
                    return redirect(url_for('view_document', document_id=new_document.id))
                
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
                    api_calls=api_attempts,
                    api_calls_made=api_attempts,
                    api_used=True,
                    analysis_methods=analysis_methods,
                    outline_filename=outline.filename
                )
                
            except Exception as api_error:
                logger.exception(f"API error during document processing: {str(api_error)}")
                raise
                
        except Exception as e:
            logger.exception(f"Error processing request: {str(e)}")
            raise
            
        finally:
            # Clean up temporary files
            if checklist_path and os.path.exists(checklist_path):
                try:
                    os.remove(checklist_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary checklist file: {str(e)}")
    
    return render_template('index.html')

@app.route('/get_match_details', methods=['POST'])
def get_match_details():
    """Get the matching excerpt for a checklist item"""
    if request.method == 'POST':
        item = request.form.get('item')
        if not item:
            return jsonify({'error': 'No item provided'}), 400
        
        result = analysis_data.get('analysis_results', {}).get(item, {})
        evidence = result.get('evidence', '')
        
        return jsonify({
            'evidence': evidence,
            'confidence': result.get('confidence', 0),
            'method': result.get('method', 'unknown')
        })
    
    return jsonify({'error': 'Invalid request method'}), 405

@app.route('/api/analyze', methods=['POST'])
def api_analyze_course_outline():
    """API endpoint for analyzing a course outline"""
    try:
        # Check if request has the appropriate content
        if request.files and 'outline' in request.files:
            # Handle file upload
            outline = request.files['outline']
            if outline.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Save file temporarily
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline.filename))
            outline.save(outline_path)
            
            # Extract text from file
            document_text = extract_text(outline_path)
            
            # Clean up file after extraction
            try:
                os.remove(outline_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")
        
        elif request.is_json and 'document_text' in request.json:
            # Handle JSON payload with document text
            document_text = request.json['document_text']
        else:
            return jsonify({'error': 'No document provided. Please upload a file or provide document text'}), 400
        
        # Perform analysis using the OpenAI-based function
        try:
            analysis_results = analyze_course_outline(document_text)
            return jsonify(analysis_results)
        except Exception as analysis_error:
            logger.exception(f"Error during API analysis: {str(analysis_error)}")
            return jsonify({'error': f'Analysis error: {str(analysis_error)}'}), 500
            
    except Exception as e:
        logger.exception(f"API request error: {str(e)}")
        return jsonify({'error': f'Request processing error: {str(e)}'}), 500

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        logger.info(f'Client connected: User {current_user.username}')
    else:
        logger.info('Anonymous client connected')

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        logger.info(f'Client disconnected: User {current_user.username}')
    else:
        logger.info('Anonymous client disconnected')

@socketio.on('join_document')
def handle_join_document(data):
    document_id = data.get('document_id')
    if not document_id:
        return
    
    room = f'document_{document_id}'
    join_room(room)
    
    # Notify others that user joined
    if current_user.is_authenticated:
        emit('user_joined', {
            'username': current_user.username,
            'user_id': current_user.id,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room, include_self=False)

@socketio.on('leave_document')
def handle_leave_document(data):
    document_id = data.get('document_id')
    if not document_id:
        return
    
    room = f'document_{document_id}'
    leave_room(room)
    
    # Notify others that user left
    if current_user.is_authenticated:
        emit('user_left', {
            'username': current_user.username,
            'user_id': current_user.id,
            'timestamp': datetime.utcnow().isoformat()
        }, room=room, include_self=False)

@socketio.on('new_chat_message')
def handle_new_chat_message(data):
    if not current_user.is_authenticated:
        return
    
    document_id = data.get('document_id')
    message_text = data.get('message')
    
    if not document_id or not message_text:
        return
    
    # Check if user has access to the document
    document = Document.query.get(document_id)
    if not document:
        return
    
    if document.owner_id != current_user.id and not Collaboration.query.filter_by(
        document_id=document_id, user_id=current_user.id).first():
        return
    
    # Save the message
    new_message = ChatMessage(
        user_id=current_user.id,
        document_id=document_id,
        message=message_text
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    # Broadcast to everyone in the room
    room = f'document_{document_id}'
    emit('chat_message', {
        'id': new_message.id,
        'username': current_user.username,
        'user_id': current_user.id,
        'message': message_text,
        'timestamp': new_message.timestamp.isoformat()
    }, room=room)

@socketio.on('annotation_updated')
def handle_annotation_updated(data):
    if not current_user.is_authenticated:
        return
    
    annotation_id = data.get('annotation_id')
    new_text = data.get('text')
    
    if not annotation_id or not new_text:
        return
    
    # Find the annotation
    annotation = Annotation.query.get(annotation_id)
    if not annotation:
        return
    
    # Check if user has permission to edit
    if annotation.user_id != current_user.id:
        document = Document.query.get(annotation.document_id)
        if not document or (document.owner_id != current_user.id and not Collaboration.query.filter_by(
            document_id=document.id, user_id=current_user.id, access_level='editor').first()):
            return
    
    # Update the annotation
    annotation.text = new_text
    annotation.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Broadcast the update
    room = f'document_{annotation.document_id}'
    emit('annotation_updated', {
        'id': annotation.id,
        'text': new_text,
        'updated_at': annotation.updated_at.isoformat(),
        'updated_by_username': current_user.username,
        'updated_by_id': current_user.id
    }, room=room)

@socketio.on('delete_annotation')
def handle_delete_annotation(data):
    if not current_user.is_authenticated:
        return
    
    annotation_id = data.get('annotation_id')
    if not annotation_id:
        return
    
    # Find the annotation
    annotation = Annotation.query.get(annotation_id)
    if not annotation:
        return
    
    document_id = annotation.document_id
    
    # Check if user has permission to delete
    if annotation.user_id != current_user.id:
        document = Document.query.get(document_id)
        if not document or (document.owner_id != current_user.id and not Collaboration.query.filter_by(
            document_id=document_id, user_id=current_user.id, access_level='editor').first()):
            return
    
    # Delete the annotation
    db.session.delete(annotation)
    db.session.commit()
    
    # Broadcast the deletion
    room = f'document_{document_id}'
    emit('annotation_deleted', {
        'id': annotation_id,
        'deleted_by_username': current_user.username,
        'deleted_by_id': current_user.id
    }, room=room)

# Create database tables before first request
@app.before_first_request
def create_tables():
    db.create_all()

# Run the application
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)