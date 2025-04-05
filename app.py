from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'dev_secret_key'

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

        checklist.save(checklist_path)
        outline.save(outline_path)

        # Process files here
        results = [
            {"item": "Sample item 1", "analysis": "✅ Present - Found in document"},
            {"item": "Sample item 2", "analysis": "❌ Missing - Not found in document"}
        ]

        # Cleanup
        os.remove(checklist_path)
        os.remove(outline_path)

        return render_template('results.html', results=results)

    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)