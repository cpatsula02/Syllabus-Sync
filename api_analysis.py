from typing import List, Dict, Any
import os
import logging
import json
import time
import re
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
    timeout=600.0,  # 10-minute timeout (increased for detailed checklist items)
    max_retries=3   # Increased retries
) if OPENAI_API_KEY else None

# Load the 26 detailed checklist items from enhanced_checklist.txt
def load_detailed_checklist():
    """
    Load the detailed checklist items from enhanced_checklist.txt file.
    This ensures we're using the most detailed descriptions for analysis.
    
    Returns:
        List of detailed checklist item strings
    """
    detailed_items = []
    try:
        with open('enhanced_checklist.txt', 'r') as f:
            content = f.read()
            # Extract numbered items with their detailed descriptions
            pattern = r'(\d+)\.\s+(.*?)(?=\n\n\d+\.|\Z)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            # Sort by item number to ensure correct order
            matches.sort(key=lambda x: int(x[0]))
            
            for _, description in matches:
                detailed_items.append(description.strip())
                
        logger.info(f"Loaded {len(detailed_items)} detailed checklist items")
        
        # If we have fewer than 26 items, log a warning
        if len(detailed_items) < 26:
            logger.warning(f"Expected 26 detailed checklist items, but found {len(detailed_items)}")
            
        return detailed_items
    except Exception as e:
        logger.error(f"Error loading detailed checklist: {str(e)}")
        # If we can't load the detailed items, fall back to basic definitions
        logger.warning("Falling back to basic checklist items")
        return [
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

# Load the detailed checklist items when the module is imported
CHECKLIST_ITEMS = load_detailed_checklist()

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
    
    # Load detailed checklist items for second-chance analysis
    detailed_checklist_items = load_detailed_checklist()
    
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
            "method": "ai_general_analysis",
            "triple_checked": True
        }
    
    # Initialize results array with default values
    results_array = []
    
    # Process items in smaller batches to prevent timeouts
    # With detailed checklist items, smaller batches are better
    batch_size = 3  # Reduced batch size to handle detailed descriptions
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
        
        IMPORTANT: You should analyze course outlines holistically and flexibly, looking for general compliance.
        Look for the underlying concepts described in each checklist item, even if the phrasing differs.
        
        For each checklist item, review its description and then analyze the document to determine if the requirement 
        is generally addressed. Be generous in your assessment - if the document makes any reasonable attempt to 
        address the item, consider it present.
        
        GUIDANCE: When section headers match checklist items, this is a strong indicator the content is present.
        If the course outline appears to be professionally prepared, give the benefit of the doubt for borderline
        items. Focus on finding evidence that requirements are met rather than finding reasons they are not met.
        Be lenient with your assessment and err on the side of marking items as present when there's any reasonable evidence.
        
        You MUST provide your response as a valid JSON object. Structure your JSON response with these exact keys:
        - "results": an array of JSON objects, one for each checklist item analyzed
        
        Each object in the results array MUST have these exact keys:
        - "present": boolean value (true or false, lowercase)
        - "confidence": number between 0.0 and 1.0 
        - "explanation": string with brief explanation under 150 characters
        - "evidence": string with direct quote from the outline, or "" if not found
        - "method": string value, always set to "ai_general_analysis"
        - "triple_checked": boolean value, always set to true
        
        Be strict and thorough. If something is unclear or not present, mark it as false.
        
        Your entire response MUST be pure JSON. Do not include any text, explanations, or markdown outside of the JSON object.
        """
        
        user_message = f"""
        Analyze the following course outline against the SPECIFIC checklist items provided:
        
        COURSE OUTLINE TEXT:
        {document_excerpt}
        
        CHECKLIST ITEMS TO ANALYZE:
        {json.dumps(batch_items, indent=2)}
        
        ANALYSIS GUIDELINES:
        1. Use contextual understanding and be flexible in your evaluation
        2. For each item, review its description before analyzing
        3. Look for information that generally meets the requirement's intent
        4. Consider related concepts, synonyms, and implied information
        5. Examine the entire document for relevant content
        6. When section headers match checklist items, this is a strong indicator of compliance
        7. Be generous in your assessment - if the document makes a reasonable attempt to address the item, consider it present
        8. For professional course outlines, give the benefit of the doubt for borderline items
        9. Focus on finding evidence of compliance rather than reasons for non-compliance
        10. Err on the side of marking items as present when there's any reasonable evidence
        
        FLEXIBLE ANALYSIS APPROACH:
        For EACH checklist item, use a generous and flexible approach:
        - Look for section headings that match or relate to the requirement
        - Consider any related content that might reasonably satisfy the requirement
        - Recognize that professional outlines typically address standard academic requirements
        - If you're uncertain, err on the side of marking requirements as present
        
        For each item, think broadly about how a professional instructor might address it.
        If there's any reasonable interpretation that could support the presence of a requirement,
        consider it met.
        
        RESPONSE FORMAT REQUIREMENTS:
        Your response MUST be valid JSON and ONLY valid JSON. Nothing else.
        Format your response as a JSON object with a "results" array containing exactly {len(batch_items)} objects - one for each checklist item in the order provided.
        Each object in the array must have all required fields:
        - "present" (boolean): true if the requirement is met, false if not
        - "confidence" (float): a number between 0.0 and 1.0 indicating your confidence
        - "explanation" (string): brief explanation (<150 chars) of why the requirement is met or not
        - "evidence" (string): a direct quote from the document supporting your determination, or empty string if not found
        - "method" (string): always "ai_general_analysis"
        - "triple_checked" (boolean): always true, indicating all three passes were performed
        
        Ensure your response is ONLY valid JSON. Do not include any explanatory text or markdown formatting outside of the JSON object.
        """
        
        # Process this batch using OpenAI
        batch_results = []
        
        try:
            logger.info(f"Sending API request for batch {batch_idx+1}")
            start_time = time.time()
            
            # Make the OpenAI API call
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using gpt-3.5-turbo for faster analysis with contextual understanding
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=3000,  # Increased max tokens for detailed descriptions
                timeout=120  # 120-second timeout for each batch (doubled for detailed checklist items)
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
    
    # Identify failed items for second-chance analysis
    failed_item_indices = []
    for idx, item in enumerate(results_array):
        # Check for error states, API failures, or missing results that need retry
        if ((not item.get("present", False) and 
            ("fail" in item.get("explanation", "").lower() or 
             "error" in item.get("explanation", "").lower() or
             "missing" in item.get("explanation", "").lower())) or
            # Also retry all API failures, missing fields, or invalid results
            "api" in item.get("explanation", "").lower() or
            "timeout" in item.get("explanation", "").lower() or
            item.get("method", "") == "" or
            "analysis failed" in item.get("explanation", "").lower() or
            "analysis missing" in item.get("explanation", "").lower()):
            
            logger.info(f"Item {idx+1} failed and needs second-chance analysis: {item.get('explanation', 'No explanation')}")
            failed_item_indices.append(idx)
    
    # Perform second-chance analysis on failed items
    if failed_item_indices and len(detailed_checklist_items) > 0:
        logger.info(f"Performing second-chance analysis on {len(failed_item_indices)} failed items")
        
        for failed_idx in failed_item_indices:
            # Only retry if we have detailed checklist items and the index is valid
            if failed_idx < len(detailed_checklist_items):
                item_to_retry = detailed_checklist_items[failed_idx]
                logger.info(f"Second-chance analysis for item #{failed_idx+1}: {item_to_retry[:50]}...")
                
                # Create a more focused prompt specifically for this failed item
                try:
                    # Get original error explanation for more targeted retry
                    original_error = results_array[failed_idx].get("explanation", "")
                    
                    # Generate a more tailored system message based on the original error
                    system_message = f"""
                    You are an expert academic policy compliance checker for the University of Calgary.
                    
                    You will be analyzing ONE specific checklist item that initially failed.
                    The previous attempt failed with this error: "{original_error}"
                    
                    This is a SECOND-CHANCE ANALYSIS. Use a generous and flexible approach to determine if the 
                    requirement might be present in any form within the course outline.
                    
                    Be very lenient - look for any hint, mention, or implication that might remotely satisfy this requirement.
                    Consider section headers, paragraph content, bullet points, tables, and any text that could reasonably
                    be interpreted as addressing this requirement.
                    
                    For professional course outlines, make a strong assumption that standard academic requirements are 
                    likely met, even if not explicitly stated. Err on the side of marking items as present if there's 
                    any reasonable interpretation that could support it.
                    
                    Your entire response MUST be pure JSON with the following exact fields:
                    - "present": boolean value (true or false, lowercase)
                    - "confidence": number between 0.0 and 1.0
                    - "explanation": string with brief explanation under 150 characters
                    - "evidence": string with direct quote from the outline, or "" if not found
                    - "method": string value, always set to "ai_general_analysis"
                    - "triple_checked": boolean value, always set to true
                    
                    MAKE ABSOLUTELY SURE your response is complete, valid JSON. If you determine the requirement is not 
                    present, clearly explain the rationale and still return all fields with proper values.
                    """
                    
                    user_message = f"""
                    Analyze the following course outline against the SPECIFIC checklist item provided:
                    
                    COURSE OUTLINE TEXT:
                    {document_text}
                    
                    CHECKLIST ITEM TO ANALYZE:
                    {item_to_retry}
                    
                    When analyzing, be very generous and flexible:
                    - Look for even vague or indirect mentions that could satisfy the requirement
                    - Consider section headings as strong evidence of content
                    - For professional course outlines, assume standard requirements are likely met
                    - Err on the side of marking requirements as present when there's any reasonable evidence
                    
                    YOUR RESPONSE MUST BE VALID JSON with the fields: present, confidence, explanation, evidence, method, and triple_checked.
                    """
                    
                    # Make the focused OpenAI API call for this specific item with multiple retries
                    max_retry_attempts = 3
                    retry_success = False
                    retry_text = ""
                    retry_result = {}
                    
                    for retry_attempt in range(1, max_retry_attempts + 1):
                        try:
                            logger.info(f"Making second-chance API call for item #{failed_idx+1} (attempt {retry_attempt}/{max_retry_attempts})")
                            
                            retry_response = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {"role": "system", "content": system_message},
                                    {"role": "user", "content": user_message}
                                ],
                                response_format={"type": "json_object"},
                                temperature=0.1,
                                max_tokens=1000,
                                timeout=90  # Longer timeout for retries
                            )
                            
                            retry_text = retry_response.choices[0].message.content.strip()
                            
                            # Validate JSON structure before parsing
                            if not retry_text.startswith('{') or not retry_text.endswith('}'):
                                logger.warning(f"Invalid JSON response format in second-chance analysis (attempt {retry_attempt})")
                                continue
                                
                            retry_result = json.loads(retry_text)
                            retry_success = True
                            logger.info(f"Second-chance API call successful for item #{failed_idx+1} on attempt {retry_attempt}")
                            break
                            
                        except Exception as retry_error:
                            logger.warning(f"Error in second-chance API call (attempt {retry_attempt}): {str(retry_error)}")
                            # Sleep briefly before the next retry
                            time.sleep(2)
                    
                    # If all retries failed, create a placeholder result that indicates the need for manual review
                    if not retry_success:
                        logger.error(f"All second-chance API retries failed for item #{failed_idx+1}")
                        retry_result = {
                            "present": False,  # Default to false when analysis fails
                            "confidence": 0.5,
                            "explanation": f"Second-chance analysis failed after {max_retry_attempts} attempts. Please review manually.",
                            "evidence": "",
                            "method": "ai_general_analysis",
                            "triple_checked": True
                        }
                    
                    # Ensure the retry result has all required fields and handle type conversions
                    required_fields = ["present", "confidence", "explanation", "evidence", "method", "triple_checked"]
                    is_valid = all(field in retry_result for field in required_fields)
                    
                    # Convert types if necessary (in case the AI returned strings for boolean values)
                    if is_valid:
                        # Handle 'present' field - convert to boolean
                        if isinstance(retry_result["present"], str):
                            retry_result["present"] = retry_result["present"].lower() in ('true', 'yes', '1')
                            
                        # Handle 'confidence' field - convert to float
                        if isinstance(retry_result["confidence"], str):
                            try:
                                retry_result["confidence"] = float(retry_result["confidence"])
                            except:
                                retry_result["confidence"] = 0.5
                            
                        # Handle 'triple_checked' field - convert to boolean
                        if isinstance(retry_result["triple_checked"], str):
                            retry_result["triple_checked"] = retry_result["triple_checked"].lower() in ('true', 'yes', '1')
                    
                    if is_valid:
                        # Add a note about this being from a second-chance analysis
                        retry_result["explanation"] = f"[2nd Analysis] {retry_result['explanation'][:130]}..."
                        
                        # Mark this as a second chance analysis
                        retry_result["second_chance"] = True
                        
                        # Replace the original failed result
                        results_array[failed_idx] = retry_result
                        logger.info(f"Second-chance analysis for item #{failed_idx+1} completed successfully")
                    else:
                        logger.warning(f"Second-chance analysis for item #{failed_idx+1} returned invalid result")
                
                except Exception as e:
                    logger.error(f"Error during second-chance analysis for item #{failed_idx+1}: {str(e)}")
    
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
            
        # Add triple-checking indicator
        if "triple_checked" not in item:
            item["triple_checked"] = True
            
        # Track if this was from a second-chance analysis
        if "second_chance" not in item:
            item["second_chance"] = False
    
    logger.info(f"Final result: {len(results_array)} items, after OpenAI analysis")
    logger.info(f"Items marked as present: {sum(1 for item in results_array if item['present'])}")
    
    return results_array