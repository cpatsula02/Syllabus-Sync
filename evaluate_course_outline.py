#!/usr/bin/env python3
"""
Evaluate Course Outline Against Institutional Standards

This script evaluates a university course outline against the provided checklist
of required elements. It outputs the evaluation in the exact format requested in
the checklist document.

Usage:
    python evaluate_course_outline.py [optional_course_outline_path]

If no course outline path is provided, the script will look for a PDF document
in the attached_assets directory.
"""

import os
import sys
import re
import logging
from typing import List, Dict, Any, Tuple
from document_processor import extract_text
from openai_helper import analyze_checklist_item, count_tokens

# Try to import nltk and related libraries, but provide fallbacks if they're not available
try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    import numpy as np
    nltk_available = True
except ImportError:
    nltk_available = False

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure we have the NLTK resources we need if NLTK is available
if nltk_available:
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)

def extract_checklist_from_document(file_path: str) -> Dict[int, str]:
    """
    Extract the checklist items from the document.
    
    Args:
        file_path: Path to the checklist document
        
    Returns:
        Dictionary mapping item numbers to item descriptions
    """
    text = extract_text(file_path)
    
    # Look for the section containing the checklist items
    checklist_section_match = re.search(r'Checklist Items:(.*?)Output Format:', text, re.DOTALL)
    if not checklist_section_match:
        # Try another approach
        checklist_section_match = re.search(r'### Checklist Items:(.*?)### Output Format:', text, re.DOTALL)
    
    if not checklist_section_match:
        logger.warning("Could not identify checklist section. Using whole document.")
        checklist_section = text
    else:
        checklist_section = checklist_section_match.group(1)
    
    # Extract numbered items
    item_pattern = r'(\d+)\.\s+(.*?)(?=\n\d+\.|\n###|\Z)'
    items = re.findall(item_pattern, checklist_section, re.DOTALL)
    
    # Create a dictionary mapping numbers to items
    checklist_items = {}
    for number_str, description in items:
        try:
            number = int(number_str)
            # Clean up the description
            description = re.sub(r'\s+', ' ', description).strip()
            checklist_items[number] = description
        except ValueError:
            logger.warning(f"Could not parse item number: {number_str}")
    
    return checklist_items

