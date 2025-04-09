"""
Improved Pattern Matching for Course Outline Compliance Checking

This module provides enhanced pattern matching functions for more accurate 
detection of syllabus elements even when phrased differently.
"""

import re
import logging
from typing import List, Dict, Tuple, Any, Set

# Enhanced keyword dictionaries for each checklist item
CHECKLIST_KEYWORDS = {
    "instructor_email": [
        "instructor", "email", "contact", "professor", "faculty", "lecturer", 
        "teacher", "ucalgary.ca", "@ucalgary", "haskayne.ucalgary", "reach me", 
        "contacting", "get in touch", "reach out"
    ],
    
    "course_objectives": [
        "objectives", "outcomes", "goals", "learning outcomes", "course goals",
        "upon completion", "students will", "able to", "learn to", "course aims",
        "intended outcomes", "learning goals", "purpose", "by the end of this course"
    ],
    
    "textbooks": [
        "textbook", "readings", "materials", "required text", "course material",
        "books", "reading list", "bibliography", "required reading", "suggested reading",
        "recommended text", "course pack", "resources", "literature", "publications"
    ],
    
    "prohibited_materials": [
        "prohibited", "not allowed", "restricted", "forbidden", "not permitted", 
        "banned", "disallowed", "ChatGPT", "generative AI", "AI tools", 
        "academic integrity", "cheating", "plagiarism", "policy on", "ethics"
    ],
    
    "course_workload": [
        "workload", "time commitment", "hours per week", "expected effort",
        "time required", "work expected", "weekly time", "commitment", 
        "dedication", "engagement", "participation", "hours of work"
    ],
    
    "grading_scale": [
        "grading scale", "grade scale", "letter grade", "grade conversion", 
        "percentage", "A+", "A-", "B+", "letter grades", "grade points",
        "grade point average", "GPA", "grading system", "scoring"
    ],
    
    "grade_distribution": [
        "grade distribution", "assignment weights", "assessment weight",
        "component", "percent", "percentage", "weight", "worth", "value", 
        "points", "marking scheme", "evaluation", "assessment", "graded"
    ],
    
    "group_work": [
        "group work", "group project", "team", "collaborative", "group assignment",
        "peers", "partner", "teamwork", "group portion", "group contribution", 
        "team assignment", "group members", "team members", "group activity"
    ],
    
    "assessment_objectives": [
        "assessment", "objective", "learning outcome", "measure", "align",
        "alignment", "mapped to", "correspond", "related to", "linked to",
        "connection between", "demonstrates", "shows", "evidence"
    ],
    
    "due_dates": [
        "due date", "deadline", "due on", "submit by", "submission date",
        "calendar", "schedule", "timeline", "due", "date", "week", "day",
        "month", "time", "deadline", "cutoff"
    ],
    
    "early_assessment": [
        "30%", "thirty percent", "early feedback", "before last class", 
        "prior to end", "before final", "before end of term", "mid-term",
        "first half", "early in the course", "early assessment"
    ],
    
    "post_term_assignments": [
        "after last class", "after term ends", "after the end", "beyond last day",
        "past final class", "post-term", "after final lecture", "after course completion"
    ],
    
    "missed_assessment": [
        "missed", "absence", "unable to attend", "cannot submit", "miss an", 
        "deferral", "deferred", "make-up", "makeup", "accommodation", "exemption",
        "illness", "extenuating circumstances", "emergency", "excused", "extension"
    ],
    
    "late_policy": [
        "late", "overdue", "past deadline", "after due date", "tardy", "delayed",
        "penalty", "deduction", "points off", "percent off", "reduction", "marked down",
        "late submission", "grace period", "extension", "acceptance of late"
    ],
    
    "participation": [
        "participation", "engagement", "contribution", "discussion", "classroom", 
        "attendance", "engage", "contribute", "presence", "involvement", "active",
        "class participation", "seminar", "forum"
    ],
    
    "assignment_submission": [
        "submission", "submit", "turn in", "hand in", "upload", "deliver", "D2L",
        "dropbox", "email", "in person", "online", "platform", "instructions",
        "how to submit", "where to submit", "submission format", "file format"
    ],
    
    "group_project": [
        "group project", "team project", "team assignment", "collaborative project",
        "group work", "teamwork", "team formation", "group formation", "team members",
        "group members", "team roles", "group responsibilities", "peer evaluation"
    ],
    
    "midterm_quiz": [
        "midterm", "mid-term", "quiz", "test", "examination", "timing", "location",
        "modality", "format", "duration", "length", "open book", "closed book",
        "permitted materials", "allowed resources", "restrictions", "rules"
    ],
    
    "final_exam": [
        "final exam", "final test", "final assessment", "final", "examination",
        "culminating assessment", "end of term exam", "exam period", "registrar",
        "duration", "length", "location", "modality", "format", "permitted materials"
    ],
    
    "final_exam_weight": [
        "final exam", "weight", "percentage", "worth", "value", "less than 50%",
        "maximum", "up to", "no more than", "portion", "component", "constitutes"
    ],
    
    "take_home_final": [
        "take home", "take-home", "at home", "off-site", "remotely", "final project",
        "final assignment", "final paper", "culminating project", "end of term project"
    ],
    
    "instructor_contact": [
        "contacting", "contact", "reach", "available", "availability", "office hours",
        "office location", "get in touch", "reach out", "email", "communication",
        "response time", "questions", "help", "assistance", "support"
    ],
    
    "class_schedule": [
        "schedule", "calendar", "timetable", "outline", "weekly", "topics", "sessions",
        "meetings", "classes", "lectures", "lessons", "class by class", "week by week",
        "timeline", "course progression", "dates", "plan"
    ],
    
    "schedule_assignments": [
        "schedule", "calendar", "timeline", "assignment", "due date", "deadline",
        "submission", "due", "dates", "when", "plan", "week", "day", "time", "month"
    ],
    
    "schedule_exams": [
        "schedule", "calendar", "exam date", "test date", "quiz date", "assessment date",
        "midterm", "final exam", "final test", "examination period", "quiz time"
    ],
    
    "links": [
        "link", "url", "website", "http", "https", "www", "web", "site", "online",
        "internet", "webpage", "D2L", "Desire2Learn", "resource", "portal", "access"
    ]
}

