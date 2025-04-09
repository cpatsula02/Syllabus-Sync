import requests
import os
import time
from document_processor import extract_text

# Test file path
TEST_FILE_PATH = "uploads/test_sample.pdf"
API_URL = "http://localhost:5000"

def test_upload_file():
    """Test uploading a file and analyzing it through the web interface"""
    print(f"Testing file upload with {TEST_FILE_PATH}")
    
    if not os.path.exists(TEST_FILE_PATH):
        print(f"Error: Test file {TEST_FILE_PATH} not found")
        return False
    
    # Extract file content for potential debugging
    file_content = extract_text(TEST_FILE_PATH)
    print(f"File content extracted: {len(file_content)} characters")
    
    # Prepare the file for upload
    files = {
        'outline': (os.path.basename(TEST_FILE_PATH), open(TEST_FILE_PATH, 'rb'), 'application/pdf')
    }
    
    # For simplicity, we'll use a hardcoded checklist that matches the standard one
    checklist = """1. Instructor Email
2. Course Objectives
3. Textbooks & Other Course Material
4. Prohibited Materials
5. Course Workload
6. Grading Scale
7. Grade Distribution Table
8. Group Work Weight
9. Assessment-Objectives Alignment
10. Due Dates in Grade Table
11. 30% Before Last Class
12. No Post-Term Assignments
13. Missed Assessment Policy
14. Late Submission Policy
15. Participation Grading Criteria
16. Assignment Submission Instructions
17. Group Project Guidelines
18. Midterm/Quiz Information
19. Final Exam Details
20. Final Exam Weight Limit
21. Take-Home Final Identification
22. Instructor Contact Guidelines
23. Class Schedule Inclusion
24. Due Dates in Schedule
25. Exam Dates in Schedule
26. Functional Web Links"""
    
    data = {
        'checklist': checklist
    }
    
    print("Uploading file for analysis...")
    try:
        response = requests.post(f"{API_URL}/", files=files, data=data)
        
        # Check if the response contains HTML from the results page
        if "results" in response.url:
            print(f"✅ Success: Redirected to results page ({response.url})")
            return True
        elif "Upload a course outline" in response.text:
            print("❌ Error: Redirected back to upload page")
            return False
        else:
            print(f"❌ Error: Unexpected response - Status code {response.status_code}")
            print(f"Response URL: {response.url}")
            print(f"Response content (first 200 chars): {response.text[:200]}...")
            return False
    except Exception as e:
        print(f"❌ Error during request: {str(e)}")
        return False

def test_api_analyze():
    """Test analyzing through the API endpoint"""
    print(f"\nTesting API analysis with {TEST_FILE_PATH}")
    
    if not os.path.exists(TEST_FILE_PATH):
        print(f"Error: Test file {TEST_FILE_PATH} not found")
        return False
    
    # Extract file content for API testing
    document_text = extract_text(TEST_FILE_PATH)
    print(f"Document text extracted: {len(document_text)} characters")
    
    # JSON request
    data = {
        'document_text': document_text
    }
    
    print("Sending document text to API for analysis...")
    try:
        response = requests.post(f"{API_URL}/api/analyze-course-outline", json=data)
        
        if response.status_code == 200:
            result = response.json()
            # Check if the result contains items in array format
            if isinstance(result, list) and len(result) > 0:
                print(f"✅ Success: API returned {len(result)} analysis items")
                
                # Check for item #11 specifically
                item11 = next((item for item in result if "30%" in str(item.get('explanation', ''))), None)
                if item11:
                    print(f"✅ Item #11 (30% Before Last Class) found in results:")
                    print(f"   - Present: {item11.get('present')}")
                    print(f"   - Confidence: {item11.get('confidence')}")
                    print(f"   - Explanation: {item11.get('explanation')}")
                else:
                    print("❌ Item #11 (30% Before Last Class) not found in results")
                    
                return True
            else:
                print(f"❌ Error: Invalid API response format")
                print(f"Response: {result}")
                return False
        else:
            print(f"❌ Error: API returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error during API request: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting tests...")
    
    # Test file upload
    web_success = test_upload_file()
    
    # Test API endpoint
    api_success = test_api_analyze()
    
    # Summary
    print("\n----- Test Summary -----")
    print(f"Web Interface Test: {'✅ PASSED' if web_success else '❌ FAILED'}")
    print(f"API Endpoint Test: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    if web_success and api_success:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n❌ Some tests failed - check logs above for details")