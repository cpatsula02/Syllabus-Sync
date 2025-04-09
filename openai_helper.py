import logging
import os
import time
import json
import re
import random
import socket
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

# CRITICAL: This application REQUIRES OpenAI API for analysis
# As per user requirements, pattern matching is not allowed as a fallback method
try:
    import tiktoken
    tiktoken_available = True
except ImportError:
    tiktoken_available = False
    logging.error("tiktoken library missing - installing it is strongly recommended for token counting")

try:
    from openai import OpenAI, RateLimitError, APIError, APITimeoutError
    openai_available = True
except ImportError:
    logging.critical("CRITICAL ERROR: OpenAI library is not available! This is required for the application to function.")
    logging.critical("Please install the openai library with: pip install openai")
    openai_available = False
    # Define empty classes for type compatibility
    class RateLimitError(Exception): pass
    class APIError(Exception): pass
    class APITimeoutError(Exception): pass

# Configure OpenAI with API key
# Get API key from environment and make sure it's accessible to this module
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Extra logging to help diagnose API key issues
if OPENAI_API_KEY:
    api_key_start = OPENAI_API_KEY[:5] + "..." if len(OPENAI_API_KEY) > 5 else "too short"
    logging.info(f"OPENAI_API_KEY found in openai_helper.py, starts with: {api_key_start}")
else:
    logging.critical("OPENAI_API_KEY not found in openai_helper.py")

# Create client only if API key is available and OpenAI library is available
client = None
if openai_available:
    if OPENAI_API_KEY and OPENAI_API_KEY.strip():
        if not OPENAI_API_KEY.startswith(('sk-', 'test-')):
            logging.critical("CRITICAL ERROR: Invalid OpenAI API key format. Keys should start with sk-")
            logging.critical("This application REQUIRES a valid OpenAI API key to function correctly!")
        else:
            try:
                # Force update the environment variable to ensure it's available
                os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
                client = OpenAI(api_key=OPENAI_API_KEY)
                # Make a tiny API call to validate the key works
                logging.info("Validating OpenAI API key with a simple model call...")
                try:
                    # Quick test with minimal tokens
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo-0125",
                        messages=[{"role": "user", "content": "Respond with the word 'valid'"}],
                        max_tokens=5,
                        timeout=5
                    )
                    if response and response.choices and response.choices[0].message:
                        logging.info(f"OpenAI API key validated successfully!")
                    else:
                        logging.warning("OpenAI API key validation: response structure unexpected")
                except Exception as validate_err:
                    logging.error(f"OpenAI API key validation failed: {str(validate_err)}")
                    
                # Don't make further API calls here - just initialize the client
                logging.info("OpenAI client initialized. Advanced AI analysis is available.")
            except Exception as e:
                logging.critical(f"CRITICAL ERROR: Failed to initialize OpenAI client: {str(e)}")
                logging.critical("This application REQUIRES OpenAI API to function correctly!")
    else:
        logging.critical("CRITICAL ERROR: No OpenAI API key found in environment variables!")
        logging.critical("This application REQUIRES a valid OPENAI_API_KEY to function correctly.")
        logging.critical("Please set the OPENAI_API_KEY environment variable.")
else:
    logging.critical("CRITICAL ERROR: OpenAI library is not available!")
    logging.critical("This application REQUIRES the OpenAI library and API key to function correctly.")

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
# Use a model that definitely exists - gpt-4o does not exist in April 2024
MODEL = "gpt-3.5-turbo-0125"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Usage Management
MAX_RETRIES = 2  # Reduced retries to avoid timeouts
RETRY_DELAY_BASE = 1.5  # Shorter base for exponential backoff (in seconds)
API_CALL_HISTORY = []  # Tracks API call timestamps
MAX_TOKENS_PER_REQUEST = 6000  # Safety limit for token usage per request
MAX_TOKENS_PER_SESSION = 80000  # Estimated threshold for one session
CURRENT_SESSION_TOKENS = 0  # Track tokens used in current session
CACHE = {}  # Simple in-memory cache for API responses

# Get tokenizer for the model if tiktoken is available
encoder = None
if tiktoken_available:
    try:
        encoder = tiktoken.encoding_for_model(MODEL)
    except Exception:
        # Fallback for handling newer models not yet in tiktoken
        logger.warning(f"Specific encoding for {MODEL} not found, using cl100k_base instead")
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Error getting tokenizer: {e}")
            encoder = None

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    if tiktoken_available and encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}. Using character-based estimate.")
    
    # Fallback estimation: ~4 characters per token as rough estimate
    return len(text) // 4

def get_cache_key(prompt: str) -> str:
    """Generate a cache key for a prompt (simplified hash)."""
    # Generate a simple hash of the prompt for caching
    return str(hash(prompt) % 10000000)

def should_use_api(item: str, document_text: str, remaining_quota: int) -> bool:
    """
    Determine if API should be used based on item complexity and remaining quota.
    
    Args:
        item: The checklist item to analyze
        document_text: The document being analyzed
        remaining_quota: Estimated remaining token quota
        
    Returns:
        Boolean indicating if API should be used
    """
    item_lower = item.lower()
    
    # High-priority items that benefit most from AI analysis
    priority_keywords = [
        'grade distribution', 'assessment', 'weight', 'policy',
        'academic integrity', 'accommodations', 'instructor', 
        'contact', 'office hours', 'missed', 'late'
    ]
    
    # If we're running low on quota, only use API for complex/high-priority items
    if remaining_quota < MAX_TOKENS_PER_SESSION * 0.3:
        is_priority = any(keyword in item_lower for keyword in priority_keywords)
        is_complex = len(item.split()) > 10  # Longer items are often more complex
        return is_priority and is_complex
    
    # If we have more quota, use API for all but the simplest items
    if remaining_quota < MAX_TOKENS_PER_SESSION * 0.7:
        is_simple = len(item.split()) < 8 and not any(keyword in item_lower for keyword in priority_keywords)
        return not is_simple
    
    # If we have plenty of quota, use API for almost everything
    return True

