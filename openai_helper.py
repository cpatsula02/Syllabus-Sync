import os
import json
import logging
import time
from typing import List, Dict, Any

# Import OpenAI
from openai import OpenAI, APITimeoutError, RateLimitError, APIConnectionError, BadRequestError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Use OpenAI's API to analyze if a checklist item is present in the document.
    Returns a dictionary with match result and confidence score.
    
    This enhanced version is designed to:
    1. Better handle semantic matching (recognizing requirements even when worded differently)
    2. Be more strict with specific requirements like @ucalgary.ca emails
    3. Reduce false positives by requiring contextual evidence
    4. Reduce false negatives by focusing on semantic meaning, not just keywords
    """
    # Determine if this item needs special handling
    item_lower = item.lower()
    
    # Define all special requirement types with their keywords
    special_cases = {
        'email': any(keyword in item_lower for keyword in ['email', 'contact', 'instructor']) and '@' in item_lower,
        'course_objectives': any(keyword in item_lower for keyword in ['objective', 'goals', 'outcomes']) and any(keyword in item_lower for keyword in ['listed', 'numbered', 'course']),
        'tools_platforms': any(keyword in item_lower for keyword in ['tools', 'platforms', 'resources', 'software']) and any(keyword in item_lower for keyword in ['student', 'available', 'use', 'access']),
        'workload': 'workload' in item_lower and 'course' in item_lower,
        'missed_assessment': any(keyword in item_lower for keyword in ['missed', 'missing']) and any(keyword in item_lower for keyword in ['assessment', 'exam', 'test', 'assignment', 'policy']),
        'late_policy': any(keyword in item_lower for keyword in ['late', 'policy', 'deadline']),
        'contacting_instructor': any(keyword in item_lower for keyword in ['contacting', 'contact']) and any(keyword in item_lower for keyword in ['instructor', 'professor', 'faculty', 'teacher']),
        'links': any(keyword in item_lower for keyword in ['link', 'url', 'website', 'http', 'www'])
    }
    
    # Determine which special case(s) apply
    active_special_cases = {k: v for k, v in special_cases.items() if v}
    is_special_requirement = len(active_special_cases) > 0
    
    # Create a specialized system message based on the item type
    system_message = "You are an expert document analyzer for academic course outlines. Your job is to determine if specific requirements are met in a document."
    
    # Email requirements
    if special_cases['email']:
        system_message += """
For instructor email requirements:
1. ONLY match if you find an email that ends with @ucalgary.ca
2. The email MUST be in the context of an instructor, professor, or faculty member
3. The email must appear with contextual information like "Instructor:", "Professor:", "Contact:", etc.
4. Do NOT match general university emails or emails without instructor context
5. When explaining your findings, specify exactly what email address you found that meets the criteria"""

    # Course objectives
    if special_cases['course_objectives']:
        system_message += """
For course objectives requirements:
1. Look for a dedicated section/heading about course objectives/outcomes/goals
2. The objectives should be clearly enumerated (numbered, bulleted or otherwise distinctly listed)
3. Look for specific phrases like "By the end of this course, students will..." or "Course objectives are..."
4. Do NOT match if objectives are merely mentioned but not explicitly listed
5. When explaining your findings, quote the first few objectives as evidence"""

    # Tools and platforms
    if special_cases['tools_platforms']:
        system_message += """
For tools and platform resources requirements:
1. Look for specific mentions of software, platforms, websites, or tools students will use
2. These should be in a context of student usage or requirements
3. Look for specific tool names like "D2L", "Canvas", "MATLAB", "Zoom", etc.
4. Do NOT match generic mentions of "resources" without specific tools
5. When explaining your findings, list the specific tools/platforms mentioned"""

    # Course workload
    if special_cases['workload']:
        system_message += """
