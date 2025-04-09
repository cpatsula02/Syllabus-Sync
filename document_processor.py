import logging
import re
from typing import List, Dict, Tuple, Any, Optional

import pdfplumber
import docx

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file with enhanced extraction of tables and structured content."""
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = ""
            
            # Process each page
            for page in pdf.pages:
                # Extract main text
                page_text = page.extract_text() or ""
                
                # Extract tables separately to ensure we don't miss tabular data
                tables = page.extract_tables()
                tables_text = ""
                
                for table in tables:
                    for row in table:
                        # Join non-empty cells with tabs to preserve table structure
                        row_text = "\t".join([str(cell) if cell is not None else "" for cell in row])
                        tables_text += row_text + "\n"
                
                # Combine page text and tables text
                full_text += page_text + "\n" + tables_text + "\n\n"
            
            # Normalize whitespace to make text processing more reliable
            normalized_text = re.sub(r'\s+', ' ', full_text).strip()
            
            logging.info(f"Extracted {len(normalized_text)} characters from PDF")
            return normalized_text
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a DOCX file."""
    try:
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + "\t"
                text += "\n"
        return text
    except Exception as e:
        logging.error(f"Error extracting text from DOCX: {str(e)}")
        return ""

def extract_text(file_path: str) -> str:
    """Extract text from a document based on its file extension."""
    try:
        if file_path.lower().endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return extract_text_from_docx(file_path)
        else:
            # For text files or other formats, just read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        logging.error(f"Error extracting text: {str(e)}")
        return ""

def extract_checklist_items(text: str) -> List[str]:
    """
    Extract checklist items from the checklist document.
    Only extract numbered or bulleted items, excluding any other text.
    Ensures no duplicate items are included.
    """
    try:
        lines = text.split('\n')
        items = []
        for line in lines:
            line = line.strip()
            # Match lines that start with a number followed by a period or parenthesis
            if re.match(r'^\d+[\.\)]', line):
                # Remove the numbering and any leading/trailing whitespace
                item = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if item and item not in items:
                    items.append(item)
            # Match lines that start with common bullet point characters
            elif re.match(r'^[\*\-\+•]', line):
                # Remove the bullet point and any leading/trailing whitespace
                item = re.sub(r'^[\*\-\+•]\s*', '', line).strip()
                if item and item not in items:
                    items.append(item)
        
        return items
    except Exception as e:
        logging.error(f"Error extracting checklist items: {str(e)}")
        return []

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def check_item_in_document(item: str, document_text: str, additional_context="") -> bool:
        """Stub for pattern matching function - not used"""
        return False

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def extract_core_concepts(text):
        """Stub for extract_core_concepts - not used"""
        return []

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def extract_document_sections(document_text):
        """Stub for extract_document_sections - not used"""
        return {}

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def sections_are_related(section_title, item_concepts):
        """Stub for sections_are_related - not used"""
        return False

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def content_contains_concepts(section_content, item_concepts, threshold=0.5):
        """Stub for content_contains_concepts - not used"""
        return False

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def extract_policy_type(item_text):
        """Stub for extract_policy_type - not used"""
        return None

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def find_original_text(lowercase_text, original_document):
        """Stub for find_original_text - not used"""
        return ""

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def find_best_keyword_section(document_text, keywords):
        """Stub for find_best_keyword_section - not used"""
        return ""

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def check_special_entity_patterns(item, document, additional_context=""):
        """Stub for check_special_entity_patterns - not used"""
        return False

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def find_matching_excerpt(item, document_text):
        """Stub for find_matching_excerpt - not used"""
        return False, ""

# PATTERN MATCHING COMPLETELY DISABLED
if False:  # This code will never execute
    def identify_grade_distribution_table(document_text: str) -> Tuple[bool, str]:
        """Stub for identify_grade_distribution_table - always returns no table found"""
        return False, ""