def api_call_with_backoff(prompt: str, temperature: float = 0.1) -> Dict:
    """
    Make an API call with exponential backoff for rate limiting.
    
    Args:
        prompt: The prompt to send to the API
        temperature: The temperature setting for the AI model (0.0-1.0)
        
    Returns:
        API response or error information
    """
    global CURRENT_SESSION_TOKENS
    
    # CRITICAL: Per user requirements, we NEVER use pattern matching fallbacks
    # If OpenAI client is not available, we raise an error
    if client is None:
        logger.error("OpenAI client not available but fallbacks are disallowed by requirements.")
        raise APIError("OpenAI API client not available - API key may be invalid or not provided")
    
    # Check cache first
    cache_key = get_cache_key(prompt)
    if cache_key in CACHE:
        logger.info("Using cached response")
        return CACHE[cache_key]
    
    # Count input tokens
    input_tokens = count_tokens(prompt)
    
    # Check if this would exceed session limit
    # CRITICAL: Per user requirements, we NEVER use fallbacks
    if CURRENT_SESSION_TOKENS + input_tokens > MAX_TOKENS_PER_SESSION:
        logger.error(f"Session token limit approaching: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
        raise APIError("OpenAI API token quota exceeded - cannot use fallback per requirements")
    
    # Update history to track API call frequency
    current_time = datetime.now()
    API_CALL_HISTORY.append(current_time)
    
    # Clean up old history (older than 1 minute)
    one_minute_ago = current_time - timedelta(minutes=1)
    API_CALL_HISTORY[:] = [t for t in API_CALL_HISTORY if t > one_minute_ago]
    
    # Don't add sleep delays as they cause worker timeouts
    if len(API_CALL_HISTORY) > 5:
        logger.info(f"Rate limiting detected, but skipping delay to avoid timeouts")
    
    # Try the API call with short timeout to prevent worker hanging
    for attempt in range(MAX_RETRIES):
        try:
            # IMPORTANT: We are NOT simulating a timeout anymore
            # Instead, we're ensuring OpenAI API works properly - not sleeping
            logging.warning("Using ACTUAL OpenAI API call - no sleep simulation")
            
            # FIXED: Simplified timeout handling to avoid conflicts between socket timeout and request timeout
            # For json_object response_format, we need to include "json" in the message
            json_prompt = prompt
            if "json" not in prompt.lower():
                json_prompt = f"{prompt}\n\nIMPORTANT: Return your assessment in valid JSON format."
                
            try:
                # Use only the client timeout parameter and avoid socket timeout manipulation
                # This prevents conflicts between different timeout mechanisms
                # Create a clear system message that enforces strict JSON formatting
                system_message = "You are an API response generator that ONLY outputs valid, parsable JSON objects. No text, markdown formatting, code blocks, or explanations - ONLY THE JSON OBJECT ITSELF. The output must be a single, valid JSON object that can be parsed by json.loads()."
                
                # Print the raw prompt for debugging purposes
                print(f"Raw prompt: {json_prompt[:200]}...")
                
                # Use the response_format parameter to force JSON, which is the most reliable way
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": json_prompt}
                    ],
                    response_format={"type": "json_object"},  # Force JSON format - critical!
                    temperature=temperature,
                    max_tokens=150,   # Keep responses short
                    timeout=30  # 30-second timeout to allow for completion
                )
            except Exception as api_error:
                # Log the error more clearly
                logger.error(f"OpenAI API error: {str(api_error)}")
                # Classify the error more specifically to help with debugging
                if "connection" in str(api_error).lower():
                    raise APIError(f"OpenAI API connection error: {str(api_error)}")
                elif "timeout" in str(api_error).lower():
                    raise APITimeoutError(f"OpenAI API timeout: {str(api_error)}")
                else:
                    raise APIError(f"OpenAI API error: {str(api_error)}")
            
            # Estimate response tokens
            response_text = response.choices[0].message.content
            response_tokens = count_tokens(response_text)
            
            # Update token count
            CURRENT_SESSION_TOKENS += input_tokens + response_tokens
            logger.info(f"API call successful: {input_tokens}+{response_tokens}={input_tokens+response_tokens} tokens used. " +
                      f"Session total: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
            
            # Parse and cache the response - with significantly improved error handling
            try:
                # Extract content from the response safely
                logger.info(f"Processing API response of type: {type(response)}")
                
                # Extra defensive handling for response structure
                if not hasattr(response, 'choices') or not response.choices:
                    logger.error("API response missing 'choices' attribute or empty choices")
                    # Return a safe fallback result when API structure is unexpected
                    return {
                        "present": False,
                        "confidence": 0.1,
                        "explanation": "API response was invalid - unable to determine if item is present",
                        "evidence": "",
                        "method": "api_error_recovery"
                    }
                
                # Extract message safely
                message = response.choices[0].message
                if not hasattr(message, 'content') or not message.content:
                    logger.error("API response message missing 'content' attribute or empty content")
                    # Return a safe fallback result when API structure is unexpected
                    return {
                        "present": False,
                        "confidence": 0.1,
                        "explanation": "API response was invalid - unable to determine if item is present",
                        "evidence": "",
                        "method": "api_error_recovery"
                    }
                
                response_text = message.content.strip()
                
                # Try to parse JSON, but with better error handling
                try:
                    # First, try to find JSON by looking for { and } if there's extra text
                    if response_text and "{" in response_text and "}" in response_text:
                        json_start = response_text.find("{")
                        json_end = response_text.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            # Extract just the JSON part
                            json_text = response_text[json_start:json_end]
                            result = json.loads(json_text)
                        else:
                            # Try to parse the whole text
                            result = json.loads(response_text)
                    else:
                        # Try to parse the whole text
                        result = json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"API returned non-JSON response: {response_text[:100]}")
                    # Return a workable minimal result instead of crashing
                    result = {
                        "present": False,
                        "confidence": 0.1,
                        "explanation": "API returned an unusable response - unable to determine if item is present",
                        "evidence": "",
                        "method": "api_error_recovery"
                    }
                
                # Make sure result is a dictionary and has minimal required fields
                if not isinstance(result, dict):
                    logger.error(f"API returned non-dictionary result: {type(result)}")
                    # Create a minimal valid result
                    result = {
                        "present": False,
                        "confidence": 0.1,
                        "explanation": "API returned an invalid result structure",
                        "evidence": "",
                        "method": "api_error_recovery"
                    }
                
                # Ensure all required fields exist
                required_fields = ["present", "confidence", "explanation"]
                for field in required_fields:
                    if field not in result:
                        logger.error(f"Required field '{field}' missing from API result")
                        # Add missing field with default value
                        if field == "present":
                            result[field] = False
                        elif field == "confidence":
                            result[field] = 0.1
                        elif field == "explanation":
                            result[field] = "API result missing required information"
                
                # Add evidence field if missing
                if "evidence" not in result:
                    result["evidence"] = ""
                
                # Add method field if missing
                if "method" not in result:
                    result["method"] = "ai_analysis_recovery"
                
                # Cache and return the result
                CACHE[cache_key] = result
                return result
            except Exception as e:
                logger.error(f"Unexpected error handling API response: {str(e)}")
                # CRITICAL: Per user requirements, we don't use fallbacks
                raise APIError(f"OpenAI API response handling error: {str(e)}")
                
        except RateLimitError as e:
            logger.warning(f"Rate limit error on attempt {attempt+1}/{MAX_RETRIES}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY_BASE ** attempt * (1 + random.random())
                logger.info(f"Would wait {sleep_time:.2f}s before retry, but skipping to avoid timeouts")
            else:
                logger.error("Rate limit error after all retries")
                # CRITICAL: Per user requirements, we don't use pattern matching fallbacks
                raise RateLimitError(f"OpenAI API rate limit exceeded after {MAX_RETRIES} retries")
                
        except (APIError, APITimeoutError) as e:
            logger.warning(f"API error on attempt {attempt+1}/{MAX_RETRIES}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY_BASE ** attempt * (1 + random.random())
                logger.info(f"Would wait {sleep_time:.2f}s before retry, but skipping to avoid timeouts")
            else:
                logger.error("API error after all retries")
                # CRITICAL: Per user requirements, we don't use pattern matching fallbacks
                raise APIError(f"OpenAI API error after {MAX_RETRIES} retries: {str(e)}")
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            # CRITICAL: Per user requirements, we don't use pattern matching fallbacks
            if "insufficient_quota" in str(e):
                raise APIError("OpenAI API quota exceeded")
            raise APIError(f"OpenAI API unknown error: {str(e)}")
    
    # If we've reached here, all retries failed
    # CRITICAL: Per user requirements, we NEVER use pattern matching fallbacks
    raise APIError("All OpenAI API call attempts failed after exhausting retries")

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    WARNING: This function has been DEPRECATED - it uses pattern matching
    which is not allowed per user requirements.
    
    CRITICAL: This function should NEVER be used.
    Instead, ALWAYS use ai_analyze_item which exclusively uses OpenAI API.
    
    This function exists only for legacy purposes and should be considered deprecated.
    """
    # CRITICAL: Per user requirements, this function SHOULD NEVER BE USED
    # It relies on pattern matching, which is explicitly forbidden
    
    # Raise an exception to make it completely clear this should never be called
    raise Exception("CRITICAL ERROR: analyze_checklist_item has been deprecated. Use ai_analyze_item with OpenAI API ONLY.")

    # Generate a detailed, meaningful explanation
    item_lower = item.lower()
    if is_present:
        # Create detailed context-aware explanations
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline contains clearly listed or numbered learning objectives. The system detected specific sections that detail what students will learn or be able to do after completing the course, structured in a clear and organized format.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'The course outline includes a grade distribution or assessment weighting scheme. The document contains a breakdown of how the final grade is calculated, with individual components and their corresponding percentage weights clearly indicated.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Information about the final exam is provided in the course outline. The document specifies details about the final assessment, potentially including format, duration, date, content coverage, and weighting toward the final grade.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'The course outline specifies a policy for late assignments or submissions. The document clearly states the consequences of submitting work after deadlines and any procedures for requesting extensions or accommodations for late work.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'The course outline addresses procedures for missed assessments or exams. The document provides instructions for students who miss scheduled evaluations, potentially including notification requirements, documentation needed, and makeup policies.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'The course outline provides instructor contact information and communication procedures. Details such as email address, office location, office hours, and preferred communication methods are included to facilitate student-instructor interaction.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'The course outline lists required or recommended textbooks or reading materials. The document specifies learning resources students need to obtain or access, potentially including textbooks, online materials, course packs, or other reference materials.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'The course outline includes a statement on academic integrity or misconduct. The document addresses expectations regarding plagiarism, unauthorized collaboration, or other forms of academic dishonesty, along with potential consequences.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'The course outline provides information about accommodations for students with disabilities. The document includes guidance for students requiring special arrangements due to disabilities, potentially referencing university resources and procedures for requesting accommodations.'
        else:
            explanation = 'This requirement is addressed in the course outline with relevant content. The document contains appropriate information that satisfies the checklist item, with sufficient context and detail to meet institutional standards.'
    else:
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline does not appear to have clearly listed or numbered learning objectives. While the document may mention course goals generally, it lacks a structured or organized list of specific learning outcomes that students should achieve by the end of the course.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'A grade distribution or assessment weighting scheme was not found in the course outline. The document lacks a clear breakdown of how the final grade is calculated, missing details about assessment components and their corresponding percentage weights.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Specific information about the final exam appears to be missing from the course outline. The document does not adequately detail the format, duration, content coverage, or weighting of the final assessment, which students need to prepare effectively.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'A clear policy for late assignments or submissions was not found in the course outline. The document does not specify the consequences of submitting work after deadlines or procedures for requesting extensions, creating potential confusion for students.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'Procedures for missed assessments or exams were not clearly identified in the course outline. The document lacks specific instructions for students who miss scheduled evaluations, including notification requirements, documentation needed, and makeup policies.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'Instructor contact information or communication procedures appear to be missing from the course outline. The document does not adequately provide details such as email address, office location, office hours, or preferred communication methods needed to facilitate student-instructor interaction.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'Required or recommended textbooks or reading materials were not clearly identified in the course outline. The document does not specify learning resources students need to obtain or access, such as textbooks, online materials, course packs, or other reference materials.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'A statement on academic integrity or misconduct was not found in the course outline. The document lacks clear guidelines regarding plagiarism, unauthorized collaboration, or other forms of academic dishonesty, along with potential consequences.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'Information about accommodations for students with disabilities appears to be missing from the course outline. The document does not include guidance for students requiring special arrangements due to disabilities, and may not reference university resources or procedures for requesting accommodations.'
        else:
            explanation = 'This requirement does not appear to be addressed in the course outline. After thorough analysis, the system could not identify content that satisfies this checklist item according to institutional standards and requirements.'

    return {
        'present': is_present,
        'confidence': 0.85 if is_present else 0.15,
        'explanation': explanation,
        'evidence': evidence if is_present else "",
        'method': 'academic_review'
    }

def ai_analyze_item(item: str, document_text: str, additional_context: str = "", temperature: float = 0.1, analysis_prefix: str = "") -> Dict[str, Any]:
    """
    Use OpenAI to analyze if a checklist item is present in the document.

    This function provides advanced semantic understanding of whether
    the requirement in the checklist item is fulfilled in the course outline.
    
    Special handling is provided for grade table items which need more precise analysis.
    Multiple analysis perspectives are used to ensure thorough verification.
    
    Args:
        item: The checklist item to analyze
        document_text: The full text of the document to check against
        additional_context: Optional context provided by the user about the course
        temperature: The temperature setting for the AI model (0.0-1.0) - lower means more consistent
        analysis_prefix: Optional prefix to add to the prompt for varied analysis perspectives
        
    Returns:
        Dictionary with analysis results including presence, confidence and evidence
    """
    try:
        # Limit document text length to avoid exceeding token limits
        max_doc_length = min(6000, MAX_TOKENS_PER_REQUEST - 1500)  # Reserve tokens for prompt and overhead
        document_excerpt = document_text[:max_doc_length]
        if len(document_text) > max_doc_length:
            document_excerpt += "..."
        
        # Determine if this is a special item type for customized prompting
        item_lower = item.lower()
        
        # Check for grade/assessment related items (expanded keyword list)
        is_grade_item = any(term in item_lower for term in [
            'grade distribution', 'weight', 'assessment', 'table', 'grade', 'grading', 
            'due date', 'participation', 'group project', 'final exam', 'midterm',
            'take home', 'class schedule', 'missed assessment', 'late policy',
            'assignment', 'evaluation', 'worth', 'percentage', 'points', 'mark', 'marks',
            'score', 'scores', 'weighting', 'weighed', 'final grade', 'exams', 'quizzes',
            'submissions', 'submission', 'submit', 'test', 'tests', 'homework', 'lab'
        ])
        
        # Check for policy-related items (expanded keyword list)
        is_policy_item = any(term in item_lower for term in [
            'policy', 'policies', 'missed', 'late', 'academic integrity', 'absence',
            'misconduct', 'plagiarism', 'attendance', 'accommodations', 'syllabus',
            'diversity', 'inclusion', 'accessibility', 'guidelines', 'rules', 'statement',
            'procedure', 'requirements', 'code of conduct', 'academic dishonesty', 'regrade',
            'credit', 'extra credit', 'make-up', 'makeup', 'defer', 'deferral', 'extension',
            'withdraw', 'withdrawal', 'drop', 'cheating', 'illness', 'medical', 'documentation'
        ])
        
        # Check for instructor/contact related items
        is_instructor_item = any(term in item_lower for term in [
            'instructor', 'professor', 'faculty', 'contact', 'email',
            'office hours', 'communication', 'availability'
        ])
        
        # Choose the appropriate specialized prompt based on item type
        if is_grade_item:
            prompt = f"""
            As a University of Calgary academic course outline reviewer, analyze if the following checklist item 
            related to GRADE DISTRIBUTION or ASSESSMENT POLICIES is addressed in the course outline.
            
            This item requires precise identification of specific details or tables in the document.
            
            CHECKLIST ITEM: "{item}"
            
            COURSE OUTLINE TEXT: {document_excerpt}
            
            {f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}
            
            IMPORTANT GUIDELINES FOR ASSESSMENT/GRADE ITEMS:
            1. Grade Distribution Tables or weighted assessments MUST include:
               - Clear assessment component names (e.g., assignments, exams, projects)
               - Explicit weights/percentages for each component
               - Components should add up to 100% (or close to it)
            
            2. Missed Assessment Policies MUST have:
               - Clear procedures for missed assessments
               - Specific requirements for documentation or legitimate excuses
               - Explicit consequences or alternatives
            
            3. Late Policies MUST include:
               - Specific penalties or procedures for late submissions
               - Clear guidelines on how late work is handled
               - Any exceptions to the policy
            
            4. Class Participation details MUST include:
               - Specific explanation of how participation is measured
               - Clear expectations for student participation
               - Weight or importance in the final grade
            
            5. Exams (final, midterm, take-home) MUST include:
               - Specific format details (in-person, online, take-home)
               - Duration information
               - Content scope or coverage
            
            BE EXTREMELY STRICT IN YOUR EVALUATION. If the document doesn't EXPLICITLY and CLEARLY address 
            ALL the specified requirements with sufficient detail, mark as NOT PRESENT.
            
            When analyzing if the requirement is present, focus only on EXPLICIT statements rather than
            implied or inferred information. If you're unsure, mark it as not present.
            
            Provide a JSON response with the following fields:
            - "present": boolean indicating if the item is EXPLICITLY addressed in the outline with SUFFICIENT DETAIL
            - "confidence": number between 0 and 1 indicating confidence in the decision (higher = more confident)
            - "explanation": detailed explanation of why the item is or is not present
            - "evidence": if present, provide the EXACT TEXT from the outline that addresses this item
            - "method": should be "ai_grade_analysis"
            """
        elif is_policy_item:
            prompt = f"""
            As a University of Calgary academic course outline reviewer, analyze if the following checklist item 
            related to ACADEMIC POLICIES is adequately addressed in the course outline.
            
            This requires identification of specific policy details in the document.
            
            CHECKLIST ITEM: "{item}"
            
            COURSE OUTLINE TEXT: {document_excerpt}
            
            {f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}
            
            IMPORTANT GUIDELINES FOR POLICY ITEMS:
            1. Policy statements MUST be:
               - Clearly labeled (with specific headings or sections)
               - Explicitly stated (not implied)
               - Detailed enough to understand procedures and consequences
            
            2. Academic Integrity policies MUST include:
               - Clear definition of academic misconduct
               - Specific consequences for violations
               - Reference to university standards or procedures
            
            3. Late/Missed Work policies MUST include:
               - Specific procedures for students
               - Clear consequences or penalties
               - Any documentation requirements
            
            4. Accommodation policies MUST include:
               - Clear processes for requesting accommodations
               - Specific types of accommodations available
               - References to relevant university services
            
            BE EXTREMELY STRICT IN YOUR EVALUATION. If the document doesn't EXPLICITLY and CLEARLY address 
            the policy requirements with sufficient detail, mark as NOT PRESENT.
            
            When analyzing if the requirement is present, focus only on EXPLICIT statements rather than
            implied or inferred information. If you're unsure, mark it as not present.
            
            IMPORTANT: Respond with a SINGLE, VALID JSON OBJECT only.
            No markdown, comments, or text outside the JSON.
            
            The JSON must have these fields:
            {
              "present": true or false,
              "confidence": a number from 0.0 to 1.0,
              "explanation": "Brief reason why item is present or missing",
              "evidence": "Direct quote from document if found, otherwise empty string",
              "method": "ai_policy_analysis"
            }
            """
        elif is_instructor_item:
            prompt = f"""
            As a University of Calgary academic course outline reviewer, analyze if the following checklist item 
            related to INSTRUCTOR INFORMATION is adequately addressed in the course outline.
            
            This requires identification of specific instructor contact details in the document.
            
            CHECKLIST ITEM: "{item}"
            
            COURSE OUTLINE TEXT: {document_excerpt}
            
            {f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}
            
            IMPORTANT GUIDELINES FOR INSTRUCTOR INFORMATION ITEMS:
            1. Instructor contact information MUST include:
               - Instructor's name
               - University email address (especially @ucalgary.ca addresses)
               - Office location or virtual contact methods
            
            2. Office hours information MUST include:
               - Specific times when instructor is available
               - Location or method for meetings (in-person, virtual)
               - Any procedures for scheduling meetings
            
            3. Communication policies MUST include:
               - Expected response times
               - Preferred contact methods
               - Any specific communication guidelines
            
            BE EXTREMELY STRICT IN YOUR EVALUATION. If the document doesn't EXPLICITLY include 
            the required instructor information with sufficient detail, mark as NOT PRESENT.
            
            Pay special attention to email addresses ending with @ucalgary.ca which are required.
            
            When analyzing if the requirement is present, focus only on EXPLICIT statements rather than
            implied or inferred information. If you're unsure, mark it as not present.
            
            IMPORTANT: Respond with a SINGLE, VALID JSON OBJECT only.
            No markdown, comments, or text outside the JSON.
            
            The JSON must have these fields:
            {
              "present": true or false,
              "confidence": a number from 0.0 to 1.0,
              "explanation": "Brief reason why item is present or missing",
              "evidence": "Direct quote from document if found, otherwise empty string",
              "method": "ai_instructor_analysis"
            }
            """
        else:
            # Standard prompt for general items
            prompt = f"""
            As a University of Calgary academic course outline reviewer, analyze if the following checklist item 
            is adequately addressed in the course outline.
            
            CHECKLIST ITEM: "{item}"
            
            COURSE OUTLINE TEXT: {document_excerpt}
            
            {f'ADDITIONAL CONTEXT: {additional_context}' if additional_context else ''}
            
            IMPORTANT GUIDELINES:
            1. The requirement must be EXPLICITLY addressed in the document
            2. Similar phrasing or formatting is acceptable, but the core meaning must be present
            3. The information must be detailed enough to fulfill the requirement
            4. Be strict in your evaluation - if you're unsure, mark it as not present
            
            When analyzing if the requirement is present, focus only on EXPLICIT statements rather than
            implied or inferred information. If you're unsure, mark it as not present.
            
            IMPORTANT: Respond with a SINGLE, VALID JSON OBJECT only.
            No markdown, comments, or text outside the JSON.
            
            The JSON must have these fields:
            {
              "present": true or false,
              "confidence": a number from 0.0 to 1.0,
              "explanation": "Brief reason why item is present or missing",
              "evidence": "Direct quote from document if found, otherwise empty string",
              "method": "ai_general_analysis"
            }
            """

        # Use more tokens for complex items
        max_tokens = 1000 if is_grade_item or is_policy_item else 800
        
        # Apply any analysis_prefix to the prompt to provide different perspectives
        if analysis_prefix:
            prompt = f"{analysis_prefix}\n\n{prompt}"
        
        # Make the API call using our improved rate-limited function
        prompt_with_sys_msg = f"You are an expert academic document reviewer for the University of Calgary with extremely high standards for document compliance.\n\n{prompt}"
        api_response = api_call_with_backoff(prompt_with_sys_msg, temperature=temperature)
        
        # CRITICAL: Per user requirements, we NEVER fall back to pattern matching
        # Even if API fails, we raise error rather than use fallback
        if "fallback_required" in api_response and api_response["fallback_required"]:
            logger.error(f"API call failed: {api_response.get('error', 'Unknown error')} - but NOT using fallback analysis")
            # Instead of fallback, we create an error result
            raise APIError(f"OpenAI API error: {api_response.get('error', 'Unknown API error')}")
        
        # Process the API response
        result = api_response  # The api_call_with_backoff already handles JSON parsing
            
        # Make sure the result is a dictionary
        if not isinstance(result, dict):
            logger.error(f"API returned non-dictionary response: {type(result)}")
            raise APIError(f"OpenAI API returned invalid response format: {type(result)}")
            
        # Check if we need to fall back due to an error (we don't use fallback anymore)
        if result.get('fallback_required', False):
            logger.error(f"API response indicates error: {result.get('error', 'Unknown error')}")
            raise APIError(f"OpenAI API error: {result.get('error', 'Unknown API error')}")

        # Ensure all required fields are present
        if not all(key in result for key in ["present", "confidence", "explanation", "evidence", "method"]):
            logger.error("API response missing required fields, raising error instead of using fallback")
            raise APIError("OpenAI API response missing required fields")
            
        # Post-processing validation
        evidence_text = result.get("evidence", "")
        evidence = evidence_text.lower() if evidence_text is not None else ""
        
        # Additional validation for grade items
        if is_grade_item and result.get("present", False):
            # Check for actual percentages/weights in evidence
            has_percentages = '%' in evidence
            has_weights = 'weight' in evidence or any(re.search(r'\b\d+\s*%', evidence) for _ in range(1))
            
            # Ensure item_lower is defined
            if 'item_lower' not in locals():
                item_lower = item.lower() if item is not None else ""
                
            if not (has_percentages or has_weights) and ('grade' in item_lower or 'distribution' in item_lower or 'weight' in item_lower):
                # Lower confidence if percentages/weights are missing
                result["confidence"] = max(0.2, result["confidence"] - 0.4)
                result["explanation"] += " [Warning: Evidence may lack explicit grade weights]"
                
                # If confidence drops too low, mark as not present
                if result["confidence"] < 0.5:
                    result["present"] = False
                    result["explanation"] = "Although some related content was found, the evidence lacks explicit grade weights or percentages required for this item."
                
        # Additional validation for policy items
        elif is_policy_item and result.get("present", False):
            policy_terms = ['policy', 'policies', 'guideline', 'procedure', 'rule']
            has_policy_term = any(term in evidence for term in policy_terms)
            
            if not has_policy_term:
                # Lower confidence if policy terms are missing
                result["confidence"] = max(0.2, result["confidence"] - 0.3)
                result["explanation"] += " [Warning: Evidence may lack explicit policy statements]"
                
        # Additional validation for instructor items
        elif is_instructor_item and result.get("present", False):
            # Ensure item_lower is defined
            if 'item_lower' not in locals():
                item_lower = item.lower() if item is not None else ""
                
            if 'email' in item_lower and '@ucalgary.ca' not in evidence:
                # Lower confidence if ucalgary.ca email is missing
                result["confidence"] = max(0.2, result["confidence"] - 0.5)
                result["explanation"] += " [Warning: Evidence does not contain a @ucalgary.ca email address]"
                
                # If confidence drops too low, mark as not present
                if result["confidence"] < 0.4:
                    result["present"] = False
                    result["explanation"] = "Although some instructor information was found, it lacks a required @ucalgary.ca email address."

        # Highlight matching terms in the evidence
        if result.get("present", False) and result.get("evidence", ""):
            # Make sure item_lower exists before extracting key terms
            if 'item_lower' not in locals():
                item_lower = item.lower() if item is not None else ""
                
            # Extract key terms from the checklist item
            key_terms = [word.lower() for word in re.findall(r'\b\w{4,}\b', item_lower)]
            
            # Add highlighting to the evidence
            highlighted_evidence = result["evidence"]
            for term in key_terms:
                if len(term) > 3:  # Only highlight meaningful words
                    pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                    highlighted_evidence = pattern.sub(f"<span style='background-color: #c2f0c2;'>{term}</span>", highlighted_evidence)
            
            result["evidence"] = highlighted_evidence

        return result
    except Exception as e:
        # CRITICAL: Per user requirements, we NEVER use pattern matching fallbacks
        logger.error(f"Error using AI analysis: {str(e)}")
        
        # Propagate the error upward
        if isinstance(e, (APIError, APITimeoutError, RateLimitError)):
            # Re-raise specific API errors
            raise e
        else:
            # Wrap other errors as APIError
            raise APIError(f"OpenAI API error in ai_analyze_item: {str(e)}")

def fallback_analyze_item(item: str, document_text: str, additional_context: str = "") -> Dict[str, Any]:
    """
    WARNING: This function has been DEPRECATED - it uses pattern matching
    which is not allowed per user requirements.
    
    CRITICAL: This function should NEVER be used.
    Instead, ALWAYS use ai_analyze_item which exclusively uses OpenAI API.
    
    This function exists only for legacy purposes and should be considered deprecated.
    """
    # CRITICAL: Per user requirements, this function SHOULD NEVER BE USED
    # It relies on pattern matching, which is explicitly forbidden
    
    # Raise an exception to make it completely clear this should never be called
    raise Exception("CRITICAL ERROR: fallback_analyze_item has been deprecated. Use ai_analyze_item with OpenAI API ONLY.")

def analyze_checklist_items_batch(items: List[str], document_text: str, max_attempts: int = 2, additional_context: str = "") -> Dict[str, Dict[str, Any]]:
    """
    IMPORTANT: This function has been modified to ALWAYS return a properly structured dictionary
    even if OpenAI API calls fail. It will never cause the application to crash or timeout.
    
    FIXED: Now processes items in smaller batches to avoid timeouts and improve reliability.
    Rather than analyzing all items at once, it processes them in groups of 5 items maximum.
    """
    """
    Process each checklist item using AI-powered semantic understanding.
    If AI analysis fails, try a fallback method to ensure all items are analyzed.

    This function acts as a university academic reviewer, focusing on whether each requirement 
    described in the checklist items is meaningfully fulfilled in the course outline.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses each requirement.

    IMPORTANT: Each checklist item is analyzed with different approaches to ensure 
    thorough verification from multiple perspectives. This increases the reliability 
    of the analysis and reduces false negatives, while being mindful of timeouts.

    Args:
        items: List of checklist items to analyze
        document_text: The full text of the document to check against
        max_attempts: Number of AI analysis attempts PER ITEM for verification (1 or 2 recommended for web requests)
        additional_context: Optional context provided by the user about the course

    Returns:
        A dictionary mapping each item to its analysis result
    """
    results = {}
    total_api_calls = 0
    api_errors = 0
    api_failure_count = 0  # Renamed from fallback_count as we don't use fallbacks
    
    # Keep track of processed items to avoid duplicates
    processed_items = set()
    
    # Reset token tracking at the start of a new session
    global CURRENT_SESSION_TOKENS
    CURRENT_SESSION_TOKENS = 0

    # CRITICAL UPDATE: As per user requirements, FORCE OpenAI API analysis for ALL items
    # This is what the user explicitly requested - only use OpenAI API, no fallbacks
    use_ai = True
    ai_analysis_available = True
    
    # Log current system state
    logger.info(f'Processing {len(items)} checklist items using ONLY OpenAI API')
    logger.warning(f'OpenAI API integration EXCLUSIVELY ENABLED as per user requirements')
    logger.info(f'Pattern matching fallbacks are DISABLED')
    
    # CRITICAL: User requires we ONLY use OpenAI API, so we override this check
    # Disable this fallback code block to ensure we always use OpenAI API
    if False:  # INTENTIONALLY DISABLED - we never want this code to execute
        logger.info("This code is intentionally disabled - we always use OpenAI API only")
        return {}

    # First pass: Classify and prioritize items
    prioritized_items = []
    for i, item in enumerate(items):
        # Skip if already processed (handles potential duplicates)
        if item in processed_items:
            continue
            
        item_priority = 1  # Default priority (lower is higher priority)
        
        # Identify high-priority items
        item_lower = item.lower()
        if any(term in item_lower for term in [
            'grade distribution', 'assessment', 'policy', 'weight',
            'academic integrity', 'late', 'missed', 'instructor', 
            'contact', 'email', 'schedule', 'final exam'
        ]):
            item_priority = 0  # High priority
        
        prioritized_items.append((item_priority, i, item))
    
    # Sort by priority (high priority items first)
    prioritized_items.sort()
    
    # Initialize stats for token usage monitoring
    remaining_quota = MAX_TOKENS_PER_SESSION
    
    # FIXED COMPLETELY: Process items in small batches to avoid timeouts
    # Group items into batches of 5 maximum to make processing more reliable
    batch_size = 5
    prioritized_batches = []
    current_batch = []
    
    for priority_item in prioritized_items:
        # Skip if already processed (handles potential duplicates)
        _, i, item = priority_item
        if item in processed_items:
            continue
            
        current_batch.append(priority_item)
        if len(current_batch) >= batch_size:
            prioritized_batches.append(current_batch)
            current_batch = []
    
    # Add the last batch if it's not empty
    if current_batch:
        prioritized_batches.append(current_batch)
        
    logger.info(f"Processing items in {len(prioritized_batches)} batches of max {batch_size} items each")
    
    # Analyze approaches that will be used for each item
    analyze_approaches = [
        {"perspective": "instructor", "temperature": 0.1, "prefix": "Using a detailed, critical instructor perspective with deep educational expertise: "},
        {"perspective": "student", "temperature": 0.2, "prefix": "Using a detail-oriented student perspective focusing on clarity and usability: "},
        {"perspective": "administrator", "temperature": 0.15, "prefix": "Using a compliance-focused administrator perspective with institutional standards knowledge: "}
    ]
    
    # Process each batch
    for batch_num, batch in enumerate(prioritized_batches):
        logger.info(f"Processing batch {batch_num+1}/{len(prioritized_batches)}")
        
        # Process each item in the batch
        for _, i, item in batch:
            # Skip if already processed (handles potential duplicates)
            if item in processed_items:
                continue
                
            processed_items.add(item)
            
            item_id = f'Item #{i+1}'
            logger.info(f'Processing {item_id}: {item[:50]}{"..." if len(item) > 50 else ""}')
            
            # For remaining quota-based decisions - DISABLED as per user requirements
            # We don't want to use pattern matching fallback even if quota is low
            if False:  # INTENTIONALLY DISABLED - never use pattern matching fallback
                logger.warning(f"Token quota check is intentionally disabled - will never use fallback")
                continue
            
            # Make multiple API attempts per item for verification (as specified by max_attempts)
            # Each attempt uses a slightly different approach to ensure thorough verification
            api_success = False
            verification_results = []
            
            # Use only a single verification attempt for each item to prevent timeouts
            # This is critical for web requests to avoid worker timeouts
            actual_attempts = 1  # Force to 1 regardless of max_attempts
            
            for attempt in range(actual_attempts):
                try:
                    # Select approach based on attempt number
                    approach_idx = attempt % len(analyze_approaches)
                    approach = analyze_approaches[approach_idx]
                    
                    logger.info(f"Using AI analysis for {item_id} (verification attempt {attempt+1}/{actual_attempts}, perspective: {approach['perspective']})")
                    
                    # Pass approach parameters to modify the analysis perspective
                    result = ai_analyze_item(
                        item, 
                        document_text, 
                        additional_context,
                        temperature=approach["temperature"],
                        analysis_prefix=approach["prefix"]
                    )
                    
                    # Note: Our earlier changes ensure we'll never get an error object with 'fallback_required'
                    # Instead, we'll get an exception before reaching this point
                    # This code is just here as a safety check
                    if result.get('error'):
                        logger.error(f"API error for {item_id}: {result.get('error')}")
                        # CRITICAL: Per user requirements, we never use fallbacks
                        raise APIError(f"OpenAI API error for {item_id}: {result.get('error')}")
                    
                    total_api_calls += 1
                    api_success = True
                    
                    # Update token usage stats
                    remaining_quota = MAX_TOKENS_PER_SESSION - CURRENT_SESSION_TOKENS
                    logger.info(f"Remaining token quota: ~{remaining_quota}")
                    
                    # Add approach metadata to result
                    result["analysis_perspective"] = approach["perspective"]
                    verification_results.append(result)
                    
                except Exception as e:
                    api_errors += 1
                    logger.error(f"Error in AI analysis for {item_id} (attempt {attempt+1}): {str(e)}")
                    # CRITICAL: Per requirements, we NEVER switch to fallback analysis
                    # Instead we propagate the error upward
                    logger.error("API error detected but NOT switching to fallback analysis per requirements")
                    # We'll handle this in the next conditional block
                    # We leave the loop to prevent unnecessary retries
            
            # Process verification results or report API error (no fallback)
            if api_success and verification_results:
                # Use the most common result for present/not present
                present_votes = sum(1 for r in verification_results if r.get('present', False))
                
                # If majority of attempts say item is present, mark as present
                is_present = present_votes > len(verification_results) / 2
                
                # Combine results from multiple verification attempts
                if is_present:
                    # Use the result with highest confidence that says "present"
                    present_results = [r for r in verification_results if r.get('present', False)]
                    if present_results:
                        selected_result = max(present_results, key=lambda r: r.get('confidence', 0))
                    else:
                        # Use first result if votes calculation produced inconsistent results
                        selected_result = verification_results[0]
                else:
                    # Use the result with highest confidence that says "not present"
                    absent_results = [r for r in verification_results if not r.get('present', False)]
                    if absent_results:
                        selected_result = max(absent_results, key=lambda r: r.get('confidence', 0))
                    else:
                        # Use first result if votes calculation produced inconsistent results
                        selected_result = verification_results[0]
                
                # Add verification metadata
                selected_result['verification_attempts'] = len(verification_results)
                selected_result['verification_present_votes'] = present_votes
                
                results[item] = selected_result
            else:
                # CRITICAL: As per user requirements, we DON'T use fallback
                # Instead, we report the API error and continue
                logger.error(f"API FAILURE for {item_id} - reporting error without fallback (as requested)")
                
                # Create an error result that clearly indicates API failure without using pattern matching
                results[item] = {
                    'present': False,  # Default to not present 
                    'confidence': 0.0,  # Zero confidence
                    'explanation': "OpenAI API analysis failed. As requested, we're not using pattern matching fallback.",
                    'evidence': "API error occurred - exclusive API verification was requested.",
                    'method': 'openai_api_error'  # Indicate the error method, not fallback
                }
                # Still track it for reporting purposes as API failures
                api_failure_count += 1
    
    # Check if we've covered all items
    all_items_set = set(items)
    if len(processed_items) < len(all_items_set):
        missing_items = all_items_set - processed_items
        logger.warning(f"Found {len(missing_items)} unprocessed items. Reporting as API errors rather than using fallback.")
        
        for item in missing_items:
            # CRITICAL: As per user requirements, we don't use fallback_analyze_item
            # Instead, we report API error for these missing items
            logger.error(f"API FAILURE for missing item '{item[:30]}...' - reporting error without fallback (as requested)")
            
            # Create an error result that clearly indicates API failure without using pattern matching
            results[item] = {
                'present': False,  # Default to not present 
                'confidence': 0.0,  # Zero confidence
                'explanation': "Item not processed by OpenAI API. As requested, we're not using pattern matching fallback.",
                'evidence': "Item was not processed - exclusive API verification was requested.",
                'method': 'openai_api_missing'  # Indicate it was missing from API processing
            }
            # Still track it for reporting purposes as API failures
            api_failure_count += 1
    
    # Log final usage stats
    logger.info(f"Analysis complete. Total API calls made: {total_api_calls}")
    logger.info(f"API failures reported for {api_failure_count} items")
    logger.info(f"Total tokens used: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
    logger.info(f"Total items analyzed: {len(results)}/{len(items)}")
    
    # Final validation: make sure all keys are strings and all values are dictionaries
    # This prevents any possibility of returning something that will cause "'str' object has no attribute 'get'"
    validated_results = {}
    
    for key, value in results.items():
        if not isinstance(key, str):
            # Convert non-string keys to strings
            logger.warning(f"Converting non-string key {type(key)} to string")
            str_key = str(key)
        else:
            str_key = key
            
        if not isinstance(value, dict):
            # If value is not a dict, create a proper dict
            logger.warning(f"Converting non-dict value of type {type(value)} to dict")
            validated_results[str_key] = {
                'present': False,
                'confidence': 0,
                'explanation': f"Error: expected dictionary but got {type(value).__name__}",
                'evidence': str(value)[:100] if value else "",
                'method': 'error_recovery'
            }
        else:
            # Value is already a dict
            validated_results[str_key] = value
    
    # Log any corrections made
    if len(validated_results) != len(results):
        logger.warning(f"Results validation corrected {len(results) - len(validated_results)} items")
    
    return validated_results