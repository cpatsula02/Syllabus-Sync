# Course Outline Compliance Checker

An advanced AI-powered document verification platform leveraging sophisticated natural language processing for intelligent academic course outline compliance analysis, with enhanced contextual understanding and comprehensive verification mechanisms.

## Core Features

1. **OpenAI API Integration**: Exclusively uses OpenAI's API for all checklist verifications
2. **Advanced Contextual Analysis**: Multi-pass verification with deep semantic understanding
3. **Triple-Checking Process**: Each item analyzed through multiple perspectives
4. **Resilient API Handling**: Built-in retry mechanisms and optimized batch processing
5. **Comprehensive API Documentation**: Well-documented API endpoints with examples
6. **Professional Report Generation**: Creates detailed PDF reports of analysis results

## Technical Improvements

Recent enhancements to improve reliability and performance:

- **Enhanced Document Processing**: Better capture of tables and structured data
- **Optimized OpenAI API Usage**: Using gpt-3.5-turbo-16k model for better balance of speed and quality
- **Reduced Batch Sizes**: Processing 1-2 items at a time for improved reliability
- **Extended Timeouts**: Increased from 45 to 90 seconds with comprehensive error handling
- **Gunicorn Configuration**: Using threaded worker class to prevent timeouts
- **Single-Item Retry Approach**: New resilient OpenAI API calling mechanism

## Getting Started

1. Clone the repository
2. Set your OpenAI API key in the environment variables: `export OPENAI_API_KEY=your-key-here`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the application: `./run.sh`

## API Documentation

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed API information.

## Running Tests

- Test the enhanced OpenAI integration: `python test_enhanced_openai.py`
- Test API functionality: `python test_api_detailed.py`
- Verify implementation: `python verify_implementation.py`

## Important Notes

- This system requires a valid OpenAI API key to function. It does NOT fall back to pattern matching.
- For production use, increase worker timeouts to accommodate longer documents.
- All analysis must use OpenAI API exclusively - hybrid approaches are not acceptable.