def get_enhanced_keywords(item_text: str) -> List[str]:
    """
    Extract enhanced keywords for a checklist item based on its content.
    
    Args:
        item_text: The text of the checklist item
        
    Returns:
        List of relevant keywords to look for
    """
    item_lower = item_text.lower()
    
    # Determine which keyword set to use
    if "email" in item_lower and "instructor" in item_lower:
        return CHECKLIST_KEYWORDS["instructor_email"]
    elif "objective" in item_lower:
        return CHECKLIST_KEYWORDS["course_objectives"]
    elif "textbook" in item_lower or "course material" in item_lower:
        return CHECKLIST_KEYWORDS["textbooks"]
    elif "prohibited" in item_lower:
        return CHECKLIST_KEYWORDS["prohibited_materials"]
    elif "workload" in item_lower:
        return CHECKLIST_KEYWORDS["course_workload"]
    elif "grade scale" in item_lower or "grading scale" in item_lower:
        return CHECKLIST_KEYWORDS["grading_scale"]
    elif "grade distribution" in item_lower and "table" in item_lower:
        return CHECKLIST_KEYWORDS["grade_distribution"]
    elif "group work" in item_lower and "40%" in item_lower:
        return CHECKLIST_KEYWORDS["group_work"]
    elif "assessment" in item_lower and "objective" in item_lower:
        return CHECKLIST_KEYWORDS["assessment_objectives"]
    elif "due date" in item_lower and "distribution table" in item_lower:
        return CHECKLIST_KEYWORDS["due_dates"]
    elif "30%" in item_lower and "before the last day" in item_lower:
        return CHECKLIST_KEYWORDS["early_assessment"]
    elif "after the last day" in item_lower:
        return CHECKLIST_KEYWORDS["post_term_assignments"]
    elif "missed assessment" in item_lower or "missed assessment policy" in item_lower:
        return CHECKLIST_KEYWORDS["missed_assessment"]
    elif "late policy" in item_lower:
        return CHECKLIST_KEYWORDS["late_policy"]
    elif "participation" in item_lower:
        return CHECKLIST_KEYWORDS["participation"]
    elif "assignment" in item_lower and "submit" in item_lower:
        return CHECKLIST_KEYWORDS["assignment_submission"]
    elif "group project" in item_lower:
        return CHECKLIST_KEYWORDS["group_project"]
    elif ("midterm" in item_lower or "quiz" in item_lower) and not "final" in item_lower:
        return CHECKLIST_KEYWORDS["midterm_quiz"]
    elif "final exam" in item_lower and not "50%" in item_lower and not "take-home" in item_lower:
        return CHECKLIST_KEYWORDS["final_exam"]
    elif "final exam" in item_lower and "50%" in item_lower:
        return CHECKLIST_KEYWORDS["final_exam_weight"]
    elif "take-home" in item_lower or "take home" in item_lower:
        return CHECKLIST_KEYWORDS["take_home_final"]
    elif "contact" in item_lower and "instructor" in item_lower:
        return CHECKLIST_KEYWORDS["instructor_contact"]
    elif "class schedule" in item_lower and not "due date" in item_lower and not "exam" in item_lower:
        return CHECKLIST_KEYWORDS["class_schedule"]
    elif "class schedule" in item_lower and "due date" in item_lower:
        return CHECKLIST_KEYWORDS["schedule_assignments"]
    elif "class schedule" in item_lower and "exam" in item_lower:
        return CHECKLIST_KEYWORDS["schedule_exams"]
    elif "link" in item_lower:
        return CHECKLIST_KEYWORDS["links"]
    
    # Default case - extract key nouns and phrases
    words = item_lower.split()
    keywords = [word for word in words if len(word) > 3 and word not in 
               ["this", "that", "with", "from", "have", "does", "item", "section"]]
    return keywords