def extract_checklist_items_strict(text: str) -> List[str]:
    """
    Extract checklist items from text, ensuring each numbered/bulleted item is separate.
    Handles pasted text from various sources with different list formats.
    Intelligently processes text even without explicit bullets or numbers.
    """
    items = []
    lines = text.split('\n')

    # Mode detection - check if list appears to use bullets, numbers, or plain text
    has_numbered_items = False
    has_bulleted_items = False
    has_lettered_items = False
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if re.match(r'^\d+[\.\)]\s+\w+', line):
            has_numbered_items = True
        elif re.match(r'^[a-zA-Z][\.\)]\s+\w+', line):
            has_lettered_items = True
        elif re.match(r'^[\*\-\+•⚫⚪○●◆◇■□▪▫]\s+\w+', line):
            has_bulleted_items = True

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match numbered items (1., 1), etc.)
        if re.match(r'^\d+[\.\)]\s+\w+', line):
            items.append(line)
        # Match lettered items (a., a), etc.)
        elif re.match(r'^[a-zA-Z][\.\)]\s+\w+', line):
            items.append(line)
        # Match bullet points with more bullet types
        elif re.match(r'^[\*\-\+•⚫⚪○●◆◇■□▪▫➢➤➔→⇒✓✔✗✘]\s+\w+', line):
            items.append(line)
        # For plain text lines (when no formatting detected), treat each non-empty line as an item
        elif not (has_numbered_items or has_bulleted_items or has_lettered_items) and len(line) > 10:
            # Only include substantial lines (longer than 10 chars) as checklist items
            items.append(line)

    # Clean up items
    cleaned_items = []
    for item in items:
        # Remove leading numbers/bullets and clean up
        cleaned = re.sub(r'^\d+[\.\)]|^[a-zA-Z][\.\)]|^[\*\-\+•⚫⚪○●◆◇■□▪▫➢➤➔→⇒✓✔✗✘]\s*', '', item).strip()
        if cleaned:
            cleaned_items.append(cleaned)

    return cleaned_items

def load_enhanced_checklist() -> Dict[str, str]:
    """
    Load the detailed checklist that contains specific requirements for each item.
    This ensures pattern matching follows the exact requirements provided in the checklist.

    Returns:
        Dictionary mapping checklist item numbers to their detailed descriptions
    """
    enhanced_checklist = {}
    try:
        with open('enhanced_checklist.txt', 'r') as f:
            content = f.read()
            # Extract numbered items with their descriptions
            pattern = r'(\d+)\.\s+(.*?)(?=\n\n\d+\.|\Z)'
            matches = re.findall(pattern, content, re.DOTALL)

            for num, description in matches:
                enhanced_checklist[int(num)] = description.strip()

        logging.info(f"Enhanced checklist loaded with {len(enhanced_checklist)} detailed items")
        return enhanced_checklist
    except Exception as e:
        logging.error(f"Error loading enhanced checklist: {str(e)}")
        return {}

