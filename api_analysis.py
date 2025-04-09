from typing import List, Dict, Any
import os
import logging
import json
import time
import openai
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load OpenAI API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment. API calls will fail.")
else:
    api_key_start = OPENAI_API_KEY[:5] + "..." if len(OPENAI_API_KEY) > 5 else "too short"
    logger.info(f"OPENAI_API_KEY found in api_analysis.py, starts with: {api_key_start}")

# Initialize OpenAI client with longer timeout
client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=300.0,  # 5-minute timeout
    max_retries=2
) if OPENAI_API_KEY else None

# The 26 hardcoded checklist items from enhanced_checklist.txt
CHECKLIST_ITEMS = [
    "Instructor Email: Does the outline include the instructor's email? An acceptable email must end with \"ucalgary.ca\".",
    "Course Objectives: Are the course objectives listed and numbered?",
    "Textbooks & Other Course Material: Are any textbooks, readings, and additional course materials listed?",
    "Prohibited Materials: Check for information that details any prohibited platforms, resources, and tools that cannot be used.",
    "Course Workload: Is there a course workload section?",
    "Grading Scale: Does the course outline include the Grade Scale header and a table mapping percentages to letter grades?",
    "Grade Distribution Table: Does the course outline include a Grade Distribution statement with weights assigned to assessments?",
    "Group Work Weight: If group work is included, verify it doesn't exceed 40% of the overall final grade.",
    "Assessment-Objectives Alignment: Check that assessments indicate which course objectives each assessment measures.",
    "Due Dates in Grade Table: Does the grade distribution table include due dates for all assignments and examinations?",
    "30% Before Last Class: Will students receive AT LEAST 30% of their final grade before the last day of classes?",
    "No Post-Term Assignments: Are there any assignments due after the last day of classes?",
    "Missed Assessment Policy: Does the outline have a missed assessment policy section?",
    "Late Submission Policy: Does the outline have a Late Policy section that explains penalties for late submissions?",
    "Participation Grading Criteria: If class participation is listed, are details provided on how it's evaluated?",
    "Assignment Submission Instructions: Are assignment details included with instructions on how and where to submit work?",
    "Group Project Guidelines: If a group project is listed, are details provided including the first group work deadline?",
    "Midterm/Quiz Information: For any midterms or quizzes, is information provided about timing, location, format, and permitted materials?",
    "Final Exam Details: If a Final Exam is listed, does the outline include information on timing, location, modality, and permitted materials?",
    "Final Exam Weight Limit: Does the Final Exam count for LESS THAN 50% of the final grade?",
    "Take-Home Final Identification: If there is a Take-Home Final Examination, is it clearly identified?",
    "Instructor Contact Guidelines: Is the \"Contacting Your Instructor\" section included with guidelines for communication?",
    "Class Schedule Inclusion: Is there a Class Schedule and Topics section showing weekly topics and activities?",
    "Due Dates in Schedule: Does the Class Schedule include or reference assignment due dates?",
    "Exam Dates in Schedule: Does the Class Schedule include quiz, test, or exam dates?",
    "Functional Web Links: Are all links in the outline valid and working?"
]