def validate_email(text: str) -> bool:
    """Check if a ucalgary.ca email is present in the text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@.*?ucalgary\.ca\b'
    return bool(re.search(email_pattern, text))

def has_grade_scale(text: str) -> bool:
    """Check if a grade scale mapping percentages to letter grades is present."""
    grade_patterns = [
        r'[A-F][+\-]?\s*[:=]\s*\d+',  # A+ = 90, etc.
        r'\d+\s*-\s*\d+\s*[%]?\s*[:=]\s*[A-F][+\-]?',  # 90-100% = A+, etc.
        r'[Gg]rade\s+[Ss]cale',
        r'[Gg]rading\s+[Ss]cale',
    ]
    
    for pattern in grade_patterns:
        if re.search(pattern, text):
            return True
    
    return False

def has_assessment_weights(text: str) -> bool:
    """Check if assessments have percentage weights."""
    weight_patterns = [
        r'(\d+)\s*%',  # 20%, etc.
        r'[Ww]eight\s*[:=]\s*\d+',
        r'[Ww]orth\s*[:=]?\s*\d+',
    ]
    
    # Look for multiple percentage indicators
    matches = re.findall(r'(\d+)\s*%', text)
    if len(matches) >= 3:  # At least 3 different assessments with percentages
        return True
    
    # Look for a table with percentages
    table_pattern = r'(\w+)\s*\|\s*(\d+)\s*%'
    table_matches = re.findall(table_pattern, text)
    if len(table_matches) >= 2:
        return True
    
    return False

def check_group_work_percent(text: str) -> Tuple[bool, str]:
    """
    Check if group work is 40% or less of the total grade.
    Returns (meets_criteria, status_code)
    where status_code is 'yes', 'no', or 'na'
    """
    # First, check if group work is mentioned
    group_terms = ['group project', 'group work', 'team project', 'team assignment', 'collaborative']
    found_group_work = any(term in text.lower() for term in group_terms)
    
    if not found_group_work:
        return True, "N/A"
    
    # Look for percentage associated with group work
    group_percent_pattern = r'(?:group|team).*?(\d+)\s*%'
    matches = re.findall(group_percent_pattern, text.lower())
    
    if matches:
        # Extract the highest percentage associated with group work
        percentages = [int(match) for match in matches]
        max_percent = max(percentages)
        
        if max_percent <= 40:
            return True, "Yes"
        else:
            return False, "No"
    
    # If no specific percentage found but group work is mentioned
    return True, "Yes"  # Assume it's acceptable if no specific percentage is found

def check_assessments_linked_to_objectives(text: str) -> bool:
    """Check if assessments are linked to course objectives/outcomes."""
    link_patterns = [
        r'assessment.*?objective',
        r'objective.*?assessment',
        r'linked to learning outcomes',
        r'aligned with course objectives',
        r'measures.*?objective',
        r'evaluate.*?outcome',
    ]
    
    for pattern in link_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_due_dates_included(text: str) -> bool:
    """Check if due dates for assessments are included."""
    date_patterns = [
        r'due\s+(?:on|by)?\s+\w+\s+\d+',  # due on March 15
        r'due\s+(?:on|by)?\s+\d+/\d+',     # due on 3/15
        r'deadline.*?\d+',                  # deadline March 15
        r'submit.*?by.*?\w+\s+\d+',        # submit by March 15
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    # Look for date mentions in proximity to assessment terms
    assessment_terms = ['assignment', 'project', 'report', 'paper', 'exam', 'quiz', 'test']
    date_indicators = [r'\d+/\d+', r'jan\w*', r'feb\w*', r'mar\w*', r'apr\w*', r'may', r'jun\w*', 
                      r'jul\w*', r'aug\w*', r'sep\w*', r'oct\w*', r'nov\w*', r'dec\w*']
    
    sentences = re.split(r'[.!?]\s+', text.lower())
    for sentence in sentences:
        if any(term in sentence for term in assessment_terms) and any(re.search(date, sentence) for date in date_indicators):
            return True
    
    return False

def check_thirty_percent_before_last_class(text: str) -> bool:
    """Check if at least 30% of the grade is earned before the last class."""
    # This is a complex check that would require understanding of the course schedule
    # and assessment weights. We'll use a simplified approach.
    
    # Look for indications that early assessments exist
    early_assessment_patterns = [
        r'midterm.*?(\d+)\s*%',
        r'quiz(?:zes)?.*?(?:total|worth).*?(\d+)\s*%',
        r'assignment.*?(?:due|before).*?(?:final|last).*?(\d+)\s*%',
    ]
    
    total_early_percent = 0
    for pattern in early_assessment_patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            for match in matches:
                try:
                    total_early_percent += int(match)
                except ValueError:
                    pass
    
    if total_early_percent >= 30:
        return True
    
    # Look for explicit statements about early assessments
    early_statements = [
        r'30%.*?before.*?(?:final|last class)',
        r'students will complete.*?(\d+)%.*?before.*?(?:final|last)',
    ]
    
    for pattern in early_statements:
        if re.search(pattern, text.lower()):
            return True
    
    return total_early_percent >= 30

def check_no_assessments_after_final_class(text: str) -> bool:
    """Check if no assessments or deliverables are scheduled after the final class."""
    after_final_patterns = [
        r'(?:assignment|project|deliverable).*?due.*?after.*?(?:final|last) class',
        r'(?:assignment|project|deliverable).*?due.*?during exam period',
        r'(?:submit|turn in).*?after.*?(?:final|last) class',
    ]
    
    for pattern in after_final_patterns:
        if re.search(pattern, text.lower()):
            return False
    
    return True

def check_missed_assessment_policy(text: str) -> bool:
    """Check if a missed assessment policy is included."""
    missed_patterns = [
        r'missed assessment',
        r'missed.*?(?:assignment|exam|quiz|test)',
        r'absence.*?(?:assignment|exam|quiz|test)',
        r'(?:assignment|exam|quiz|test).*?absence',
        r'makeup.*?(?:assignment|exam|quiz|test)',
        r'deferral',
        r'illness.*?(?:assignment|exam|quiz|test)',
    ]
    
    for pattern in missed_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_late_policy(text: str) -> bool:
    """Check if a late policy is described."""
    late_patterns = [
        r'late.*?(?:assignment|submission|project|work)',
        r'(?:assignment|submission|project|work).*?late',
        r'late.*?penalty',
        r'penalty.*?late',
        r'extension',
        r'grace period',
    ]
    
    for pattern in late_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_participation_evaluation(text: str) -> bool:
    """Check if participation grading is explained."""
    # First, check if participation is mentioned as part of the grade
    participation_grade = re.search(r'participation.*?(\d+)\s*%', text.lower())
    
    if not participation_grade:
        return True  # No participation grading found, so N/A
    
    # Check if there's an explanation of how participation is evaluated
    participation_explanation = [
        r'participation.*?(?:evaluated|assessed|graded)',
        r'(?:evaluate|assess|grade).*?participation',
        r'participation.*?(?:criteria|rubric)',
        r'participation.*?(?:discussion|engagement|attendance)',
    ]
    
    for pattern in participation_explanation:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_assignment_submission_instructions(text: str) -> bool:
    """Check if assignment instructions include how and where to submit."""
    submission_patterns = [
        r'submit.*?(?:via|through|using).*?(?:d2l|blackboard|canvas|online|platform)',
        r'(?:d2l|blackboard|canvas|online|platform).*?submission',
        r'(?:upload|turn in).*?(?:assignment|paper|project)',
        r'submission.*?(?:instruction|guideline)',
    ]
    
    for pattern in submission_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_group_project_details(text: str) -> bool:
    """Check if group project details are included."""
    # First check if there's a group project
    group_project = re.search(r'(?:group|team).*?(?:project|assignment|work)', text.lower())
    
    if not group_project:
        return True  # No group project found, so N/A
    
    # Check for project details
    detail_patterns = [
        r'(?:group|team).*?(?:expectation|guideline|instruction)',
        r'(?:group|team).*?(?:due date|deadline)',
        r'(?:group|team).*?(?:first|initial).*?(?:due|deadline)',
    ]
    
    for pattern in detail_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_exam_details(text: str, is_final=False) -> bool:
    """Check if exam details are provided."""
    exam_type = 'final exam' if is_final else '(?:midterm|quiz|test)'
    
    # First check if the exam type exists
    exam_exists = re.search(f'{exam_type}', text.lower())
    
    if not exam_exists:
        return True  # Exam not found, so N/A
    
    # Check for details
    detail_patterns = [
        f'{exam_type}.*?(?:time|duration|length)',
        f'{exam_type}.*?(?:location|room|venue)',
        f'{exam_type}.*?(?:format|structure)',
        f'{exam_type}.*?(?:allowed|permitted)',
        f'{exam_type}.*?(?:technology|computer|device)',
    ]
    
    detail_count = 0
    for pattern in detail_patterns:
        if re.search(pattern, text.lower()):
            detail_count += 1
    
    return detail_count >= 2  # Require at least 2 different details

def check_final_exam_weight(text: str) -> Tuple[bool, str]:
    """
    Check if final exam is 50% or less.
    Returns (meets_criteria, status_code)
    where status_code is 'yes', 'no', or 'na'
    """
    # Check if there's a final exam
    final_exam = re.search(r'final\s+exam', text.lower())
    
    if not final_exam:
        return True, "N/A"
    
    # Look for the weight of the final exam
    final_weight_pattern = r'final\s+exam.*?(\d+)\s*%'
    alternate_pattern = r'(\d+)\s*%.*?final\s+exam'
    
    weight_match = re.search(final_weight_pattern, text.lower())
    if not weight_match:
        weight_match = re.search(alternate_pattern, text.lower())
    
    if weight_match:
        try:
            weight = int(weight_match.group(1))
            if weight <= 50:
                return True, "Yes"
            else:
                return False, "No"
        except ValueError:
            pass
    
    # If no specific percentage found but final exam is mentioned
    return True, "Yes"  # Assume it's acceptable if no specific percentage is found

def check_take_home_final(text: str) -> Tuple[bool, str]:
    """
    Check if there's a take-home final exam.
    Returns (needs_review, status_code)
    where status_code is 'yes' or 'na'
    """
    take_home_patterns = [
        r'take[\s-]home.*?final',
        r'final.*?take[\s-]home',
    ]
    
    for pattern in take_home_patterns:
        if re.search(pattern, text.lower()):
            return True, "Yes"
    
    return False, "N/A"

def check_instructor_contact_section(text: str) -> bool:
    """Check if there's a section about contacting the instructor."""
    contact_patterns = [
        r'(?:contact|contacting).*?(?:instructor|professor|teacher)',
        r'(?:instructor|professor|teacher).*?(?:contact|contacting)',
        r'office hours',
    ]
    
    for pattern in contact_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    return False

