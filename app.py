
from flask import Flask, request, render_template, jsonify, redirect, flash
from werkzeug.utils import secure_filename
import os
from document_processor import process_documents

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

        try:
            checklist.save(checklist_path)
            outline.save(outline_path)

            # Get additional context if provided
            additional_context = request.form.get('additional_context', '').strip()

            # Process files using document_processor
            checklist_items, analysis_results = process_documents(checklist_path, outline_path, additional_context=additional_context)
            
            if "error" in analysis_results:
                flash(analysis_results["error"])
                return redirect(request.url)

            # Format results for template with enhanced data
            results = []
            present_count = 0
            missing_count = 0
            
            for item in checklist_items:
                result = analysis_results.get(item, {})
                is_present = result.get("present", False)
                
                if is_present:
                    present_count += 1
                else:
                    missing_count += 1
                    
                results.append({
                    "item": item,
                    "present": is_present,
                    "explanation": result.get("explanation", ""),
                    "evidence": result.get("evidence", "")
                })

            return render_template('results.html', 
                                results=results,
                                present_count=present_count,
                                missing_count=missing_count,
                                total_count=len(checklist_items))

        except Exception as e:
            flash(f'An error occurred: {str(e)}')
            return redirect(request.url)
        finally:
            # Cleanup
            if os.path.exists(checklist_path):
                os.remove(checklist_path)
            if os.path.exists(outline_path):
                os.remove(outline_path)

    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