def analyze_course_outline(document_text: str) -> List[Dict[str, Any]]:
    """
    Analyze a course outline against the 26 hardcoded checklist items.
    This implementation uses OpenAI for analysis, with performance optimizations to ensure reliable results.
    
    Args:
        document_text: The text content of the course outline document
        
    Returns:
        List of 26 JSON objects, one for each checklist item
    """
    if not client:
        logger.error("OpenAI client not initialized. Cannot perform analysis.")
        raise ValueError("OpenAI API key not available. Cannot perform analysis.")
    
    # Break document into manageable chunks if needed
    max_doc_length = 12000  # Most outlines should fit within this limit
    document_excerpt = document_text[:max_doc_length]
    if len(document_text) > max_doc_length:
        document_excerpt += "..."
        logger.warning(f"Document text truncated from {len(document_text)} to {max_doc_length} characters")
    
    logger.info(f"Document length: {len(document_excerpt)} characters")
    
    # Define functions to create standard structured response objects
    def create_result_item(present, confidence, explanation, evidence=""):
        """Create a properly formatted result item"""
        return {
            "present": present,
            "confidence": confidence,
            "explanation": explanation[:147] + "..." if len(explanation) > 150 else explanation,
            "evidence": evidence,
            "method": "ai_general_analysis"
        }
    
    # Initialize results array with default values
    results_array = []
    
    # Process items in smaller batches to prevent timeouts
    # We'll process items in batches of 5 to keep API calls manageable
    batch_size = 5
    num_batches = (len(CHECKLIST_ITEMS) + batch_size - 1) // batch_size
    
    logger.info(f"Processing document in {num_batches} batches of {batch_size} items each")
    
    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(CHECKLIST_ITEMS))
        batch_items = CHECKLIST_ITEMS[start_idx:end_idx]
        
        logger.info(f"Processing batch {batch_idx+1}/{num_batches} with items {start_idx+1}-{end_idx}")
        
        # Create system message for OpenAI
        system_message = """
        You are an expert academic policy compliance checker for the University of Calgary.
        You'll analyze course outlines against specific checklist items contextually - don't look for exact phrasing.
        
        For each checklist item, provide a structured JSON object with these keys:
        - "present": true or false (must be lowercase booleans)
        - "confidence": number between 0.0 and 1.0 
        - "explanation": a brief explanation under 150 characters
        - "evidence": a direct quote from the outline, or "" if not found
        - "method": always set to "ai_general_analysis"
        
        Be strict and thorough. If something is unclear or not present, mark it as false.
        """
        
        user_message = f"""
        Analyze the following course outline against the SPECIFIC checklist items provided:
        
        COURSE OUTLINE TEXT:
        {document_excerpt}
        
        CHECKLIST ITEMS TO ANALYZE:
        {json.dumps(batch_items, indent=2)}
        
        For EACH checklist item, analyze the document to determine if the requirement is met.
        
        Return a JSON object with a "results" array containing exactly {len(batch_items)} objects - one for each checklist item in the order provided.
        Each object in the array must have all required fields:
        - "present" (boolean): true if the requirement is met, false if not
        - "confidence" (float): a number between 0.0 and 1.0 indicating your confidence
        - "explanation" (string): brief explanation (<150 chars) of why the requirement is met or not
        - "evidence" (string): a direct quote from the document supporting your determination, or empty string if not found
        - "method" (string): always "ai_general_analysis"
        """
        
        # Process this batch using OpenAI
        batch_results = []
        
        try:
            logger.info(f"Sending API request for batch {batch_idx+1}")
            start_time = time.time()
            
            # Make the OpenAI API call
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using 3.5-turbo for faster analysis
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=2000,
                timeout=60  # 60-second timeout for each batch
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Batch {batch_idx+1} OpenAI API call completed in {elapsed:.2f} seconds")
            
            # Extract and process the response
            try:
                response_text = response.choices[0].message.content.strip()
                parsed_response = json.loads(response_text)
                
                if isinstance(parsed_response, dict) and "results" in parsed_response:
                    batch_results = parsed_response["results"]
                elif isinstance(parsed_response, list):
                    batch_results = parsed_response
                else:
                    logger.warning(f"Unexpected response format for batch {batch_idx+1}")
                    # Use default values if format is unexpected
                    batch_results = []
                
                # Ensure we have the correct number of items in this batch
                if len(batch_results) != len(batch_items):
                    logger.warning(f"Expected {len(batch_items)} results in batch {batch_idx+1}, but got {len(batch_results)}")
                    # Pad or truncate as needed
                    while len(batch_results) < len(batch_items):
                        missing_idx = start_idx + len(batch_results)
                        batch_results.append(create_result_item(
                            False, 0.5, 
                            f"Analysis missing for item {missing_idx+1}", ""
                        ))
                    
                    if len(batch_results) > len(batch_items):
                        batch_results = batch_results[:len(batch_items)]
                
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Error processing batch {batch_idx+1} response: {str(e)}")
                # Create default responses for this batch
                batch_results = []
                for i in range(len(batch_items)):
                    item_idx = start_idx + i
                    batch_results.append(create_result_item(
                        False, 0.5, 
                        f"Analysis failed for item {item_idx+1}", ""
                    ))
        
        except Exception as e:
            logger.error(f"Error during OpenAI API call for batch {batch_idx+1}: {str(e)}")
            # Create default responses for this batch
            batch_results = []
            for i in range(len(batch_items)):
                item_idx = start_idx + i
                batch_results.append(create_result_item(
                    False, 0.5, 
                    f"API call failed for item {item_idx+1}", ""
                ))
        
        # Add this batch's results to the main results array
        results_array.extend(batch_results)
    
    # Final validation: ensure we have exactly 26 items with all required fields
    if len(results_array) != 26:
        logger.warning(f"Final validation: expected 26 results, but got {len(results_array)}")
        # Adjust as needed to ensure exactly 26 items
        while len(results_array) < 26:
            missing_idx = len(results_array)
            results_array.append(create_result_item(
                False, 0.5, 
                f"Analysis missing for item {missing_idx+1}", ""
            ))
        
        if len(results_array) > 26:
            results_array = results_array[:26]
    
    # Verify that all items have required fields, fix any issues
    for idx, item in enumerate(results_array):
        # Check and fix required fields
        if "present" not in item or not isinstance(item["present"], bool):
            item["present"] = False
        
        if "confidence" not in item or not isinstance(item["confidence"], (int, float)) or item["confidence"] < 0 or item["confidence"] > 1:
            item["confidence"] = 0.5
            
        if "explanation" not in item or not isinstance(item["explanation"], str):
            item["explanation"] = f"Analysis incomplete for item {idx+1}"
        elif len(item["explanation"]) > 150:
            item["explanation"] = item["explanation"][:147] + "..."
            
        if "evidence" not in item or not isinstance(item["evidence"], str):
            item["evidence"] = ""
            
        if "method" not in item or item["method"] != "ai_general_analysis":
            item["method"] = "ai_general_analysis"
    
    logger.info(f"Final result: {len(results_array)} items, after OpenAI analysis")
    logger.info(f"Items marked as present: {sum(1 for item in results_array if item['present'])}")
    
    return results_array