def extract_section(document_text: str, keywords: List[str], context_lines: int = 5) -> str:
    """
    Extract a relevant section from the document based on keywords.
    
    Args:
        document_text: The full document text
        keywords: List of keywords to look for
        context_lines: Number of lines to include before and after the match
        
    Returns:
        A section of the document that contains relevant content
    """
    lines = document_text.split('\n')
    matched_indices = []
    
    # Find lines with keyword matches
    for i, line in enumerate(lines):
        if any(keyword.lower() in line.lower() for keyword in keywords):
            matched_indices.append(i)
    
    if not matched_indices:
        return ""
    
    # Extract the section with context
    start_idx = max(0, min(matched_indices) - context_lines)
    end_idx = min(len(lines), max(matched_indices) + context_lines + 1)
    
    return '\n'.join(lines[start_idx:end_idx])

def improved_check_item(item: str, document_text: str) -> Tuple[bool, str, float]:
    """
    Improved pattern matching to check if an item is present in the document.
    Enhanced with advanced heuristics and more flexible matching thresholds.
    
    Args:
        item: The checklist item
        document_text: The full document text
        
    Returns:
        Tuple of (is_present, evidence, confidence)
    """
    # Get enhanced keywords
    keywords = get_enhanced_keywords(item)
    item_lower = item.lower()
    
    # Modified matching logic with weighted keywords and phrase matching
    total_score = 0
    max_score = len(keywords)
    matched_keywords = []
    
    # First pass: exact keyword matching with importance weighting
    for keyword in keywords:
        # Give higher weight to longer, more specific keywords
        weight = min(1.0, 0.4 + (len(keyword) / 20))
        
        if keyword.lower() in document_text.lower():
            total_score += weight
            matched_keywords.append(keyword)
    
    # Second pass: phrase matching for important concepts
    # Extract 2-3 word phrases from the item
    words = item_lower.split()
    if len(words) >= 3:
        # Extract key phrases (2-3 words)
        phrases = []
        for i in range(len(words) - 1):
            phrases.append(f"{words[i]} {words[i+1]}")
        for i in range(len(words) - 2):
            phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        
        # Check for phrase matches with higher weight
        for phrase in phrases:
            if len(phrase) > 6 and phrase not in ["with the", "does the", "in the", "for the", "of the"]:
                if phrase in document_text.lower():
                    total_score += 0.5  # Phrases are strong indicators
                    matched_keywords.append(phrase)
    
    # Calculate final match ratio
    match_ratio = total_score / max_score if max_score > 0 else 0
    
    # Extract relevant section
    relevant_section = extract_section(document_text, keywords)
    
    # Variable threshold based on item content
    # Lower threshold for policies that might be embedded in other sections
    base_threshold = 0.4  # Lower overall threshold for better recall
    if "policy" in item_lower or "rule" in item_lower or "procedure" in item_lower:
        threshold = base_threshold - 0.1  # Even lower for policies (0.3)
    elif "email" in item_lower or "contact" in item_lower:
        threshold = base_threshold - 0.05  # Lower for contact info (0.35)
    else:
        threshold = base_threshold
    
    # Determine presence based on adjusted threshold
    is_present = match_ratio >= threshold
    
    # For important items, double-check with alternative methods if not found
    if not is_present and (
        "email" in item_lower or 
        "policy" in item_lower or 
        "textbook" in item_lower or 
        "reading" in item_lower
    ):
        # Alternative detection using exact phrase search
        key_phrases = []
        if "email" in item_lower:
            key_phrases = ["contact", "email", "reach out"]
        elif "late policy" in item_lower:
            key_phrases = ["late", "after the deadline", "overdue", "penalty"]
        elif "missed" in item_lower:
            key_phrases = ["miss", "absence", "cannot attend", "unable to"]
        elif "textbook" in item_lower or "reading" in item_lower:
            key_phrases = ["book", "text", "reading", "literature", "resource"]
        
        # Check if any key phrase is present in a relevant context
        for phrase in key_phrases:
            if phrase in document_text.lower():
                # Confirm it's in a relevant context by looking at surrounding text
                pattern = r'(?i)(?:[^\n]*' + re.escape(phrase) + r'[^\n]*\n){1,3}'
                contexts = re.findall(pattern, document_text)
                for context in contexts:
                    # Check for topical relevance
                    if (
                        ("contact" in context.lower() and phrase == "email") or
                        ("policy" in context.lower() and phrase in ["late", "miss", "absence"]) or
                        (any(word in context.lower() for word in ["required", "recommended", "course"]) 
                         and phrase in ["book", "text", "reading"])
                    ):
                        is_present = True
                        match_ratio = 0.55  # Just above threshold to indicate found by alternative method
                        matched_keywords.append(phrase)
                        break
    
    # Create evidence with highlighted matches
    evidence = relevant_section
    for keyword in set(matched_keywords):  # Use set to avoid duplicate highlighting
        if keyword.lower() in evidence.lower():
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            evidence = pattern.sub(f'<mark>{keyword}</mark>', evidence)
    
    # Add diagnostic information to evidence
    if not evidence:
        evidence = f"No relevant section found. Searched for keywords: {', '.join(keywords[:5])}..."
    
    # Add match statistics
    evidence += f"\n\nMatch ratio: {match_ratio:.2f} (threshold: {threshold:.2f})"
    
    return is_present, evidence, match_ratio