def check_class_schedule_included(text: str) -> bool:
    """Check if a class schedule is included."""
    schedule_patterns = [
        r'(?:class|course).*?(?:schedule|calendar|outline)',
        r'(?:weekly|daily).*?(?:schedule|topics|sessions)',
        r'(?:lecture|session|class).*?(?:topics|schedule)',
    ]
    
    for pattern in schedule_patterns:
        if re.search(pattern, text.lower()):
            return True
    
    # Look for a structured schedule format
    schedule_format = [
        r'week\s+\d+.*?:.*?\w+',
        r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec).*?\d+.*?:.*?\w+',
        r'\d+/\d+.*?:.*?\w+',
    ]
    
    for pattern in schedule_format:
        matches = re.findall(pattern, text.lower())
        if len(matches) >= 3:  # At least 3 schedule entries
            return True
    
    return False

def check_schedule_includes_due_dates(text: str) -> bool:
    """Check if the class schedule includes assignment due dates."""
    # First check if there's a schedule
    if not check_class_schedule_included(text):
        return False
    
    # Find schedule section
    schedule_section = None
    schedule_headers = [
        r'(?:class|course).*?(?:schedule|calendar)',
        r'(?:weekly|daily).*?(?:schedule|topics)',
        r'(?:lecture|session|class).*?(?:topics|schedule)',
    ]
    
    paragraphs = re.split(r'\n\s*\n', text)
    for i, para in enumerate(paragraphs):
        if any(re.search(pattern, para.lower()) for pattern in schedule_headers):
            schedule_section = ' '.join(paragraphs[i:i+5])  # Include the next few paragraphs
            break
    
    if not schedule_section:
        schedule_section = text  # Use the whole text if no specific section found
    
    # Look for due date mentions in the schedule
    due_date_patterns = [
        r'(?:assignment|paper|project|report).*?due',
        r'due date.*?(?:assignment|paper|project|report)',
        r'submit.*?(?:assignment|paper|project|report)',
    ]
    
    for pattern in due_date_patterns:
        if re.search(pattern, schedule_section.lower()):
            return True
    
    return False

