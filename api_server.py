from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import io
import logging
import re
import socket
from document_processor import extract_text
from api_analysis import analyze_course_outline

# Configure logging with more detailed output
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure OpenAI integration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    api_key_start = OPENAI_API_KEY[:5] + "..." if len(OPENAI_API_KEY) > 5 else "too short"
    logger.info(f"OPENAI_API_KEY found in api_server.py, starts with: {api_key_start}")
else:
    logger.warning("OPENAI_API_KEY not found in environment variables")

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = os.environ.get('SESSION_SECRET', 'dev_secret_key')

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

@app.route('/', methods=['GET'])
def index():
    """Simple welcome page for the API"""
    return """
    <html>
        <head>
            <title>Course Outline Analysis API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #2c3e50; }
                code { background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px; }
                pre { background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto; }
                .endpoint { margin-top: 20px; }
                .param { margin-left: 20px; }
            </style>
        </head>
        <body>
            <h1>Course Outline Analysis API</h1>
            <p>This API analyzes course outlines against 26 standard University of Calgary checklist items.</p>
            
            <div class="endpoint">
                <h2>Endpoint</h2>
                <code>POST /api/analyze-course-outline</code>
                
                <h3>Option 1: Send document text as JSON</h3>
                <pre>
curl -X POST http://localhost:5000/api/analyze-course-outline \\
  -H "Content-Type: application/json" \\
  -d '{
    "document_text": "COURSE OUTLINE\\nPSYC 201 - Introduction to Psychology\\n\\nInstructor: Dr. Smith\\nEmail: smith@ucalgary.ca..."
  }'</pre>
                
                <h3>Option 2: Upload a file</h3>
                <pre>
curl -X POST http://localhost:5000/api/analyze-course-outline \\
  -F "outline=@/path/to/course_outline.pdf"</pre>
                
                <h3>Response Format</h3>
                <p>The API returns a JSON array of 26 objects, one for each checklist item.</p>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    # Start the API server
    port = 5001  # Use a different port to avoid conflicts with the main app
    
    try:
        # Check if the port is available
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", port))
        sock.close()
        print(f"Port {port} is available")
        print(f"Starting API server on port {port}...")
        app.run(host="0.0.0.0", port=port, threaded=True)
    except socket.error:
        print(f"Port {port} is already in use")
        # Try another port if 5001 is in use
        try:
            port = 5002
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("0.0.0.0", port))
            sock.close()
            print(f"Port {port} is available")
            print(f"Starting API server on port {port}...")
            app.run(host="0.0.0.0", port=port, threaded=True)
        except socket.error:
            print(f"Port {port} is also in use. Please free up port 5001 or 5002 and try again.")
    except Exception as e:
        print(f"Failed to start server: {str(e)}")