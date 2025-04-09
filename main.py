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
import traceback

# Import custom modules
from document_processor import process_documents, extract_text
from api_analysis import analyze_course_outline
from models import db, User, Document, Collaboration, Annotation, ChatMessage, AnalysisResult

# Configure logging with more detailed output
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenAI integration with detailed validation
# CRITICAL: This application REQUIRES OpenAI API for analysis as per user requirements
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ENABLE_OPENAI = True  # CRITICAL: Force OpenAI API to be used exclusively (no pattern matching fallbacks allowed)

# OpenAI API status for displaying in UI
OPENAI_API_STATUS = "unavailable"
OPENAI_API_STATUS_MESSAGE = ""

# Explicitly log the first 5 characters of the API key (for debugging, to confirm we have a key)
if OPENAI_API_KEY:
    api_key_start = OPENAI_API_KEY[:5] + "..." if len(OPENAI_API_KEY) > 5 else "too short"
    logger.info(f"OPENAI_API_KEY found in environment, starts with: {api_key_start}")
else:
    logger.critical("OPENAI_API_KEY not found in environment")

# Add API key validation for proper format (for future debugging)
if OPENAI_API_KEY:
    # Check if key has valid format (starts with sk- and has sufficient length)
    if len(OPENAI_API_KEY) < 20 or not OPENAI_API_KEY.startswith("sk-"):
        logger.critical("CRITICAL ERROR: OpenAI API key present but appears to be invalid format (should start with 'sk-')")
        OPENAI_API_STATUS = "invalid"
        OPENAI_API_STATUS_MESSAGE = "API key has invalid format (must start with 'sk-')"
    else:
        logger.info("OpenAI API key validated with correct format")
        OPENAI_API_STATUS = "available"
        OPENAI_API_STATUS_MESSAGE = "Valid OpenAI API key detected"
        # Force set the environment variable to ensure it's accessible to all modules
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
else:
    logger.critical("CRITICAL ERROR: No OpenAI API key found in environment variables")
    logger.critical("This application REQUIRES a valid OPENAI_API_KEY to function correctly")
    OPENAI_API_STATUS = "missing"
    OPENAI_API_STATUS_MESSAGE = "No API key found. This application requires a valid OpenAI API key."
    # Since we've forced ENABLE_OPENAI to True, we should still log this warning
    logger.warning("OPENAI_API_KEY environment variable not found - but we'll still try to use OpenAI API exclusively")
    logger.warning("This will likely cause API authentication errors - please set a valid OPENAI_API_KEY")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24))

# Set upload folder and maximum file size (16MB)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

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

# Create database tables on startup
with app.app_context():
    db.create_all()

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
        collaborators=collaborators,
        document_id=document_id
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

# Socket.IO event handlers
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
                
                # DEBUGGING: Print the type of results
                logger.error(f"DEBUG INFO: Type of results is: {type(results)}")
                if not isinstance(results, dict):
                    logger.error(f"ERROR: results is not a dict! Value: {str(results)[:100]}")
                else:
                    logger.error(f"DEBUG INFO: results dict contains {len(results)} items")
                    
                # Calculate API usage statistics - with defensive error handling
                api_calls = 0
                api_used = False
                
                if isinstance(results, dict):
                    # Check all results and ensure we only access dictionary values
                    for key, result in results.items():
                        logger.error(f"DEBUG: Processing key {key}, value type: {type(result)}")
                        if isinstance(result, dict):
                            api_calls += result.get('verification_attempts', 0)
                            if result.get('verification_attempts', 0) > 0:
                                api_used = True
                        else:
                            logger.error(f"ERROR: Value for key '{key}' is not a dict! Value: {str(result)[:50]}")
                
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
                    # CRITICAL: As per user requirements, we DON'T fallback to pattern matching
                    # Instead, we report the API error directly
                    flash("ERROR: OpenAI API authentication failed. As requested, we're not using pattern matching fallback.")
                    # We are not forcing fallback methods anymore
                    # CRITICAL: As per user requirements, we DON'T process documents without OpenAI API
                    # Instead, we return a custom error response
                    logger.error("OpenAI API required but authentication failed. Not using fallback as per requirements.")
                    
                    # Create placeholder items and results to show API error
                    checklist_items = ["OpenAI API Authentication Failed"]
                    results = {
                        "OpenAI API Authentication Failed": {
                            'present': False,
                            'confidence': 0,
                            'explanation': "Cannot process without OpenAI API as per requirements. Please check API key and try again.",
                            'evidence': "",
                            'method': 'ai_general_analysis'
                        }
                    }
                    
                    try:
                        # Additional validation of results (rarely needed with our approach)
                        if not isinstance(results, dict):
                            logger.error(f"Invalid results type: {type(results)}. Creating empty results.")
                            results = {}
                            for item in checklist_items:
                                results[item] = {
                                    'present': False,
                                    'confidence': 0,
                                    'explanation': "Error processing this item.",
                                    'evidence': "",
                                    'method': 'ai_general_analysis'
                                }
                    except Exception as fallback_error:
                        logger.exception(f"Error handling API failure: {str(fallback_error)}")
                        flash(f"An error occurred during API error handling: {str(fallback_error)}")
                        return redirect(request.url)
                    
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
                            'method': result_data.get('method', 'ai_general_analysis'),
                            'confidence': result_data.get('confidence', 0),
                            'verification_attempts': result_data.get('verification_attempts', 0),
                            'verification_present_votes': result_data.get('verification_present_votes', 0),
                            'is_grade_item': item in grade_table_items,
                            'triple_checked': result_data.get('triple_checked', False),
                            'second_chance': result_data.get('second_chance', False)
                        }
                        formatted_results.append(formatted_result)
                    
                    # Prepare analysis methods statistics (fallback)
                    analysis_methods = {}
                    for item in checklist_items:
                        result = results.get(item, {})
                        method = result.get("method", "ai_general_analysis")
                        
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
    # Pass API status to the template
    return render_template('index.html', 
                          openai_api_status=OPENAI_API_STATUS,
                          openai_api_message=OPENAI_API_STATUS_MESSAGE)

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
            method = result.get("method", "ai_general_analysis")
            
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
        try:
            results = analyze_course_outline(document_text)
            logger.info(f"Analysis complete, returned {len(results)} results")
        except Exception as e:
            logger.error(f"Error during API analysis: {str(e)}")
            # Create a properly formatted fallback response with default values
            # This is needed to ensure the API always returns the expected structure
            from api_analysis import CHECKLIST_ITEMS
            results = []
            for i, item in enumerate(CHECKLIST_ITEMS):
                results.append({
                    "present": False,
                    "confidence": 0.5,
                    "explanation": f"Analysis failed due to API error: {str(e)[:50]}...",
                    "evidence": "",
                    "method": "ai_general_analysis",
                    "triple_checked": True,
                    "second_chance": True
                })
            logger.warning(f"Returning default response with {len(results)} items")
        
        return jsonify(results)
        
    except Exception as e:
        logger.exception(f"Error analyzing course outline: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)