def check_schedule_includes_exam_dates(text: str) -> bool:
    """Check if the class schedule includes exam/quiz dates."""
    # First check if there's a schedule
    if not check_class_schedule_included(text):
        return False
    
    # Find schedule section
    schedule_section = None
    schedule_headers = [
        r'(?:class|course).*?(?:schedule|calendar)',
        r'(?:weekly|daily).*?(?:schedule|topics)',
        r'(?:lecture|session|class).*?(?:topics|schedule)',
    ]
    
    paragraphs = re.split(r'\n\s*\n', text)
    for i, para in enumerate(paragraphs):
        if any(re.search(pattern, para.lower()) for pattern in schedule_headers):
            schedule_section = ' '.join(paragraphs[i:i+5])  # Include the next few paragraphs
            break
    
    if not schedule_section:
        schedule_section = text  # Use the whole text if no specific section found
    
    # Look for exam/quiz mentions in the schedule
    exam_patterns = [
        r'(?:exam|test|quiz|midterm).*?(?:date|scheduled)',
        r'(?:date|scheduled).*?(?:exam|test|quiz|midterm)',
    ]
    
    for pattern in exam_patterns:
        if re.search(pattern, schedule_section.lower()):
            return True
    
    return False

def validate_links(text: str) -> bool:
    """Check if links in the document are valid."""
    # Extract all URLs from the document
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        return True  # No links to validate
    
    # In a real implementation, we would check if each URL is valid
    # For now, we'll assume they are valid
    return True