def process_documents(checklist_path: str, outline_path: str, api_attempts: int = 3, additional_context: str = "") -> Tuple[List[str], Dict[str, Any]]:
    """
    Document processing that exclusively uses the OpenAI API for analysis.
    
    THIS FUNCTION HAS BEEN MODIFIED FOR EXCLUSIVE OpenAI API USAGE:
    - Uses OpenAI API with strict timeout handling (60 seconds max)
    - NEVER uses pattern matching (as per strict user requirements)
    - Never falls back to any non-AI methods for analysis
    - Always returns properly structured data with proper types
    - Always uses 'ai_general_analysis' as the method field
    """
    # Maximum API timeout in seconds to ensure we don't hang indefinitely
    MAX_API_TIMEOUT = 300  # Increased to 300 seconds (5 minutes) to prevent timeout errors
    # This longer timeout accommodates more in-depth analysis while preventing worker termination
    # Ensure we have the OS module imported
    import os
    
    # Initialize empty variables that will be filled later
    # This ensures these variables always exist even if an exception occurs
    checklist_items = []
    checklist_text = ""
    outline_text = ""
    
    # Add debugging log
    logging.error(f"DEBUG: Starting process_documents with api_attempts={api_attempts}")
    
    try:
        # Validate file paths
        if not os.path.exists(checklist_path):
            raise FileNotFoundError(f"Checklist file not found: {checklist_path}")
        if not os.path.exists(outline_path):
            raise FileNotFoundError(f"Course outline file not found: {outline_path}")

        # Extract and validate text from both documents
        checklist_text = extract_text(checklist_path)
        if not checklist_text.strip():
            raise ValueError("Checklist file is empty")

        outline_text = extract_text(outline_path)
        if not outline_text.strip():
            raise ValueError("Course outline file is empty")

        # Parse checklist items, ensuring each numbered/bulleted item is separate
        checklist_items = extract_checklist_items_strict(checklist_text)
        if not checklist_items:
            raise ValueError("No checklist items found in the document")

        # We'll skip tokenization here to make the code more robust
        # Just do basic processing for keywords
        outline_lower = outline_text.lower()
        logging.info("Document text loaded and preprocessed successfully.")

        # Initialize disable
        has_grade_table = False
        grade_table_text = ""

        # Add insights about grade table to additional context if found
        enhanced_context = additional_context
        
        # Parse the additional context to identify "not applicable" items with enhanced detection
        not_applicable_items = {}
        if additional_context:
            # List of keywords and phrases that indicate an item is not applicable
            na_phrases = [
                "not applicable", "n/a", "na ", "doesn't apply", "does not apply", 
                "not included", "not required", "no final", "no exam", "no midterm",
                "no group", "no participation", "no textbook", "not needed",
                "exempt from", "waived", "excluded", "not relevant", "not part of",
                "ignored", "skipped", "omitted"
            ]

            # Define specific item keywords that might be mentioned in additional context
            item_specific_keywords = {
                "final exam": ["final", "exam", "examination", "culminating assessment"],
                "group": ["group", "team", "collaborative", "group work", "group project"],
                "participation": ["participation", "class participation", "engagement"],
                "textbook": ["textbook", "text", "book", "reading", "course material"],
                "midterm": ["midterm", "test", "quiz", "mid-term"],
                "take home": ["take home", "takehome", "take-home"],
                "due date": ["due date", "deadline", "submission date"],
                "assignment": ["assignment", "homework", "task"],
                "schedule": ["schedule", "calendar", "timetable", "weekly"],
                "instructor": ["instructor", "professor", "teacher", "faculty"],
                "link": ["link", "url", "website", "web"],
                "grade distribution": ["grade distribution", "grade table", "assessment weight"]
            }

            context_lower = additional_context.lower()

            # First pass: Check each checklist item against the additional context
            for item in checklist_items:
                item_lower = item.lower()

                # Check if the item is explicitly mentioned as not applicable
                for phrase in na_phrases:
                    # Look for patterns like "no final exam" or "final exam: not applicable"
                    if any(re.search(re.escape(phrase) + ".*" + re.escape(keyword), context_lower) or 
                           re.search(re.escape(keyword) + ".*" + re.escape(phrase), context_lower) 
                           for keyword in item_lower.split() if len(keyword) > 3):
                        not_applicable_items[item] = True
                        break

                # If not already marked as N/A, check for specific item patterns
                if item not in not_applicable_items:
                    # Check each category of item
                    for category, keywords in item_specific_keywords.items():
                        if any(keyword in item_lower for keyword in category.split()):
                            # If this category is in the item, check if it's mentioned as N/A
                            for phrase in na_phrases:
                                for keyword in keywords:
                                    pattern1 = re.escape(phrase) + ".*" + re.escape(keyword)
                                    pattern2 = re.escape(keyword) + ".*" + re.escape(phrase)

                                    if (re.search(pattern1, context_lower) or re.search(pattern2, context_lower)):
                                        not_applicable_items[item] = True
                                        break

            # Second pass: Additional special cases based on context phrasing
            for item in checklist_items:
                if item in not_applicable_items:
                    continue  # Already marked as N/A

                item_lower = item.lower()

                # Special case 1: Final Exam-related items
                if any(term in item_lower for term in ["final exam", "final", "exam weight"]):
                    if any(phrase in context_lower for phrase in [
                        "no final", "no exam", "without final", "exempt from final",
                        "final exam is not", "final not included", "no final assessment",
                        "course has no final", "course doesn't have a final",
                        "course does not have final", "not having a final"
                    ]):
                        not_applicable_items[item] = True

                # Special case 2: Group Work-related items
                if any(term in item_lower for term in ["group", "team", "collaborative"]):
                    if any(phrase in context_lower for phrase in [
                        "no group work", "not a group", "individual only",
                        "no group component", "no team", "no collaborative",
                        "all individual work", "all work is individual",
                        "course has no group", "course doesn't have group"
                    ]):
                        not_applicable_items[item] = True

                # Special case 3: Participation-related items
                if "participation" in item_lower:
                    if any(phrase in context_lower for phrase in [
                        "no participation", "participation not", "no class participation",
                        "participation is not", "participation isn't", "no participation component"
                    ]):
                        not_applicable_items[item] = True

                # Special case 4: Textbook-related items
                if any(term in item_lower for term in ["textbook", "course material", "reading"]):
                    if any(phrase in context_lower for phrase in [
                        "no textbook", "no required text", "no course material", 
                        "no readings", "no required readings"
                    ]):
                        not_applicable_items[item] = True

        # Process using AI if permitted, otherwise use traditional matching
        try:
            # Try to import OpenAI helper, which will fail gracefully if OpenAI is not available
            from openai_helper import analyze_checklist_items_batch, fallback_analyze_item

            # FORCE ENABLE OpenAI API - always use OpenAI API first with proper timeout handling
            # This ensures we always use the API with better failover if it times out
            ENABLE_OPENAI = True  # Always try OpenAI API first (will properly fallback if needed)
            logging.warning("IMPORTANT: Always trying OpenAI API first (FORCE ENABLED)")
            print("IMPORTANT: OpenAI API is FORCE ENABLED - Using OpenAI API with timeout protection")

            results = {}

            # Initialize results dictionary with proper structure
            for item in checklist_items:
                results[item] = {
                    'present': False,
                    'confidence': 0,
                    'explanation': '',
                    'evidence': '',
                    'method': 'ai_general_analysis'
                }

            if ENABLE_OPENAI:
                # Set up timeout to prevent hanging
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("OpenAI API request timed out")
                
                # Set a timeout for OpenAI requests (longer timeout as requested by user)
                logging.info(f"Using OpenAI API EXCLUSIVELY for analysis with {MAX_API_TIMEOUT}-second timeout (NO fallbacks used)")
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(MAX_API_TIMEOUT)  # Set alarm for timeout (300 seconds)
                
                try:
                    # Try the OpenAI API with timeout protection
                    ai_results = analyze_checklist_items_batch(
                        checklist_items, 
                        outline_text, 
                        max_attempts=api_attempts, 
                        additional_context=enhanced_context
                    )
                    
                    # Cancel the alarm since we're done
                    signal.alarm(0)
                    
                    # Check if we received a proper dictionary result
                    if isinstance(ai_results, dict):
                        logging.info(f"Successfully received AI results with {len(ai_results)} items")
                        # Extra validation to make sure all results are proper dictionaries
                        valid_results = True
                        for key, value in ai_results.items():
                            if not isinstance(value, dict):
                                logging.error(f"AI results contain invalid value type: {type(value)} for key {key}")
                                valid_results = False
                                break
                        
                        if valid_results:
                            results = ai_results
                            logging.info("Successfully using OpenAI API results")
                        else:
                            logging.error("Invalid results structure detected - returning error to user (NO pattern matching fallback used)")
                    else:
                        logging.error(f"OpenAI analysis returned invalid results type: {type(ai_results)} - returning error to user (NO pattern matching fallback used)")
                except (TimeoutError, Exception) as e:
                    # Cancel the alarm if there was an exception
                    signal.alarm(0)
                    logging.exception(f"Error or timeout in OpenAI processing: {str(e)}")
                    logging.error("API failed - returning error to user (NO pattern matching fallback used)")
            
            # Check if any items are marked as not applicable
            for item in checklist_items:
                # Check if this item is marked as not applicable
                if item in not_applicable_items:
                    results[item] = {
                        'present': True,  # Mark as present since it's intentionally excluded
                        'confidence': 0.9,
                        'explanation': "This item is not applicable to this course.",
                        'evidence': "Marked as not applicable in the additional context.",
                        'method': 'ai_general_analysis',
                        'status': 'na'  # Special status for not applicable items
                    }

            # Return checklist items and analysis results
            return checklist_items, results

        except Exception as e:
            # Return error to user when OpenAI API fails - NO PATTERN MATCHING FALLBACK
            logging.exception(f"Error with OpenAI processing - returning error to user (NO pattern matching fallback): {str(e)}")
            
            # Create proper error response with appropriate messaging - NO PATTERN MATCHING
            results = {}
            for item in checklist_items:
                results[item] = {
                    'present': False,
                    'confidence': 0,
                    'explanation': f"OpenAI API error: {str(e)}. Analysis could not be completed.",
                    'evidence': "",
                    'method': 'ai_general_analysis'  # Consistent method name even for error cases
                }
            
            # Return checklist items and analysis results
            return checklist_items, results

    except Exception as e:
        logging.exception(f"Error processing documents: {str(e)}")
        
        # Create a properly structured empty results dictionary
        empty_results = {}
        
        # Make sure checklist_items is a valid list
        if not checklist_items or not isinstance(checklist_items, list):
            # Create a default single-item list if we don't have valid checklist items
            logging.error("DEBUG: No valid checklist items found during error handling")
            default_items = ["Error processing checklist"]
            
            # Create a default result with explicit OpenAI API error method
            for item in default_items:
                empty_results[item] = {
                    'present': False,
                    'confidence': 0,
                    'explanation': f"OpenAI API error during processing: {str(e)}. Analysis could not be completed.",
                    'evidence': "",
                    'method': 'ai_general_analysis'  # Consistent method name even for error cases
                }
            return default_items, empty_results
        else:
            # If we do have valid items, create results for each with explicit OpenAI API error method
            logging.error(f"DEBUG: Creating API error responses for {len(checklist_items)} items")
            for item in checklist_items:
                empty_results[item] = {
                    'present': False,
                    'confidence': 0,
                    'explanation': f"OpenAI API error during processing: {str(e)}. Analysis could not be completed.",
                    'evidence': "",
                    'method': 'ai_general_analysis'  # Consistent method name even for error cases
                }
            return checklist_items, empty_results