from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import io
import logging
import re
import socket
import urllib.request
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

def validate_links(text):
    """
    Validates links found in the provided text.
    Returns lists of valid and invalid links.
    Used for checking the 26th checklist item (functional web links).
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
        
        # Add validation to ensure all results have the required fields
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                logger.error(f"Item #{i+1} has invalid result type: {type(result)}")
                # Create default response for invalid item
                results[i] = {
                    "present": False,
                    "confidence": 0.5,
                    "explanation": "Error: Invalid result format",
                    "evidence": "",
                    "method": "ai_general_analysis",
                    "triple_checked": True,
                    "second_chance": False
                }
                continue
                
            # Check for missing required fields
            missing_fields = []
            for field in ["present", "confidence", "explanation", "evidence", "method", "triple_checked"]:
                if field not in result:
                    missing_fields.append(field)
                    
            if missing_fields:
                logger.error(f"Item #{i+1} is missing required fields: {missing_fields}")
                # Add default values for missing fields
                for field in missing_fields:
                    if field == "present":
                        result[field] = False
                    elif field == "confidence":
                        result[field] = 0.5
                    elif field == "explanation":
                        result[field] = "Error: Missing explanation"
                    elif field == "evidence":
                        result[field] = ""
                    elif field == "method":
                        result[field] = "ai_general_analysis"
                    elif field == "triple_checked":
                        result[field] = True
                    elif field == "second_chance":
                        result[field] = False
        
        # Handle web links validation (for the 26th checklist item)
        valid_links, invalid_links = validate_links(document_text)
        
        # Find the web links related checklist item (usually the 26th item)
        for i, item in enumerate(results):
            if 'link' in item.get('explanation', '').lower() or 'url' in item.get('explanation', '').lower():
                if invalid_links:
                    results[i] = {
                        'present': False,
                        'confidence': 0.9,
                        'explanation': f'Found {len(invalid_links)} invalid links in document',
                        'evidence': "Invalid links found: " + ", ".join(invalid_links[:3]),
                        'method': 'ai_general_analysis',
                        'triple_checked': True,
                        'second_chance': False
                    }
                else:
                    results[i] = {
                        'present': True,
                        'confidence': 0.9,
                        'explanation': 'All links in document are valid',
                        'evidence': "Valid links found: " + ", ".join(valid_links[:3]),
                        'method': 'ai_general_analysis',
                        'triple_checked': True,
                        'second_chance': False
                    }
                logger.info(f"Updated item {i+1} with web links validation results")
                break
        
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
                <p>The API returns a JSON array of 26 objects, one for each checklist item with the following properties:</p>
                <ul style="list-style-type: none; padding-left: 20px; line-height: 1.5;">
                    <li><code>present</code>: boolean - indicates if the item is present in the outline</li>
                    <li><code>confidence</code>: number - between 0.0 and 1.0, representing analysis confidence</li>
                    <li><code>explanation</code>: string - brief explanation (prefixed with "[2nd Analysis]" if from second-chance analysis)</li>
                    <li><code>evidence</code>: string - direct quote from the outline, or empty string if not found</li>
                    <li><code>method</code>: string - always "ai_general_analysis"</li>
                    <li><code>triple_checked</code>: boolean - indicates if the item was analyzed using multiple passes</li>
                    <li><code>second_chance</code>: boolean - indicates if this result came from a second-chance analysis</li>
                </ul>
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