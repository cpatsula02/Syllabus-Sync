from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import openai
from PyPDF2 import PdfReader
from docx import Document
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
openai.api_key = os.getenv("OPENAI_API_KEY")  # Set in Replit secrets

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
    elif file_path.endswith(".docx"):
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif file_path.endswith(".txt"):
        with open(file_path, 'r') as f:
            return f.read()
    else:
        return ""

def extract_checklist_items(checklist_text):
    return [line.strip() for line in checklist_text.split('\n') if line.strip()]

def analyze_item_with_gpt(checklist_item, course_outline):
    prompt = f"""
You are reviewing a university course outline to determine whether a specific requirement is met.

Requirement:
{checklist_item}

Course Outline:
{course_outline}

Respond with one of the following:
✅ Present – [brief reason and matched text]
❌ Missing – [brief reason]
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API error: {str(e)}")
        return f"❌ Error – {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        checklist_file = request.files.get('checklist')
        outline_file = request.files.get('outline')

        if not checklist_file or not outline_file:
            flash('Both files are required.')
            return redirect(request.url)


        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        checklist_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(checklist_file.filename))
        outline_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(outline_file.filename))

        try:
            checklist_file.save(checklist_path)
            outline_file.save(outline_path)

            checklist_text = extract_text(checklist_path)
            outline_text = extract_text(outline_path)

            checklist_items = extract_checklist_items(checklist_text)
            results = []

            for item in checklist_items:
                analysis = analyze_item_with_gpt(item, outline_text)
                results.append({"item": item, "analysis": analysis})

            return render_template('results.html', results=results)

        except Exception as e:
            logging.error(f"Error processing files: {str(e)}", exc_info=True)
            flash('An error occurred during processing. Please try again.')
            return redirect(request.url)
        finally:
            # Cleanup files
            if os.path.exists(checklist_path):
                os.remove(checklist_path)
            if os.path.exists(outline_path):
                os.remove(outline_path)

    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)