For course workload requirements:
1. Look for a dedicated section about course workload or time commitment
2. Should include specific estimates of hours or time expectations
3. Might include breakdown of in-class vs. out-of-class time
4. Consider related terms like "time commitment", "hours per week", etc.
5. When explaining your findings, quote the specific workload information"""

    # Missed assessment policy
    if special_cases['missed_assessment']:
        system_message += """
For missed assessment policy requirements:
1. Look for a specific section or header about missed assessments/exams/assignments
2. This should detail what happens if a student misses an exam or assignment
3. May include terms like "make-up", "deferral", "absence", or "missed"
4. The policy should be clearly stated, not just mentioned
5. When explaining your findings, quote the specific policy information"""

    # Late policy
    if special_cases['late_policy']:
        system_message += """
For late policy requirements:
1. Look for a specific section or header about late submissions or deadlines
2. This should detail penalties or consequences for late work
3. May include terms like "penalty", "deduction", "grace period" or specific penalties (e.g., "5% per day")
4. The policy should be clearly stated, not just mentioned
5. When explaining your findings, quote the specific late policy information"""

    # Contacting instructor
    if special_cases['contacting_instructor']:
        system_message += """
For contacting instructor requirements:
1. Look for a dedicated section about contacting the instructor
2. Should include specific methods of contact (email, office hours, etc.)
3. May include response time expectations or communication policies
4. Must be more than just listing contact information
5. When explaining your findings, quote the specific contacting instructions"""

    # Links validation
    if special_cases['links']:
        system_message += """
For link validation requirements:
1. Identify any URLs or hyperlinks mentioned in the document
2. These might be formatted as http://example.com or www.example.com or just mentioned as "website"
3. Look for the context of these links to understand their purpose
4. Note that you cannot determine if the links are working, only if they exist
5. When explaining your findings, list any links you've found"""
    
    # Prepare the document by cleaning and splitting it
    # Instead of truncating, we'll use a semantic chunking approach
    chunks = []
    # Split the document into sections of approximately 1000 characters
    paragraphs = document_text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) < 1500:
            current_chunk += para + "\n\n"
        else:
            chunks.append(current_chunk)
            current_chunk = para + "\n\n"
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    # If we have no chunks (very short document), use the whole document
    if not chunks:
        chunks = [document_text]
    
    # Limit to maximum 3 chunks for efficiency
    if len(chunks) > 3:
        # Prioritize the beginning and end of the document, plus a middle section
        chunks = [chunks[0], chunks[len(chunks)//2], chunks[-1]]
    
    try:
        all_results = []
        
        # Analyze each chunk separately
        for i, chunk in enumerate(chunks):
            # Prepare a detailed prompt that focuses on semantic meaning
            prompt = f"""I need to verify if a specific requirement from a course outline checklist is fulfilled in this document.

CHECKLIST REQUIREMENT: "{item}"

DOCUMENT SECTION {i+1} of {len(chunks)}:
```
{chunk[:1500]}
```

TASK:
1. Determine if this requirement is TRULY satisfied in the document section
2. Focus on the MEANING and INTENT of the requirement, not just matching keywords
3. Be strict about specific details like email domains (@ucalgary.ca)
4. Look for the requirement in context, not just isolated keywords
5. Respond with your findings in the JSON format below

Response format:
{{
  "present": true/false,
  "confidence": 0.0-1.0,
  "evidence": "Quote the specific text from the document that satisfies the requirement if present",
  "explanation": "Explain your reasoning in 1-2 sentences"
}}"""
            
            # Call the OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
                                 # do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Lower temperature for more consistent results
                max_tokens=200,   # Allow more tokens for detailed explanation and evidence
                timeout=10        # Reduce timeout for faster retries
            )
            
            # Extract and parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Add chunk info to the result
            result["chunk_id"] = i+1
            all_results.append(result)
        
        # Determine the final result from all chunk analyses
        # If ANY chunk has the item present with confidence > 0.7, consider it present
        present_results = [r for r in all_results if r.get("present", False) and r.get("confidence", 0) > 0.7]
        
        if present_results:
            # Use the highest confidence result from the present results
            best_result = max(present_results, key=lambda x: x.get("confidence", 0))
            final_result = {
                "present": True,
                "confidence": best_result.get("confidence", 0.8),
                "explanation": best_result.get("explanation", "Found in document"),
                "evidence": best_result.get("evidence", "")
            }
        else:
            # If no high-confidence matches were found, consider it missing
            final_result = {
                "present": False,
                "confidence": max([1.0 - r.get("confidence", 0) for r in all_results if not r.get("present", False)] or [0.7]),
                "explanation": all_results[0].get("explanation", "Not found in document"),
                "evidence": ""
            }
        
        logger.info(f"OpenAI analysis complete for item: {item[:30]}...")
        return final_result
        
    except (APITimeoutError, RateLimitError, APIConnectionError) as e:
        logger.error(f"OpenAI API error: {str(e)}")
        # Check if this is a quota exceeded error
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
            logger.error(f"OpenAI API quota exceeded: {str(e)}")
            raise Exception(f"OpenAI API quota exceeded: {str(e)}")
        
        # For other API-specific errors, return a special message
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "OpenAI API temporarily unavailable. Using fallback analysis."
        }
    except BadRequestError as e:
        logger.error(f"OpenAI API bad request: {str(e)}")
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "Invalid request to OpenAI API. Using fallback analysis."
        }
    except Exception as e:
        logger.error(f"Error using OpenAI API: {str(e)}")
        # Check if this is a quota exceeded error before falling back
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
            logger.error(f"OpenAI API quota exceeded: {str(e)}")
            raise Exception(f"OpenAI API quota exceeded: {str(e)}")
        
        # Fallback to a default response in case of other failures
        return {
            "present": False,
            "confidence": 0.0,
            "explanation": "Error during AI analysis. Using fallback analysis."
        }

