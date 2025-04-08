import logging
import os
import time
import json
import re
import random
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta

# Try to import tiktoken and openai, but provide fallbacks if not available
try:
    import tiktoken
    tiktoken_available = True
except ImportError:
    tiktoken_available = False

try:
    from openai import OpenAI, RateLimitError, APIError, APITimeoutError
    openai_available = True
except ImportError:
    openai_available = False
    # Define empty classes for type compatibility
    class RateLimitError(Exception): pass
    class APIError(Exception): pass
    class APITimeoutError(Exception): pass

# Configure OpenAI with API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# Create client only if API key is available and OpenAI library is available
client = None
if openai_available:
    if OPENAI_API_KEY and OPENAI_API_KEY.strip():
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            logging.info("OpenAI API key is configured. Advanced AI analysis is available.")
        except Exception as e:
            logging.error(f"Error initializing OpenAI client: {str(e)}")
            logging.info("Proceeding with rule-based analysis only.")
    else:
        logging.info("No OpenAI API key found. Using rule-based analysis only.")
else:
    logging.info("OpenAI library is not available. Using rule-based analysis only.")

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

def api_call_with_backoff(prompt: str) -> Dict:
    """
    Make an API call with exponential backoff for rate limiting.
    
    Args:
        prompt: The prompt to send to the API
        
    Returns:
        API response or error information
    """
    global CURRENT_SESSION_TOKENS
    
    # If OpenAI client is not available, return fallback immediately
    if client is None:
        logger.warning("OpenAI client not available. Using rule-based analysis.")
        return {"error": "OpenAI client not available", "fallback_required": True}
    
    # Check cache first
    cache_key = get_cache_key(prompt)
    if cache_key in CACHE:
        logger.info("Using cached response")
        return CACHE[cache_key]
    
    # Count input tokens
    input_tokens = count_tokens(prompt)
    
    # Check if this would exceed session limit
    if CURRENT_SESSION_TOKENS + input_tokens > MAX_TOKENS_PER_SESSION:
        logger.warning(f"Session token limit approaching: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
        return {"error": "Session token limit reached", "fallback_required": True}
    
    # Update history to track API call frequency
    current_time = datetime.now()
    API_CALL_HISTORY.append(current_time)
    
    # Clean up old history (older than 1 minute)
    one_minute_ago = current_time - timedelta(minutes=1)
    API_CALL_HISTORY[:] = [t for t in API_CALL_HISTORY if t > one_minute_ago]
    
    # If we've made more than 5 calls in the last minute, add a small delay but keep it minimal
    if len(API_CALL_HISTORY) > 5:
        delay = 0.5  # Fixed shorter delay to prevent timeouts
        logger.info(f"Rate limiting - adding {delay:.2f}s delay")
        time.sleep(delay)
    
    # Try the API call with short timeout to prevent worker hanging
    for attempt in range(MAX_RETRIES):
        try:
            # Use global client with timeout
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Lower temperature for more consistent analysis
                max_tokens=400,   # Limit token output to speed up response
            )
            
            # Estimate response tokens
            response_text = response.choices[0].message.content
            response_tokens = count_tokens(response_text)
            
            # Update token count
            CURRENT_SESSION_TOKENS += input_tokens + response_tokens
            logger.info(f"API call successful: {input_tokens}+{response_tokens}={input_tokens+response_tokens} tokens used. " +
                      f"Session total: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
            
            # Parse and cache the response
            try:
                result = json.loads(response_text)
                CACHE[cache_key] = result
                return result
            except json.JSONDecodeError:
                logger.warning("API returned non-JSON response")
                return {"error": "Invalid API response format", "fallback_required": True}
                
        except RateLimitError as e:
            logger.warning(f"Rate limit error on attempt {attempt+1}/{MAX_RETRIES}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY_BASE ** attempt * (1 + random.random())
                logger.info(f"Waiting {sleep_time:.2f}s before retry")
                time.sleep(sleep_time)
            else:
                logger.error("Rate limit error after all retries")
                return {"error": "Rate limit exceeded", "fallback_required": True}
                
        except (APIError, APITimeoutError) as e:
            logger.warning(f"API error on attempt {attempt+1}/{MAX_RETRIES}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                sleep_time = RETRY_DELAY_BASE ** attempt * (1 + random.random())
                logger.info(f"Waiting {sleep_time:.2f}s before retry")
                time.sleep(sleep_time)
            else:
                logger.error("API error after all retries")
                return {"error": "API error", "fallback_required": True}
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if "insufficient_quota" in str(e):
                return {"error": "Insufficient quota", "fallback_required": True}
            return {"error": f"Unknown error: {str(e)}", "fallback_required": True}
    
    # If we've reached here, all retries failed
    return {"error": "All API call attempts failed", "fallback_required": True}

def analyze_checklist_item(item: str, document_text: str) -> Dict[str, Any]:
    """
    Analyze if a checklist item is present in the document using semantic understanding.

    This function acts as a university academic reviewer, focusing on whether the 
    requirement described in the checklist item is meaningfully fulfilled in the 
    course outline.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses the requirement.

    Returns a dictionary with match result and confidence score.
    """
    # Use document_processor's specialized functions to get a more accurate result
    from document_processor import check_item_in_document, find_matching_excerpt

    # First check using the advanced semantic matching in check_item_in_document
    is_present = check_item_in_document(item, document_text)

    # If the item is present, try to find the specific section that matches it
    evidence = ""
    if is_present:
        found, excerpt = find_matching_excerpt(item, document_text)
        if found and excerpt:
            evidence = excerpt

    # Generate a meaningful explanation
    item_lower = item.lower()
    if is_present:
        # Create context-aware explanations
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline contains clearly listed or numbered learning objectives.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'The course outline includes a grade distribution or assessment weighting scheme.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Information about the final exam is provided in the course outline.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'The course outline specifies a policy for late assignments or submissions.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'The course outline addresses procedures for missed assessments or exams.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'The course outline provides instructor contact information and communication procedures.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'The course outline lists required or recommended textbooks or reading materials.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'The course outline includes a statement on academic integrity or misconduct.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'The course outline provides information about accommodations for students with disabilities.'
        else:
            explanation = 'This requirement is addressed in the course outline with relevant content.'
    else:
        if 'objective' in item_lower and ('list' in item_lower or 'number' in item_lower):
            explanation = 'The course outline does not appear to have clearly listed or numbered learning objectives.'
        elif 'grade' in item_lower or 'grading' in item_lower or 'weighting' in item_lower:
            explanation = 'A grade distribution or assessment weighting scheme was not found in the course outline.'
        elif 'exam' in item_lower and 'final' in item_lower:
            explanation = 'Specific information about the final exam appears to be missing from the course outline.'
        elif 'policy' in item_lower and 'late' in item_lower:
            explanation = 'A clear policy for late assignments or submissions was not found in the course outline.'
        elif 'miss' in item_lower and ('exam' in item_lower or 'assignment' in item_lower):
            explanation = 'Procedures for missed assessments or exams were not clearly identified in the course outline.'
        elif 'instructor' in item_lower and 'contact' in item_lower:
            explanation = 'Instructor contact information or communication procedures appear to be missing from the course outline.'
        elif 'text' in item_lower and 'book' in item_lower:
            explanation = 'Required or recommended textbooks or reading materials were not clearly identified in the course outline.'
        elif 'academic' in item_lower and ('integrity' in item_lower or 'misconduct' in item_lower):
            explanation = 'A statement on academic integrity or misconduct was not found in the course outline.'
        elif 'accommodation' in item_lower or 'accessibility' in item_lower:
            explanation = 'Information about accommodations for students with disabilities appears to be missing from the course outline.'
        else:
            explanation = 'This requirement does not appear to be addressed in the course outline.'

    return {
        'present': is_present,
        'confidence': 0.85 if is_present else 0.15,
        'explanation': explanation,
        'evidence': evidence if is_present else "",
        'method': 'academic_review'
    }

def ai_analyze_item(item: str, document_text: str, additional_context: str = "") -> Dict[str, Any]:
    """
    Use OpenAI to analyze if a checklist item is present in the document.

    This function provides advanced semantic understanding of whether
    the requirement in the checklist item is fulfilled in the course outline.
    
    Special handling is provided for grade table items which need more precise analysis.
    
    Args:
        item: The checklist item to analyze
        document_text: The full text of the document to check against
        additional_context: Optional context provided by the user about the course
        
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
        
        # Check for grade/assessment related items
        is_grade_item = any(term in item_lower for term in [
            'grade distribution', 'weight', 'assessment', 'table',
            'due date', 'participation', 'group project', 'final exam',
            'take home', 'class schedule', 'missed assessment', 'late policy',
            'assignment', 'evaluation', 'worth', 'percentage', 'grading'
        ])
        
        # Check for policy-related items
        is_policy_item = any(term in item_lower for term in [
            'policy', 'policies', 'missed', 'late', 'academic integrity',
            'misconduct', 'plagiarism', 'attendance', 'accommodations',
            'diversity', 'inclusion', 'accessibility', 'guidelines', 'rules'
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
            
            Provide a JSON response with the following fields:
            - "present": boolean indicating if the item is EXPLICITLY addressed in the outline with SUFFICIENT DETAIL
            - "confidence": number between 0 and 1 indicating confidence in the decision (higher = more confident)
            - "explanation": detailed explanation of why the item is or is not present
            - "evidence": if present, provide the EXACT TEXT from the outline that addresses this item
            - "method": should be "ai_policy_analysis"
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
            
            Provide a JSON response with the following fields:
            - "present": boolean indicating if the item is EXPLICITLY addressed in the outline with SUFFICIENT DETAIL
            - "confidence": number between 0 and 1 indicating confidence in the decision (higher = more confident)
            - "explanation": detailed explanation of why the item is or is not present
            - "evidence": if present, provide the EXACT TEXT from the outline that addresses this item
            - "method": should be "ai_instructor_analysis"
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
            
            Provide a JSON response with the following fields:
            - "present": boolean indicating if the item is EXPLICITLY addressed in the outline with SUFFICIENT DETAIL
            - "confidence": number between 0 and 1 indicating confidence in the decision (higher = more confident)
            - "explanation": detailed explanation of why the item is or is not present
            - "evidence": if present, provide the EXACT TEXT from the outline that addresses this item
            - "method": should be "ai_general_analysis"
            """

        # Adjust temperature and tokens based on item type
        # Lower temperature for stricter, more consistent responses
        temperature = 0.1
        
        # Use more tokens for complex items
        max_tokens = 1000 if is_grade_item or is_policy_item else 800
        
        # Make the API call using our improved rate-limited function
        prompt_with_sys_msg = f"You are an expert academic document reviewer for the University of Calgary with extremely high standards for document compliance.\n\n{prompt}"
        api_response = api_call_with_backoff(prompt_with_sys_msg)
        
        # Check if we need to fall back to traditional analysis
        if "fallback_required" in api_response and api_response["fallback_required"]:
            logger.warning(f"API call failed: {api_response.get('error', 'Unknown error')} - using fallback analysis")
            return fallback_analyze_item(item, document_text, additional_context)
        
        # Process the API response
        result = api_response  # The api_call_with_backoff already handles JSON parsing

        # Ensure all required fields are present
        if not all(key in result for key in ["present", "confidence", "explanation", "evidence", "method"]):
            raise ValueError("API response missing required fields")
            
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
        logger.error(f"Error using AI analysis: {str(e)}")
        if "insufficient_quota" in str(e):
            logger.warning("API quota exceeded - using enhanced traditional analysis")
        
        # Fall back to enhanced traditional analysis with multiple checks
        from document_processor import check_item_in_document, find_matching_excerpt, check_special_entity_patterns, identify_grade_distribution_table
        
        # Get the item_lower value for the fallback process
        item_lower = item.lower()
        
        # Multiple validation approaches
        is_present_basic = check_item_in_document(item, document_text, additional_context)
        is_present_special = check_special_entity_patterns(item, document_text, additional_context)
        
        # Special handling for grade table items
        is_grade_item = ('grade' in item_lower and 'distribution' in item_lower) or 'weight' in item_lower
        if is_grade_item:
            has_grade_table, _ = identify_grade_distribution_table(document_text)
            if has_grade_table:
                is_present_special = True
        
        # Find matching excerpt
        found_excerpt, excerpt = find_matching_excerpt(item, document_text)
        
        # Require at least 2 out of 3 checks to pass for higher confidence
        checks_passed = sum([is_present_basic, is_present_special, found_excerpt])
        is_present = checks_passed >= 2
        confidence = min(0.85, 0.3 + (checks_passed * 0.2))
        
        return {
            'present': is_present,
            'confidence': confidence if is_present else 0.2,
            'explanation': f"Fallback analysis after API error: {'Item is present in document' if is_present else 'Item not found in document'} ({checks_passed}/3 checks passed)",
            'evidence': excerpt if found_excerpt else "",
            'method': 'fallback_academic_review'
        }

def fallback_analyze_item(item: str, document_text: str, additional_context: str = "") -> Dict[str, Any]:
    """
    Fallback analysis when API calls fail or quota is exceeded.
    Uses multiple traditional analysis techniques for better results.
    """
    import re
    # Import document processing functions here to avoid circular imports
    from document_processor import check_item_in_document, find_matching_excerpt, check_special_entity_patterns, identify_grade_distribution_table
    
    # Get the item_lower value for the fallback process
    item_lower = item.lower()
    
    # Multiple validation approaches
    is_present_basic = check_item_in_document(item, document_text, additional_context)
    is_present_special = check_special_entity_patterns(item, document_text, additional_context)
    
    # Special handling for grade table items
    is_grade_item = ('grade' in item_lower and 'distribution' in item_lower) or 'weight' in item_lower
    if is_grade_item:
        has_grade_table, table_text = identify_grade_distribution_table(document_text)
        if has_grade_table:
            is_present_special = True
    
    # Find matching excerpt
    found_excerpt, excerpt = find_matching_excerpt(item, document_text)
    
    # Require at least 2 out of 3 checks to pass for higher confidence
    checks_passed = sum([is_present_basic, is_present_special, found_excerpt])
    is_present = checks_passed >= 2
    confidence = min(0.85, 0.3 + (checks_passed * 0.2))
    
    # Generate an appropriate explanation
    if is_present:
        if is_grade_item:
            explanation = f"Fallback analysis: Grade distribution or assessment information found. ({checks_passed}/3 checks passed)"
        elif 'policy' in item_lower:
            explanation = f"Fallback analysis: Relevant policy information identified. ({checks_passed}/3 checks passed)"
        elif 'instructor' in item_lower or 'contact' in item_lower:
            explanation = f"Fallback analysis: Instructor contact information found. ({checks_passed}/3 checks passed)"
        else:
            explanation = f"Fallback analysis: Item is present in document. ({checks_passed}/3 checks passed)"
    else:
        if is_grade_item:
            explanation = f"Fallback analysis: Grade distribution or assessment information not clearly found. ({checks_passed}/3 checks passed)"
        elif 'policy' in item_lower:
            explanation = f"Fallback analysis: Required policy information not clearly identified. ({checks_passed}/3 checks passed)"
        elif 'instructor' in item_lower or 'contact' in item_lower:
            explanation = f"Fallback analysis: Complete instructor contact information not found. ({checks_passed}/3 checks passed)"
        else:
            explanation = f"Fallback analysis: Item not found in document. ({checks_passed}/3 checks passed)"
    
    # Add highlighting to the evidence
    highlighted_evidence = ""
    if found_excerpt and excerpt:
        highlighted_evidence = excerpt
        # Extract key terms from the checklist item
        key_terms = [word.lower() for word in re.findall(r'\b\w{4,}\b', item_lower)]
        # Add highlighting
        for term in key_terms:
            if len(term) > 3:  # Only highlight meaningful words
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                highlighted_evidence = pattern.sub(f"<span style='background-color: #c2f0c2;'>{term}</span>", highlighted_evidence)
    
    return {
        'present': is_present,
        'confidence': confidence if is_present else 0.2,
        'explanation': explanation,
        'evidence': highlighted_evidence,
        'method': 'fallback_analysis'
    }

def analyze_checklist_items_batch(items: List[str], document_text: str, max_attempts: int = 3, additional_context: str = "") -> Dict[str, Dict[str, Any]]:
    """
    Process each checklist item using AI-powered semantic understanding.
    If AI analysis fails, try a fallback method to ensure all items are analyzed.

    This function acts as a university academic reviewer, focusing on whether each requirement 
    described in the checklist items is meaningfully fulfilled in the course outline.

    The analysis considers that the same concept may be expressed with different phrasing, 
    formatting, or section titles, and uses deep understanding of intent and meaning to
    determine whether the course outline addresses each requirement.

    Args:
        items: List of checklist items to analyze
        document_text: The full text of the document to check against
        max_attempts: Number of AI analysis attempts PER ITEM for verification
        additional_context: Optional context provided by the user about the course

    Returns:
        A dictionary mapping each item to its analysis result
    """
    results = {}
    total_api_calls = 0
    api_errors = 0
    fallback_count = 0
    
    # Keep track of processed items to avoid duplicates
    processed_items = set()
    
    # Reset token tracking at the start of a new session
    global CURRENT_SESSION_TOKENS
    CURRENT_SESSION_TOKENS = 0

    # Decide whether AI analysis is available based on API key
    use_ai = client is not None
    
    # Track API status for proper error handling
    ai_analysis_available = False
    
    # Log current system state
    logger.info(f'Processing {len(items)} checklist items')
    
    if use_ai:
        logger.info(f'OpenAI client is configured. Advanced AI analysis is available.')
        logger.info(f'Using {max_attempts} verification attempts per item')
        ai_analysis_available = True
        
        # Validate API connection with test call
        if max_attempts > 0:  # Only if API analysis is requested by user setting
            try:
                # Simple test call with minimal tokens
                test_prompt = "Return valid JSON with key 'status' and value 'ok'"
                test_response = api_call_with_backoff(test_prompt)
                
                if 'error' in test_response:
                    logger.warning(f"API test call failed: {test_response.get('error')}")
                    logger.warning("Will use fallback analysis methods for all items")
                    ai_analysis_available = False
                else:
                    logger.info("API connection verified successfully")
            except Exception as e:
                logger.exception(f"Error verifying API connection: {str(e)}")
                logger.warning("Will use fallback analysis methods for all items")
                ai_analysis_available = False
    else:
        logger.warning(f'OpenAI client is not available. Using fallback analysis methods.')
        ai_analysis_available = False
    
    # If API is not available, use fallback for all items
    if not ai_analysis_available or max_attempts == 0:
        logger.info("Using pattern matching fallback for all items")
        
        # Use fallback analysis for all items
        for item in items:
            if item in processed_items:
                continue
                
            processed_items.add(item)
            results[item] = fallback_analyze_item(item, document_text, additional_context)
            fallback_count += 1
            
        logger.info(f'Completed analysis of {len(processed_items)} items using fallback methods')
        return results

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
    
    # Process items in priority order
    for _, i, item in prioritized_items:
        # Skip if already processed (handles potential duplicates)
        if item in processed_items:
            continue
            
        processed_items.add(item)
        
        item_id = f'Item #{i+1}'
        logger.info(f'Processing {item_id}: {item[:50]}{"..." if len(item) > 50 else ""}')
        
        # For remaining quota-based decisions
        if remaining_quota < 1000:  # Set a minimum threshold for remaining tokens
            logger.warning(f"Token quota nearly exhausted. Using fallback analysis for {item_id}")
            results[item] = fallback_analyze_item(item, document_text, additional_context)
            fallback_count += 1
            continue
        
        # Make multiple API attempts per item for verification (as specified by max_attempts)
        api_success = False
        verification_results = []
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Using AI analysis for {item_id} (verification attempt {attempt+1}/{max_attempts})")
                result = ai_analyze_item(item, document_text, additional_context)
                
                # Check if API returned an error that requires fallback
                if result.get('error') and result.get('fallback_required', False):
                    logger.warning(f"API error for {item_id}: {result.get('error')}")
                    raise Exception(result.get('error'))
                
                total_api_calls += 1
                api_success = True
                
                # Update token usage stats
                remaining_quota = MAX_TOKENS_PER_SESSION - CURRENT_SESSION_TOKENS
                logger.info(f"Remaining token quota: ~{remaining_quota}")
                
                verification_results.append(result)
                
                # We could stop after one successful attempt, but we're making multiple attempts
                # for verification as per the requested functionality
                
            except Exception as e:
                api_errors += 1
                logger.error(f"Error in AI analysis for {item_id} (attempt {attempt+1}): {str(e)}")
                if "insufficient_quota" in str(e) or remaining_quota < 1000:
                    logger.warning("API quota exceeded - switching to fallback analysis")
                    remaining_quota = 0
                    break  # Stop trying if quota is exceeded
        
        # Process verification results or use fallback
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
                    # Fallback if votes calculation and filtering produced inconsistent results
                    selected_result = verification_results[0]
            else:
                # Use the result with highest confidence that says "not present"
                absent_results = [r for r in verification_results if not r.get('present', False)]
                if absent_results:
                    selected_result = max(absent_results, key=lambda r: r.get('confidence', 0))
                else:
                    # Fallback if votes calculation and filtering produced inconsistent results
                    selected_result = verification_results[0]
            
            # Add verification metadata
            selected_result['verification_attempts'] = len(verification_results)
            selected_result['verification_present_votes'] = present_votes
            
            results[item] = selected_result
        else:
            # Use fallback analysis method instead of just reporting an error
            logger.warning(f"Using fallback analysis for {item_id} after API failures")
            results[item] = fallback_analyze_item(item, document_text, additional_context)
            fallback_count += 1
    
    # Check if we've covered all items
    all_items_set = set(items)
    if len(processed_items) < len(all_items_set):
        missing_items = all_items_set - processed_items
        logger.warning(f"Found {len(missing_items)} unprocessed items. Processing with fallback method.")
        
        for item in missing_items:
            results[item] = fallback_analyze_item(item, document_text, additional_context)
            fallback_count += 1
    
    # Log final usage stats
    logger.info(f"Analysis complete. Total API calls made: {total_api_calls}")
    logger.info(f"Fallback method used for {fallback_count} items")
    logger.info(f"Total tokens used: {CURRENT_SESSION_TOKENS}/{MAX_TOKENS_PER_SESSION}")
    logger.info(f"Total items analyzed: {len(results)}/{len(items)}")
    
    return results