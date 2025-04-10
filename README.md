Syllabus Sync

A Flask-based web application that analyzes university course outlines to ensure compliance with institutional standards using advanced AI-powered analysis.

## Overview

Syllabus Sync helps faculty and administrators verify course outlines against 26 essential compliance requirements, providing detailed feedback and generating comprehensive PDF reports. The system uses OpenAI's GPT models for intelligent analysis combined with pattern matching for enhanced accuracy.

## Key Features

- AI-powered document analysis using OpenAI GPT models
- Support for PDF and Word document formats
- Interactive web interface with real-time analysis
- Detailed compliance reporting with evidence
- Professional PDF report generation
- Triple-checking verification system
- Enhanced pattern matching for accurate results
- REST API for programmatic access

## Tech Stack

- **Backend**: Python Flask
- **AI Integration**: OpenAI API
- **Document Processing**: pdfplumber, python-docx
- **Frontend**: HTML/CSS/JavaScript, Bootstrap
- **PDF Generation**: FPDF2
- **Server**: Gunicorn

## Installation and Setup

1. Clone this Repl
2. Add your OpenAI API key to the Secrets tab (Environment Variables)
   - Secret name: `OPENAI_API_KEY`
3. Click the Run button to start the application

## Usage

### Web Interface

1. Access the web interface through your Repl's URL
2. Upload your course outline (PDF/DOCX)
3. Review the provided checklist items
4. Submit for analysis
5. View detailed results and download PDF report

### API Usage

The system provides a REST API for programmatic access:

```bash
POST /api/analyze-course-outline
Content-Type: multipart/form-data
Body: outline=[File Upload]

# or

POST /api/analyze-course-outline
Content-Type: application/json
Body: {
  "document_text": "Full text content of the course outline..."
}
```

Response format:
```json
[
  {
    "present": true|false,
    "confidence": 0.0-1.0,
    "explanation": "Brief explanation",
    "evidence": "Supporting quote from document",
    "method": "ai_general_analysis",
    "triple_checked": true
  },
  ...
]
```

## Compliance Requirements

The system checks for 26 essential requirements including:
- Instructor contact information
- Course objectives
- Grade distribution
- Assessment policies
- Course schedule
- And more...

## Acknowledgments

- Built with OpenAI's GPT models
- Uses DejaVu Fonts for PDF generation
- Developed for academic course outline compliance verification

## Support

For issues or questions:
1. Create a fork of this Repl
2. Add details about the issue
3. Share the Repl URL for troubleshooting

## Contributors

Developed by Sarah Chan, Alpa Duque, Melody Kivia, Joyce Lam, and Casey Patsula to streamline course outline compliance verification for a project in ENTI 674.
