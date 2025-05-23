# Course Outline Compliance Checker API

This API analyzes course outlines against 26 institutional compliance requirements using OpenAI's advanced language understanding capabilities, providing detailed feedback on whether each requirement is met, along with supporting evidence from the document.

## Implementation Details

The API uses the OpenAI Chat Completions API to perform comprehensive contextual analysis of the document against all 26 checklist items. The analysis is based entirely on contextual understanding of the document, NOT pattern matching - the system looks for concepts and requirements rather than specific keywords or patterns.

### Enhanced Anti-Pattern Matching Directives

The system has been explicitly designed to avoid relying on simplistic pattern matching by incorporating six critical directives:

1. Do not rely on exact keyword matches or specific section headers
2. Never assume presence based on headers alone
3. Analyze the actual content for compliance, not just section titles
4. Evaluate whether the substance/meaning of each checklist item is present, regardless of terminology
5. Verify that the content substantially fulfills the requirement's criteria in a meaningful way
6. Focus on compliance with the requirement's purpose, not just matching terminology

### Triple-Checking Process

A unique triple-checking process is implemented for each checklist item:
1. First pass: Initial contextual scan focusing on obvious mentions and relevant sections
2. Second pass: Deeper analysis looking for implicit, indirect or related information
3. Third pass: Final verification and critical evaluation of the evidence found

Only after all three passes does the system finalize its determination and confidence level, with each result marked with a "triple_checked" field set to true.

### Enhanced Automatic Second-Chance Analysis with API Failure Recovery

The system implements an intelligent second-chance analysis with robust retry mechanisms for items that initially fail, with special handling for API failures:

1. After the initial analysis, the system identifies any failed items with errors, API failures, or missing information
2. A focused, item-specific analysis is performed for each failed item with a more tailored prompt, including the original error
3. Each second-chance analysis includes multiple retry attempts (up to 3) with increased timeouts to ensure completion
4. Advanced JSON validation and type conversion ensure consistent output formats even with varying API responses
5. Results from the second-chance analysis are clearly marked with a prefix in the explanation field
6. The system never reports an API failure as a missing/present item - it always attempts to recover through retries
7. If all retry attempts fail, a structured placeholder result indicates the need for manual review
8. All second-chance analyses are logged for transparency and tracked with the "second_chance" boolean field

To ensure reliable performance and prevent timeouts, the implementation:

1. Processes checklist items in small batches (3 items at a time) to optimize API response times
2. Uses GPT-3.5-Turbo with enhanced prompts for contextual understanding and efficient analysis of each batch
3. Implements robust error handling to ensure the API always returns properly formatted responses
4. Has extended timeouts (120 seconds per batch, 600 seconds total) and enhanced retry logic (3 attempts) to handle API stability issues
5. Supports both plain text input and document file uploads (PDF, DOCX)

The API is designed for scalability and can handle documents of various sizes and complexity while maintaining consistent response times.

## API Endpoint

```
POST /api/analyze-course-outline
```

## Request Format

The API accepts requests in two formats:

### 1. JSON Format

```
Content-Type: application/json

{
  "document_text": "Full text content of the course outline document..."
}
```

### 2. Multipart Form Format

```
Content-Type: multipart/form-data

outline: [File Upload]
```

## Response Format

The API returns a JSON array with 26 items, each corresponding to one of the institutional requirements. Each item has the following structure:

```json
[
  {
    "present": true|false,
    "confidence": 0.0-1.0,
    "explanation": "Brief explanation of why the requirement is met or not",
    "evidence": "Direct quote from the document supporting the determination",
    "method": "ai_general_analysis",
    "triple_checked": true,
    "second_chance": true|false
  },
  ...
]
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether the requirement is met (true) or not (false) |
| `confidence` | float | Confidence level (0.0-1.0) in the determination |
| `explanation` | string | Brief explanation (<150 chars) of the analysis. If from second-chance analysis, prefixed with "[2nd Analysis]" |
| `evidence` | string | Direct quote from the document supporting the determination, or empty string if not found |
| `method` | string | Always "ai_general_analysis" |
| `triple_checked` | boolean | Always true, indicates the item was analyzed using the triple-checking process |
| `second_chance` | boolean | Whether the result came from a second-chance analysis after an initial failure |

## Checklist Items

The API evaluates the following 26 institutional requirements, using detailed descriptions from enhanced_checklist.txt for more accurate analysis:

1. **Instructor Email**: Does the outline include the instructor's email? An acceptable email must end with "ucalgary.ca".
2. **Course Objectives**: Are the course objectives listed and numbered?
3. **Textbooks & Other Course Material**: Are any textbooks, readings, and additional course materials listed?
4. **Prohibited Materials**: Check for information that details any prohibited platforms, resources, and tools that cannot be used.
5. **Course Workload**: Is there a course workload section?
6. **Grading Scale**: Does the course outline include the Grade Scale header and a table mapping percentages to letter grades?
7. **Grade Distribution Table**: Does the course outline include a Grade Distribution statement with weights assigned to assessments?
8. **Group Work Weight**: If group work is included, verify it doesn't exceed 40% of the overall final grade.
9. **Assessment-Objectives Alignment**: Check that assessments indicate which course objectives each assessment measures.
10. **Due Dates in Grade Table**: Does the grade distribution table include due dates for all assignments and examinations?
11. **30% Before Last Class**: Will students receive AT LEAST 30% of their final grade before the last day of classes?
12. **No Post-Term Assignments**: Are there any assignments due after the last day of classes?
13. **Missed Assessment Policy**: Does the outline have a missed assessment policy section?
14. **Late Submission Policy**: Does the outline have a Late Policy section that explains penalties for late submissions?
15. **Participation Grading Criteria**: If class participation is listed, are details provided on how it's evaluated?
16. **Assignment Submission Instructions**: Are assignment details included with instructions on how and where to submit work?
17. **Group Project Guidelines**: If a group project is listed, are details provided including the first group work deadline?
18. **Midterm/Quiz Information**: For any midterms or quizzes, is information provided about timing, location, format, and permitted materials?
19. **Final Exam Details**: If a Final Exam is listed, does the outline include information on timing, location, modality, and permitted materials?
20. **Final Exam Weight Limit**: Does the Final Exam count for LESS THAN 50% of the final grade?
21. **Take-Home Final Identification**: If there is a Take-Home Final Examination, is it clearly identified?
22. **Instructor Contact Guidelines**: Is the "Contacting Your Instructor" section included with guidelines for communication?
23. **Class Schedule Inclusion**: Is there a Class Schedule and Topics section showing weekly topics and activities?
24. **Due Dates in Schedule**: Does the Class Schedule include or reference assignment due dates?
25. **Exam Dates in Schedule**: Does the Class Schedule include quiz, test, or exam dates?
26. **Functional Web Links**: Are all links in the outline valid and working?

## Example Usage

### Example Request

```bash
curl -X POST http://localhost:5000/api/analyze-course-outline \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "COURSE OUTLINE\nPSYC 201 - Introduction to Psychology\n\nInstructor: Dr. John Smith\nEmail: john.smith@ucalgary.ca\n..."
  }'
```

### Example Response

```json
[
  {
    "present": true,
    "confidence": 1.0,
    "explanation": "Instructor's email is provided and ends with 'ucalgary.ca'.",
    "evidence": "Email: john.smith@ucalgary.ca",
    "method": "ai_general_analysis",
    "triple_checked": true,
    "second_chance": false
  },
  {
    "present": true,
    "confidence": 0.9,
    "explanation": "Course objectives are listed and numbered.",
    "evidence": "Learning Objectives:\n1. Understand basic psychological theories and concepts\n2. Apply critical thinking to psychological research",
    "method": "ai_general_analysis",
    "triple_checked": true,
    "second_chance": false
  },
  {
    "present": false,
    "confidence": 0.85,
    "explanation": "[2nd Analysis] Group projects are mentioned but documentation lacks specific guidelines and first deadline information.",
    "evidence": "Group Project: Students will work in groups of 4-5 on a research project.",
    "method": "ai_general_analysis",
    "triple_checked": true,
    "second_chance": true
  },
  ...
]
```

## Error Responses

| Status Code | Response | Description |
|-------------|----------|-------------|
| 400 | `{"error": "No outline file or document text provided"}` | Missing required input |
| 400 | `{"error": "Empty document text"}` | Document text is empty |
| 413 | `{"error": "File size exceeds the maximum limit (16MB)"}` | Uploaded file too large |
| 500 | `{"error": "Error message"}` | Server error during processing |