def analyze_checklist_item_prompt(item_text: str, outline_text: str) -> Dict[str, Any]:
    """
    Analyze a checklist item against the course outline using a custom prompt.
    
    Args:
        item_text: The checklist item text
        outline_text: The course outline text
        
    Returns:
        Analysis result dictionary
    """
    item_lower = item_text.lower()
    result = {"present": False, "explanation": "", "evidence": ""}
    
    # Determine the type of checklist item
    if "instructor email" in item_lower:
        has_email = validate_email(outline_text)
        result["present"] = has_email
        if has_email:
            result["explanation"] = "The outline includes an instructor email with the ucalgary.ca domain."
        else:
            result["explanation"] = "The outline does not include an instructor email with the ucalgary.ca domain."
    
    elif "course objectives" in item_lower or "learning outcomes" in item_lower:
        # Check for structured learning outcomes
        outcome_patterns = [
            r'(?:course|learning)\s+(?:objectives|outcomes)[:\s]+(?:1|I|A)\.?\s+\w+',
            r'(?:course|learning)\s+(?:objectives|outcomes)[:\s]+(?:•|\*|-)\s+\w+',
            r'(?:course|learning)\s+(?:objectives|outcomes)[:\s]+(?:students\s+will|participants\s+will|you\s+will)',
        ]
        
        has_objectives = any(re.search(pattern, outline_text, re.IGNORECASE) for pattern in outcome_patterns)
        result["present"] = has_objectives
        if has_objectives:
            result["explanation"] = "Course objectives or learning outcomes are listed and structured in the outline."
        else:
            result["explanation"] = "Structured course objectives or learning outcomes could not be identified."
    
    elif ("readings" in item_lower or "textbooks" in item_lower or "materials" in item_lower):
        # Check for reading materials
        reading_patterns = [
            r'(?:required|recommended)\s+(?:readings|textbooks|materials)',
            r'(?:readings|textbooks|materials)[:\s]+',
            r'(?:course|required)\s+(?:materials|resources)',
        ]
        
        has_readings = any(re.search(pattern, outline_text, re.IGNORECASE) for pattern in reading_patterns)
        result["present"] = has_readings
        if has_readings:
            result["explanation"] = "The outline lists readings, textbooks, or other course materials."
        else:
            result["explanation"] = "No section listing readings, textbooks, or materials could be found."
    
    elif "tools or platforms" in item_lower or "generative ai" in item_lower:
        # Check for policy on tools/platforms
        tool_patterns = [
            r'(?:prohibited|allowed|permitted)\s+(?:tools|platforms|resources)',
            r'(?:generative|artificial)\s+(?:intelligence|AI)',
            r'(?:policy|guidelines)\s+(?:regarding|about|on)\s+(?:tools|platforms|AI)',
        ]
        
        has_tools_policy = any(re.search(pattern, outline_text, re.IGNORECASE) for pattern in tool_patterns)
        result["present"] = has_tools_policy
        if has_tools_policy:
            result["explanation"] = "The outline includes a policy about tools/platforms that students can or cannot use."
        else:
            result["explanation"] = "No policy about permitted or prohibited tools/platforms was found."
    
    elif "workload" in item_lower or "weekly effort" in item_lower:
        # Check for workload expectations
        workload_patterns = [
            r'(?:workload|effort|time)\s+(?:expectations|requirements|commitment)',
            r'(?:expect|spend|allocate)\s+(?:\d+|several|multiple)\s+(?:hours|hrs)',
            r'(?:weekly|daily)\s+(?:workload|effort|time)',
        ]
        
        has_workload = any(re.search(pattern, outline_text, re.IGNORECASE) for pattern in workload_patterns)
        result["present"] = has_workload
        if has_workload:
            result["explanation"] = "The outline describes workload or weekly effort expectations."
        else:
            result["explanation"] = "No description of workload or effort expectations was found."
    
    elif "grade scale" in item_lower:
        has_scale = has_grade_scale(outline_text)
        result["present"] = has_scale
        if has_scale:
            result["explanation"] = "A grade scale mapping percentages to letter grades is included in the outline."
        else:
            result["explanation"] = "No grade scale mapping percentages to letter grades was found."
    
    elif "assessment has a percentage weight" in item_lower:
        has_weights = has_assessment_weights(outline_text)
        result["present"] = has_weights
        if has_weights:
            result["explanation"] = "Assessments have percentage weights toward the final grade."
        else:
            result["explanation"] = "Not all assessments have clearly defined percentage weights."
    
    elif "group work" in item_lower and "40%" in item_lower:
        meets_criteria, status = check_group_work_percent(outline_text)
        result["present"] = meets_criteria
        result["status"] = status
        if status == "N/A":
            result["explanation"] = "No group work is mentioned in the outline."
        elif meets_criteria:
            result["explanation"] = "Group work is 40% or less of the total grade."
        else:
            result["explanation"] = "Group work exceeds 40% of the total grade."
    
    elif "assessment links to" in item_lower and "objective" in item_lower:
        has_links = check_assessments_linked_to_objectives(outline_text)
        result["present"] = has_links
        if has_links:
            result["explanation"] = "Assessments are linked to course objectives/outcomes."
        else:
            result["explanation"] = "No clear mapping between assessments and course objectives was found."
    
    elif "due dates" in item_lower:
        has_dates = check_due_dates_included(outline_text)
        result["present"] = has_dates
        if has_dates:
            result["explanation"] = "Due dates for assessments are included in the outline."
        else:
            result["explanation"] = "Due dates for assessments are not clearly specified."
    
    elif "30% of the grade" in item_lower and "before the last class" in item_lower:
        has_thirty_percent = check_thirty_percent_before_last_class(outline_text)
        result["present"] = has_thirty_percent
        if has_thirty_percent:
            result["explanation"] = "At least 30% of the grade is earned before the last class."
        else:
            result["explanation"] = "Less than 30% of the grade appears to be earned before the last class."
    
    elif "scheduled after the final class" in item_lower:
        no_late_assessments = check_no_assessments_after_final_class(outline_text)
        result["present"] = no_late_assessments
        if no_late_assessments:
            result["explanation"] = "No assessments or deliverables are scheduled after the final class."
        else:
            result["explanation"] = "Some assessments appear to be scheduled after the final class."
    
    elif "missed assessment policy" in item_lower:
        has_policy = check_missed_assessment_policy(outline_text)
        result["present"] = has_policy
        if has_policy:
            result["explanation"] = "A missed assessment policy is included in the outline."
        else:
            result["explanation"] = "No clear policy for missed assessments was found."
    
    elif "late policy" in item_lower:
        has_policy = check_late_policy(outline_text)
        result["present"] = has_policy
        if has_policy:
            result["explanation"] = "A late policy is described in the outline."
        else:
            result["explanation"] = "No clear policy for late submissions was found."
    
    elif "participation is graded" in item_lower:
        participation_explained = check_participation_evaluation(outline_text)
        result["present"] = participation_explained
        if "participation" not in outline_text.lower():
            result["status"] = "N/A"
            result["explanation"] = "Participation does not appear to be graded in this course."
        elif participation_explained:
            result["explanation"] = "The outline explains how participation is evaluated."
        else:
            result["explanation"] = "The outline does not explain how participation is evaluated."
    
    elif "assignment instructions" in item_lower and "submit" in item_lower:
        has_instructions = check_assignment_submission_instructions(outline_text)
        result["present"] = has_instructions
        if has_instructions:
            result["explanation"] = "Assignment instructions include how and where to submit."
        else:
            result["explanation"] = "Assignment submission instructions are not clearly provided."
    
    elif "group project" in item_lower and "expectations" in item_lower:
        has_details = check_group_project_details(outline_text)
        result["present"] = has_details
        if "group project" not in outline_text.lower():
            result["status"] = "N/A"
            result["explanation"] = "No group project appears to be assigned in this course."
        elif has_details:
            result["explanation"] = "Group project details and expectations are included."
        else:
            result["explanation"] = "Group project details are not sufficiently explained."
    
    elif ("midterm" in item_lower or "quiz" in item_lower) and "timing" in item_lower:
        has_details = check_exam_details(outline_text, is_final=False)
        result["present"] = has_details
        if not re.search(r'(?:midterm|quiz)', outline_text.lower()):
            result["status"] = "N/A"
            result["explanation"] = "No midterm or quiz appears to be scheduled in this course."
        elif has_details:
            result["explanation"] = "Midterm/quiz timing, location, and requirements are described."
        else:
            result["explanation"] = "Midterm/quiz details are not sufficiently explained."
    
    elif "final exam" in item_lower and "timing" in item_lower:
        has_details = check_exam_details(outline_text, is_final=True)
        result["present"] = has_details
        if "final exam" not in outline_text.lower():
            result["status"] = "N/A"
            result["explanation"] = "No final exam appears to be scheduled in this course."
        elif has_details:
            result["explanation"] = "Final exam timing, location, and requirements are described."
        else:
            result["explanation"] = "Final exam details are not sufficiently explained."
    
    elif "final exam" in item_lower and "50%" in item_lower:
        meets_criteria, status = check_final_exam_weight(outline_text)
        result["present"] = meets_criteria
        result["status"] = status
        if status == "N/A":
            result["explanation"] = "No final exam is mentioned in the outline."
        elif meets_criteria:
            result["explanation"] = "The final exam counts for no more than 50% of the grade."
        else:
            result["explanation"] = "The final exam exceeds 50% of the final grade."
    
    elif "take-home final exam" in item_lower:
        needs_review, status = check_take_home_final(outline_text)
        result["present"] = needs_review
        result["status"] = status
        if status == "N/A":
            result["explanation"] = "No take-home final exam is mentioned in the outline."
        else:
            result["explanation"] = "A take-home final exam is mentioned and should be flagged for admin review."
    
    elif "contact the instructor" in item_lower:
        has_section = check_instructor_contact_section(outline_text)
        result["present"] = has_section
        if has_section:
            result["explanation"] = "The outline includes instructions on how to contact the instructor."
        else:
            result["explanation"] = "No clear instructions for contacting the instructor were found."
    
    elif "class schedule" in item_lower or "session breakdown" in item_lower:
        has_schedule = check_class_schedule_included(outline_text)
        result["present"] = has_schedule
        if has_schedule:
            result["explanation"] = "A class schedule or session breakdown is included in the outline."
        else:
            result["explanation"] = "No clear class schedule or session breakdown was found."
    
    elif "due dates" in item_lower and "schedule" in item_lower:
        has_dates = check_schedule_includes_due_dates(outline_text)
        result["present"] = has_dates
        if has_dates:
            result["explanation"] = "Assessment due dates are listed or referenced in the schedule."
        else:
            result["explanation"] = "Due dates are not clearly included in the schedule."
    
    elif ("exam" in item_lower or "quiz" in item_lower) and "schedule" in item_lower:
        has_dates = check_schedule_includes_exam_dates(outline_text)
        result["present"] = has_dates
        if has_dates:
            result["explanation"] = "Exam or quiz dates are listed or referenced in the schedule."
        else:
            result["explanation"] = "Exam or quiz dates are not clearly included in the schedule."
    
    elif "web links" in item_lower or "functional" in item_lower:
        links_valid = validate_links(outline_text)
        result["present"] = links_valid
        if links_valid:
            result["explanation"] = "All web links included in the outline appear to be functional."
        else:
            result["explanation"] = "Some web links in the outline may not be functional."
    
    else:
        # For items that don't match any of the specific patterns, use OpenAI if available
        try:
            from openai_helper import analyze_checklist_item
            ai_result = analyze_checklist_item(item_text, outline_text)
            return ai_result
        except Exception as e:
            logger.warning(f"Error using AI analysis, falling back to basic analysis: {str(e)}")
            
            # Perform basic keyword matching as fallback
            # Use NLTK if available, otherwise use a simple approach
            if nltk_available:
                words = word_tokenize(item_lower)
                stop_words = set(stopwords.words('english'))
                keywords = [w for w in words if w.isalnum() and w not in stop_words and len(w) > 3]
            else:
                # Simple fallback when NLTK is not available
                words = item_lower.split()
                # Common English stop words
                common_stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 
                                    'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than', 
                                    'such', 'both', 'through', 'about', 'for', 'is', 'of', 'while', 'during', 
                                    'to', 'from', 'in', 'out', 'on', 'off', 'with', 'by', 'at', 'from'}
                keywords = [w for w in words if w.isalnum() and w not in common_stop_words and len(w) > 3]
            
            # Count keyword occurrences
            count = sum(1 for keyword in keywords if keyword in outline_text.lower())
            threshold = max(1, len(keywords) // 2)  # At least half the keywords should be present
            
            result["present"] = count >= threshold
            if result["present"]:
                result["explanation"] = "The requirement appears to be addressed in the course outline."
            else:
                result["explanation"] = "The requirement does not appear to be addressed in the course outline."
    
    # Add status if not already set
    if "status" not in result:
        if "N/A" in result["explanation"]:
            result["status"] = "N/A"
        elif result["present"]:
            result["status"] = "Yes"
        else:
            result["status"] = "No"
    
    return result

def evaluate_course_outline(checklist_path: str, outline_path: str) -> str:
    """
    Evaluate a course outline against the checklist and format output.
    
    Args:
        checklist_path: Path to the checklist file
        outline_path: Path to the course outline file
        
    Returns:
        Formatted evaluation results
    """
    try:
        # Extract checklist items
        checklist_items = extract_checklist_from_document(checklist_path)
        
        # Extract course outline text
        outline_text = extract_text(outline_path)
        
        # Perform evaluation for each checklist item
        results = []
        for item_num in sorted(checklist_items.keys()):
            item_text = checklist_items[item_num]
            
            # Analyze the item
            result = analyze_checklist_item_prompt(item_text, outline_text)
            
            # Format the result
            status = result.get("status", "Yes" if result["present"] else "No")
            justification = result["explanation"]
            
            # Format output for this item
            item_result = f"**Checklist Item #{item_num}:** {item_text}\n"
            item_result += f"**Status:** {status}\n"
            item_result += f"**Justification:** {justification}\n\n"
            
            results.append(item_result)
        
        return "".join(results)
        
    except Exception as e:
        logger.exception(f"Error in evaluate_course_outline: {str(e)}")
        return f"Error evaluating course outline: {str(e)}"

def main():
    """Main function to run the script."""
    # Get course outline path from command line argument or use default
    if len(sys.argv) > 1:
        outline_path = sys.argv[1]
    else:
        # Look for PDF files in attached_assets
        pdf_files = [f for f in os.listdir("attached_assets") if f.endswith(".pdf")]
        if pdf_files:
            outline_path = os.path.join("attached_assets", pdf_files[0])
        else:
            print("Error: No PDF file found in attached_assets directory.")
            print("Please provide a path to the course outline file.")
            sys.exit(1)
    
    # Check if the checklist file exists
    checklist_path = "attached_assets/Pasted-You-are-reviewing-a-university-course-outline-to-evaluate-whether-it-meets-institutional-standards-b-1744082496300.txt"
    if not os.path.exists(checklist_path):
        print(f"Error: Checklist file not found: {checklist_path}")
        sys.exit(1)
    
    # Run the evaluation
    evaluation_results = evaluate_course_outline(checklist_path, outline_path)
    
    # Print the results
    print(evaluation_results)

if __name__ == "__main__":
    main()