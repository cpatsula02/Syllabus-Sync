import requests
import os
import json
import time

# URL of the API endpoint
API_URL = "http://localhost:5000/api/analyze-course-outline"  # Using the main app endpoint

# Path to a sample course outline PDF
SAMPLE_OUTLINE_PATH = os.path.join('attached_assets', 'W25%20ENTI%20674%20L01-L02%20-%20Course%20Outline%20-%20Mohammad%20Keyhani1.docx.pdf')

def test_api_with_file():
    """Test the API by sending a file"""
    print(f"Testing API with file upload: {SAMPLE_OUTLINE_PATH}")
    
    # Check if the file exists
    if not os.path.exists(SAMPLE_OUTLINE_PATH):
        print(f"Error: Sample file not found at {SAMPLE_OUTLINE_PATH}")
        return
    
    # Prepare the file for upload
    with open(SAMPLE_OUTLINE_PATH, 'rb') as f:
        files = {'outline': (os.path.basename(SAMPLE_OUTLINE_PATH), f, 'application/pdf')}
        
        print("Sending API request...")
        start_time = time.time()
        
        # Send the request with a longer timeout (300 seconds)
        response = requests.post(API_URL, files=files, timeout=300)
        
        elapsed = time.time() - start_time
        print(f"API request completed in {elapsed:.2f} seconds")
        
        # Check the response
        if response.status_code == 200:
            results = response.json()
            print(f"Success! Received {len(results)} results")
            
            # Count how many items are marked as present
            present_count = sum(1 for item in results if item.get('present', False))
            print(f"Items marked as present: {present_count} out of {len(results)}")
            
            # Print the first few results
            print("\nSample results:")
            for i, result in enumerate(results[:5]):
                print(f"{i+1}. Present: {result.get('present', False)}")
                print(f"   Confidence: {result.get('confidence', 0.0):.2f}")
                print(f"   Explanation: {result.get('explanation', 'N/A')}")
                print(f"   Method: {result.get('method', 'N/A')}")
                if result.get('evidence'):
                    evidence = result.get('evidence')
                    if len(evidence) > 100:
                        evidence = evidence[:97] + "..."
                    print(f"   Evidence: {evidence}")
                print()
                
            # Save the full results to a file
            with open('api_test_results.json', 'w') as outfile:
                json.dump(results, outfile, indent=2)
                print("Full results saved to api_test_results.json")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    test_api_with_file()