def extract_email(text: str) -> str:
    """
    Extract a ucalgary.ca email from text.
    
    Args:
        text: Text to search for email
        
    Returns:
        Extracted email or empty string if none found
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*ucalgary\.ca\b'
    match = re.search(email_pattern, text)
    if match:
        return match.group(0)
    return ""

def extract_grade_table(text: str) -> str:
    """
    Extract grade distribution table or section from text.
    
    Args:
        text: Document text
        
    Returns:
        Extracted grade table section
    """
    # Search for common grade table headers
    table_pattern = r'(?i)(grade\s+distribution|grading|assessment|evaluation).*?(table|scheme|breakdown)'
    section_start = re.search(table_pattern, text)
    
    if not section_start:
        return ""
    
    # Extract a reasonable chunk after the header
    start_pos = section_start.start()
    table_text = text[start_pos:start_pos + 1500]  # Get 1500 chars, likely to include full table
    
    # Try to find a natural end to the table section
    end_markers = [
        r'\n\s*\n\w+',  # Two newlines followed by a word (new section)
        r'(?i)(\d{1,3}\s*%\s*$)',  # Line ending with percentage (likely last table row)
        r'(?i)(policy|schedule|procedure|plagiarism)'  # Common next section headers
    ]
    
    for marker in end_markers:
        end_match = re.search(marker, table_text)
        if end_match:
            end_pos = end_match.start()
            return table_text[:end_pos].strip()
    
    return table_text.strip()

def check_special_cases(item: str, document_text: str) -> Tuple[bool, str, float]:
    """
    Handle special case checklist items with custom logic.
    
    Args:
        item: Checklist item
        document_text: Document text
        
    Returns:
        Tuple of (is_present, evidence, confidence)
    """
    item_lower = item.lower()
    
    # Check for instructor email - enhanced to detect absence more reliably
    if "instructor" in item_lower and "email" in item_lower:
        # Two-stage verification for email: 
        # 1. Look for explicit email pattern
        email = extract_email(document_text)
        if email:
            return True, f"Found instructor email: {email}", 0.95
        
        # 2. If no email pattern found, check if there's an instructor section without email
        instructor_section_pattern = r'(?i)(instructor|professor|faculty|lecturer|teacher)[^\n]*\n(?:[^\n@]*\n){0,5}'
        instructor_section_match = re.search(instructor_section_pattern, document_text)
        
        if instructor_section_match:
            section_text = instructor_section_match.group(0)
            # If we find an instructor section but no email, it's likely missing
            if '@' not in section_text and '.ca' not in section_text:
                return False, f"Found instructor section but no email containing '@' or '.ca': {section_text[:150]}...", 0.9
    
    # Check for grade table
    if "grade distribution" in item_lower and "table" in item_lower:
        grade_table = extract_grade_table(document_text)
        if grade_table:
            return True, f"Found grade distribution information: {grade_table}", 0.9
    
    # Check for group work percentage
    if "group work" in item_lower and "40%" in item_lower:
        grade_table = extract_grade_table(document_text)
        if "group" in grade_table.lower():
            # Look for percentages near "group"
            percentage_pattern = r'group\s*.*?(\d{1,2})\s*%'
            match = re.search(percentage_pattern, grade_table.lower())
            if match:
                percentage = int(match.group(1))
                if percentage <= 40:
                    return True, f"Group work is {percentage}%, which is 40% or less", 0.9
                else:
                    return False, f"Group work is {percentage}%, which exceeds 40%", 0.9
    
    # Check for late policy with enhanced detection
    if "late policy" in item_lower:
        # Look for specific sections or phrases about late submissions
        late_policy_patterns = [
            r'(?i)(late\s*(?:submission|work|assignment)s?)[^.]*\.',  # Sentences about late submissions
            r'(?i)((?:penalt|deduct|reduc|mark down).*late)[^.]*\.',  # Sentences about penalties for lateness
            r'(?i)((?:grace|extension).*period)[^.]*\.',             # Sentences about grace periods
            r'(?i)(\d+%\s*(?:per|each|every)\s*(?:day|hour|week))[^.]*\.'  # Percentage penalties per time unit
        ]
        
        for pattern in late_policy_patterns:
            match = re.search(pattern, document_text)
            if match:
                context = document_text[max(0, match.start() - 100):min(len(document_text), match.end() + 100)]
                return True, f"Found late policy: {context}", 0.9
        
        # If no specific pattern found, check if "late" appears in a policy-like context
        policy_sections = re.findall(r'(?i)(?:policy|policies|rule|guideline)[^\n]*\n(?:[^\n]*\n){0,10}', document_text)
        for section in policy_sections:
            if "late" in section.lower():
                return True, f"Found policy section mentioning 'late': {section[:200]}...", 0.8
        
        # Explicitly return False with evidence if we've searched and found nothing
        return False, "No late policy found despite searching for specific patterns and policy sections.", 0.85
    
    # Check for missed assessment policy with enhanced detection
    if "missed assessment" in item_lower or "missed assignment policy" in item_lower:
        # Look for specific patterns related to missed assessments
        missed_patterns = [
            r'(?i)(miss(?:ed|ing)?\s*(?:assessment|assignment|exam|quiz|test)s?)[^.]*\.',  # Sentences about missing assessments
            r'(?i)(absence|absent|unable to attend|cannot attend)[^.]*\.',  # Sentences about absences
            r'(?i)(medical\s*(?:note|documentation|certificate))[^.]*\.',   # Medical documentation
            r'(?i)(accommodat(?:ion|e))[^.]*\.',                            # Accommodation references
            r'(?i)(make-?up\s*(?:exam|test|assignment))[^.]*\.'            # Make-up assessments
        ]
        
        for pattern in missed_patterns:
            match = re.search(pattern, document_text)
            if match:
                context = document_text[max(0, match.start() - 100):min(len(document_text), match.end() + 100)]
                return True, f"Found missed assessment policy: {context}", 0.9
        
        # Check policy sections for mentions of missed work
        policy_sections = re.findall(r'(?i)(?:policy|policies|rule|guideline)[^\n]*\n(?:[^\n]*\n){0,10}', document_text)
        for section in policy_sections:
            if any(word in section.lower() for word in ["miss", "absence", "unable", "defer", "extension"]):
                return True, f"Found policy section related to missed work: {section[:200]}...", 0.8
        
        # Explicitly return False with evidence if we've searched and found nothing
        return False, "No missed assessment policy found despite searching for specific patterns and policy sections.", 0.85
    
    # Check for textbooks with enhanced detection
    if "textbook" in item_lower or "reading" in item_lower or "materials" in item_lower:
        # Look for specific textbook sections
        textbook_patterns = [
            r'(?i)(textbook|required readings?|required materials?|course materials?)[^\n]*\n(?:[^\n]*\n){0,20}',
            r'(?i)(readings?|materials?)[^.]*required[^.]*\.',
            r'(?i)(books?|publications?|literature)[^.]*\.'
        ]
        
        for pattern in textbook_patterns:
            matches = re.findall(pattern, document_text)
            for match in matches:
                # Check if the match mentions authors, titles, or publishers
                if any(indicator in match.lower() for indicator in [
                    "author", "title", "publisher", "press", "publication", "edition", 
                    "recommended", "required", "chapter", "pages", "eds", "et al", 
                    "www", "http", "isbn", "available", "purchase"]):
                    return True, f"Found textbook/readings section: {match[:300]}...", 0.9
        
        # If none of the specific patterns matched well, do a broader search
        if re.search(r'(?i)(textbook|book|reading|publication|literature|resource)[s]?', document_text):
            context = extract_section(document_text, CHECKLIST_KEYWORDS["textbooks"], 8)
            # Look for publisher/author patterns in the context
            if any(indicator in context.lower() for indicator in [
                "author", "publication", "press", "edition", "publisher", 
                "vol", "pages", "pp", "chapter", "isbn"]):
                return True, f"Found possible textbook reference: {context[:300]}...", 0.75
    
    # Indicate no special handling - return False instead of None to fix type error
    return False, "", 0.0

def extract_email_addresses(text: str) -> List[str]:
    """
    Extract all email addresses from the given text.
    Uses a comprehensive regex pattern to detect various email formats.
    
    Args:
        text: The text to search for email addresses
        
    Returns:
        List of found email addresses
    """
    # Comprehensive email pattern that catches a wide variety of valid emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    return re.findall(email_pattern, text)

def check_instructor_email(document_text: str) -> Tuple[bool, str, float]:
    """
    Enhanced instructor email detection with multiple approaches.
    
    Args:
        document_text: The document text to search
        
    Returns:
        Tuple of (has_email, evidence, confidence)
    """
    # First approach: Find all emails in the document
    all_emails = extract_email_addresses(document_text)
    
    # Look for instructor context near emails
    if all_emails:
        for email in all_emails:
            # Get context around the email
            email_pos = document_text.find(email)
            if email_pos > -1:
                context_start = max(0, email_pos - 300)
                context_end = min(len(document_text), email_pos + 300)
                context = document_text[context_start:context_end]
                
                # Check if this email appears in an instructor context
                instructor_terms = ['instructor', 'professor', 'faculty', 'lecturer', 
                                   'teacher', 'coordinator', 'dr.', 'ph.d', 'contact']
                
                if any(term in context.lower() for term in instructor_terms):
                    highlighted_context = context.replace(
                        email, f"<span style='background-color: #c2f0c2;'>{email}</span>"
                    )
                    for term in instructor_terms:
                        if term in context.lower():
                            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                            highlighted_context = pattern.sub(
                                f"<span style='background-color: #c2f0c2;'>{term}</span>", 
                                highlighted_context, 
                                count=1
                            )
                    
                    # Check if it's a ucalgary.ca email (higher confidence if it is)
                    confidence = 0.95 if "ucalgary.ca" in email.lower() else 0.85
                    return True, f"Found instructor email in context: {highlighted_context}", confidence
    
    # Second approach: Look for instructor sections without emails
    instructor_sections = re.findall(
        r'(?i)(?:instructor|professor|contact|office hours)[^\n]*(?:\n[^\n]*){0,15}', 
        document_text
    )
    
    if instructor_sections:
        # Join all instructor-related sections
        combined_sections = '\n'.join(instructor_sections)
        
        # Check if emails exist in any instructor section
        section_emails = extract_email_addresses(combined_sections)
        
        if section_emails:
            # We found emails in instructor sections, but they weren't caught by the first approach
            # This is a backup verification for complex formatting cases
            email = section_emails[0]
            highlighted_section = combined_sections.replace(
                email, f"<span style='background-color: #c2f0c2;'>{email}</span>"
            )
            confidence = 0.9 if "ucalgary.ca" in email.lower() else 0.8
            return True, f"Found instructor email in section: {highlighted_section[:300]}...", confidence
        
        # If we found instructor sections but no emails in them
        if any(contact in combined_sections.lower() for contact in 
              ['telephone', 'phone', 'office', 'contact', 'hours', 'appointment']):
            # There are contact details but no email
            return False, f"Found instructor contact section but no email: {combined_sections[:300]}...", 0.9
    
    # If we've checked everything and can't make a definitive determination
    # We'll report not found with high confidence
    return False, "No instructor email found after extensive search of contact sections.", 0.85

def enhanced_check_item_in_document(item: str, document_text: str) -> Tuple[bool, str, float]:
    """
    Main function to check if a checklist item is satisfied in the document.
    Enhanced with multi-pass scanning and comprehensive checks.
    
    Args:
        item: Checklist item
        document_text: Document text
        
    Returns:
        Tuple of (is_present, evidence, confidence)
    """
    # First try special cases
    is_present, evidence, confidence = check_special_cases(item, document_text)
    if is_present:  # Modified: Check boolean value directly rather than "is not None"
        return is_present, evidence, confidence
    
    # Get improved pattern matching results
    is_present, evidence, confidence = improved_check_item(item, document_text)
    
    # Extra verification for crucial items known to have accuracy issues
    # This adds a second pass of detection for important items
    item_lower = item.lower()
    
    if not is_present and (
        "instructor email" in item_lower or 
        "late policy" in item_lower or 
        "missed assessment" in item_lower or 
        "textbook" in item_lower or 
        "reading" in item_lower
    ):
        # Do a comprehensive second-pass check with specialized detection
        
        # Check for instructor email with enhanced detection
        if "instructor email" in item_lower:
            has_email, evidence, confidence = check_instructor_email(document_text)
            return has_email, evidence, confidence
        
        # Check for late policy
        if "late policy" in item_lower:
            # Look for sections that might contain late policy without using the word "late"
            policy_sections = re.findall(r'(?i)(polic(?:y|ies)|rule|guideline|submission)[^\n]*\n(?:[^\n]*\n){0,15}', document_text)
            for section in policy_sections:
                if any(word in section.lower() for word in [
                    "deadline", "due date", "submit", "timely", "punctual", 
                    "penalty", "deduction", "grade reduction"
                ]):
                    # Check if there are percentage deductions or time references
                    if re.search(r'(?i)(\d+%|\d+\s*point)', section) or \
                       re.search(r'(?i)(day|hour|time|date)', section):
                        return True, f"Found potential late policy section: {section[:200]}...", 0.75
            
            # If we've thoroughly checked and still haven't found anything
            assignment_sections = re.findall(r'(?i)(assignment|submission|grading)[^\n]*\n(?:[^\n]*\n){0,15}', document_text)
            if not any('late' in section.lower() for section in assignment_sections):
                return False, "No late policy found after thorough examination of policy and assignment sections.", 0.8
        
        # Enhanced missed assessment policy detection with multi-pass checks
        if "missed assessment" in item_lower or "missed assignment" in item_lower or "missed midterm" in item_lower:
            # First approach: Check for policy sections containing relevant terms
            policy_sections = re.findall(
                r'(?i)(?:polic(?:y|ies)|rule|guideline|grading|assessment|exam|submit)[^\n]*(?:\n[^\n]*){0,20}', 
                document_text
            )
            
            # Broad list of terms related to missed assessments/policies
            missed_terms = [
                "medical", "doctor", "illness", "emergency", "absence", "sick", 
                "miss", "unable", "cannot", "accommodation", "documented", 
                "extenuating", "circumstance", "situation", "excuse", "deferral", 
                "deferred", "make-up", "makeup", "alternative", "substitute", 
                "extension", "exemption", "dispensation", "waiver", "relief"
            ]
            
            for section in policy_sections:
                section_lower = section.lower()
                # Count how many relevant terms appear in this section
                term_count = sum(1 for term in missed_terms if term in section_lower)
                
                if term_count >= 2:  # Need at least 2 relevant terms to increase confidence
                    # Highlight the relevant terms in the section
                    highlighted_section = section
                    for term in missed_terms:
                        if term in section_lower:
                            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                            highlighted_section = pattern.sub(
                                f"<span style='background-color: #c2f0c2;'>{term}</span>", 
                                highlighted_section
                            )
                    
                    # Adjust confidence based on how many terms were found and if specific phrases exist
                    confidence = 0.7 + (min(term_count, 5) * 0.05)  # Up to 0.95 confidence
                    
                    # Boost confidence for strong indicator phrases
                    strong_phrases = [
                        "missed exam policy", "missed assignment policy", 
                        "missed assessment", "unable to attend", "unable to write", 
                        "medical documentation", "doctor's note", "make-up exam"
                    ]
                    
                    if any(phrase in section_lower for phrase in strong_phrases):
                        confidence = min(0.95, confidence + 0.1)
                    
                    return True, f"Found missed assessment policy section: {highlighted_section[:300]}...", confidence
            
            # Second approach: Look for medical/emergency/absence mentions near assessment terms
            for term1 in ["medical", "doctor", "illness", "emergency", "absence", "sick"]:
                for term2 in ["exam", "test", "quiz", "assignment", "assessment", "midterm", "deadline"]:
                    # Look for these terms within reasonable proximity
                    pattern = r'(?i)(?:\w+\W+){0,10}' + re.escape(term1) + r'(?:\W+\w+){0,15}' + re.escape(term2)
                    alt_pattern = r'(?i)(?:\w+\W+){0,10}' + re.escape(term2) + r'(?:\W+\w+){0,15}' + re.escape(term1)
                    
                    for p in [pattern, alt_pattern]:
                        match = re.search(p, document_text)
                        if match:
                            context_start = max(0, match.start() - 100)
                            context_end = min(len(document_text), match.end() + 100)
                            context = document_text[context_start:context_end]
                            
                            highlighted_context = context
                            for t in [term1, term2]:
                                pattern = re.compile(r'\b' + re.escape(t) + r'\b', re.IGNORECASE)
                                highlighted_context = pattern.sub(
                                    f"<span style='background-color: #c2f0c2;'>{t}</span>", 
                                    highlighted_context
                                )
                            
                            return True, f"Found medical/absence terms near assessment references: {highlighted_context}", 0.8
            
            # Third approach: Look for explicit statements about missing assessments
            explicit_patterns = [
                r'(?i)if\s+you\s+(?:miss|cannot\s+attend|are\s+unable\s+to\s+(?:write|complete|attend|take))',
                r'(?i)in\s+the\s+event\s+(?:of|that)\s+you\s+(?:miss|cannot)',
                r'(?i)(?:student|students)\s+who\s+(?:miss|are\s+absent|cannot\s+attend)'
            ]
            
            for pattern in explicit_patterns:
                match = re.search(pattern, document_text)
                if match:
                    context_start = max(0, match.start() - 100)
                    context_end = min(len(document_text), match.end() + 200)  # Capture more of what follows
                    context = document_text[context_start:context_end]
                    return True, f"Found explicit statement about missing assessments: {context}", 0.85
            
            # Final check: If we've thoroughly checked and found nothing relevant
            # This check is more comprehensive
            if not any(term in document_text.lower() for term in missed_terms):
                # No relevant terms at all in the document - high confidence it's missing
                return False, "No missed assessment policy found after comprehensive multi-pass examination.", 0.9
        
        # Check for textbooks or readings
        if "textbook" in item_lower or "reading" in item_lower or "course material" in item_lower:
            # Check for specific textbook/reading sections
            material_sections = re.findall(r'(?i)(textbook|reading|course material|material|resource)[^\n]*\n(?:[^\n]*\n){0,20}', document_text)
            for section in material_sections:
                # Check for author/title/publisher patterns
                if re.search(r'(?i)(author|title|publisher|ISBN|edition)', section) or \
                   re.search(r'(?i)([A-Z][a-z]+,\s+[A-Z]\.)', section) or \
                   re.search(r'(?i)(recommended|required)\s+(text|book|reading)', section):
                    return True, f"Found textbook/reading section: {section[:300]}...", 0.8
                
                # Check for book listing patterns like "1. Book Title" or "- Book Title"
                if re.search(r'(?i)(^|\n)[\s\d\-\*•]+[A-Z]', section):
                    return True, f"Found potential reading list format: {section[:300]}...", 0.75
            
            # If no specific textbook section, check if there's a statement about no textbook
            if re.search(r'(?i)no\s+required\s+textbook', document_text) or \
               re.search(r'(?i)no\s+textbook\s+is\s+required', document_text):
                return False, "Document explicitly states no required textbook.", 0.9
            
            # Check for D2L or online materials
            if re.search(r'(?i)(materials|readings)\s+(available|posted|found)\s+on\s+D2L', document_text) or \
               re.search(r'(?i)(materials|readings)\s+(available|posted|found)\s+online', document_text):
                return True, "Found reference to online/D2L course materials.", 0.75
    
    # Return the original pattern matching results
    return is_present, evidence, confidence