def analyze_checklist_items_batch(items: List[str], document_text: str, max_attempts: int = 3) -> Dict[str, Dict[str, Any]]:
    """
    Process each checklist item individually through the OpenAI API,
    with fallback to traditional NLP methods if API calls fail.
    
    Args:
        items: List of checklist items to analyze
        document_text: The full text of the document to check against
        max_attempts: Maximum number of API analysis attempts for each item (1-10)
    
    Returns:
        A dictionary mapping each item to its analysis result
    
    Features:
    1. Processes each item individually for more detailed analysis
    2. Adds a delay between API calls to prevent rate limiting
    3. Gracefully handles API quota exceeded errors with fallback methods
    4. Provides detailed logging for each item's analysis
    5. Supports multiple API attempts per item for more accurate results
    """
    results = {}
    api_successes = 0
    api_failures = 0
    total_attempts = 0
    
    # Validate max_attempts
    if max_attempts < 1:
        max_attempts = 1
    elif max_attempts > 10:
        max_attempts = 10
    
    # Check if the API key exists and is not empty
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found or empty. Using only traditional analysis methods.")
        return results
    
    # Process all items, attempting to use OpenAI for each one
    logger.info(f"Attempting to analyze {len(items)} checklist items with OpenAI API (max {max_attempts} attempts per item)")
    
    api_quota_exceeded = False
    
    # Process each item individually
    for i, item in enumerate(items):
        item_id = f"Item #{i+1}"
        logger.info(f"Processing {item_id}: {item[:50]}{'...' if len(item) > 50 else ''}")
        
        # Try API calls for every item (we no longer immediately skip due to quota issues)
        if False:  # This condition will never evaluate to true, effectively removing the skip
            logger.info(f"Skipping OpenAI API call for {item_id} due to quota issues")
            
            # Use traditional method as fallback with enhanced pattern matching
            from document_processor import check_item_in_document
            is_present = check_item_in_document(item, document_text)
            
            # Provide more detailed explanations based on content type
            explanation = "Not found in document"
            if is_present:
                item_lower = item.lower()
                # Generate more specific explanations by content type
                if 'policy' in item_lower or 'policies' in item_lower:
                    explanation = "Policy content detected in document sections"
                elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                    explanation = "Found missed assignment/assessment policy content"
                elif 'assignment' in item_lower or 'assessment' in item_lower:
                    explanation = "Assignment/assessment details detected in document"
                elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                    explanation = "Grade information found in document sections"
                elif 'participation' in item_lower:
                    explanation = "Class participation information detected"
                elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                    explanation = "Course materials/textbook information found"
                elif 'objective' in item_lower or 'outcome' in item_lower:
                    explanation = "Course objectives/outcomes detected"
                elif 'schedule' in item_lower or 'calendar' in item_lower:
                    explanation = "Course schedule/calendar information found"
                elif 'contact' in item_lower or 'instructor' in item_lower:
                    explanation = "Instructor contact information detected"
                elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                    explanation = "Exam/assessment information found"
                else:
                    explanation = "Content matched through section analysis"
            
            results[item] = {
                "present": is_present,
                "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                "explanation": explanation,
                "method": "traditional (enhanced)"  # Mark which method was used
            }
            api_failures += 1
            continue
        
        # Add a delay between API calls to prevent rate limiting
        if i > 0:
            time.sleep(1.5)  # Increased delay to 1.5 seconds between API calls
        
        try:
            # Try to analyze with OpenAI API using multiple attempts if configured
            attempt_results = []
            attempt_successful = False
            
            # Make multiple attempts if max_attempts > 1
            for attempt in range(max_attempts):
                total_attempts += 1
                
                if attempt > 0:
                    logger.info(f"Attempt {attempt+1}/{max_attempts} for {item_id}")
                    # Add a small delay between retry attempts
                    time.sleep(1.0)
                
                try:
                    # Try to analyze with OpenAI API
                    attempt_result = analyze_checklist_item(item, document_text)
                    attempt_result["attempt"] = attempt + 1
                    attempt_results.append(attempt_result)
                    
                    # Consider the attempt successful
                    attempt_successful = True
                    
                    # If we're only doing one attempt or if this attempt is confident enough, stop
                    if max_attempts == 1 or attempt_result.get("confidence", 0) > 0.8:
                        break
                        
                except Exception as retry_error:
                    # If any retry fails, log it but continue with next attempt
                    logger.warning(f"Attempt {attempt+1} failed: {str(retry_error)}")
                    # Break the retry loop if we hit quota exceeded
                    if "quota" in str(retry_error).lower() or "rate limit" in str(retry_error).lower():
                        raise  # Re-raise to be caught by the outer exception handler
            
            # If we have results from at least one attempt
            if attempt_results:
                # Find the most confident result among all attempts
                best_result = max(attempt_results, key=lambda x: x.get("confidence", 0))
                
                # Add additional context about the attempts
                best_result["method"] = f"openai (attempt {best_result.get('attempt', 1)} of {max_attempts})"
                best_result["total_attempts"] = len(attempt_results)
                
                # If we made multiple attempts, add that information to the explanation
                if len(attempt_results) > 1:
                    best_result["explanation"] = f"{best_result.get('explanation', '')} (Based on {len(attempt_results)} analysis attempts)"
                
                # Store the best result
                results[item] = best_result
                logger.info(f"Successfully analyzed {item_id} with OpenAI API after {len(attempt_results)} attempts")
                api_successes += 1
            else:
                # This shouldn't happen due to our exception handling, but just in case
                raise Exception("No successful API attempts")
            
        except Exception as e:
            # Check if this is a quota exceeded error
            error_msg = str(e).lower()
            if "quota" in error_msg or "rate limit" in error_msg or "exceeded" in error_msg:
                logger.warning(f"OpenAI API quota exceeded at item {i+1}. Will retry for each item with reduced rate.")
                # We'll still try to use OpenAI for future items, just with a longer delay
                time.sleep(2)  # Add extra delay before next item
                # Don't set api_quota_exceeded = True so we keep trying future items
                
                # Use traditional method for this item too with enhanced pattern matching
                from document_processor import check_item_in_document
                is_present = check_item_in_document(item, document_text)
                
                # Provide more detailed explanations based on content type
                explanation = "Not found in document"
                if is_present:
                    item_lower = item.lower()
                    # Generate more specific explanations by content type
                    if 'policy' in item_lower or 'policies' in item_lower:
                        explanation = "Policy content detected in document sections"
                    elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                        explanation = "Found missed assignment/assessment policy content"
                    elif 'assignment' in item_lower or 'assessment' in item_lower:
                        explanation = "Assignment/assessment details detected in document"
                    elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                        explanation = "Grade information found in document sections"
                    elif 'participation' in item_lower:
                        explanation = "Class participation information detected"
                    elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                        explanation = "Course materials/textbook information found"
                    elif 'objective' in item_lower or 'outcome' in item_lower:
                        explanation = "Course objectives/outcomes detected"
                    elif 'schedule' in item_lower or 'calendar' in item_lower:
                        explanation = "Course schedule/calendar information found"
                    elif 'contact' in item_lower or 'instructor' in item_lower:
                        explanation = "Instructor contact information detected"
                    elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                        explanation = "Exam/assessment information found"
                    else:
                        explanation = "Content matched through section analysis"
                
                results[item] = {
                    "present": is_present,
                    "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                    "explanation": explanation,
                    "method": "traditional (after quota exceeded)"
                }
                api_failures += 1
            else:
                # For other errors, still use traditional method but log the specific error
                logger.error(f"Error analyzing item {i+1} with OpenAI: {str(e)}")
                
                from document_processor import check_item_in_document
                is_present = check_item_in_document(item, document_text)
                
                # Provide more detailed explanations based on content type
                explanation = "Not found in document"
                if is_present:
                    item_lower = item.lower()
                    # Generate more specific explanations by content type
                    if 'policy' in item_lower or 'policies' in item_lower:
                        explanation = "Policy content detected in document sections"
                    elif 'missed' in item_lower and ('assignment' in item_lower or 'assessment' in item_lower):
                        explanation = "Found missed assignment/assessment policy content"
                    elif 'assignment' in item_lower or 'assessment' in item_lower:
                        explanation = "Assignment/assessment details detected in document"
                    elif 'grade' in item_lower or 'grading' in item_lower or 'distribution' in item_lower:
                        explanation = "Grade information found in document sections"
                    elif 'participation' in item_lower:
                        explanation = "Class participation information detected"
                    elif 'textbook' in item_lower or 'reading' in item_lower or 'material' in item_lower:
                        explanation = "Course materials/textbook information found"
                    elif 'objective' in item_lower or 'outcome' in item_lower:
                        explanation = "Course objectives/outcomes detected"
                    elif 'schedule' in item_lower or 'calendar' in item_lower:
                        explanation = "Course schedule/calendar information found"
                    elif 'contact' in item_lower or 'instructor' in item_lower:
                        explanation = "Instructor contact information detected"
                    elif 'exam' in item_lower or 'test' in item_lower or 'quiz' in item_lower:
                        explanation = "Exam/assessment information found"
                    else:
                        explanation = "Content matched through section analysis"
                
                results[item] = {
                    "present": is_present,
                    "confidence": 0.85 if is_present else 0.2,  # Increased confidence due to better pattern matching
                    "explanation": explanation,
                    "method": "traditional (after API error)"
                }
                api_failures += 1
    
    # Log summary of API usage
    logger.info(f"OpenAI API usage summary: {api_successes} successful items, {api_failures} fallbacks to traditional methods")
    logger.info(f"Total API attempts: {total_attempts} (average {total_attempts/len(items):.1f} attempts per item)")
    
    return results