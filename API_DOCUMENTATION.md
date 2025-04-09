# Course Outline Compliance Checker API

This API analyzes course outlines against 26 institutional compliance requirements, providing detailed feedback on whether each requirement is met, along with supporting evidence from the document.

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
    "method": "ai_general_analysis"
  },
  ...
]
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `present` | boolean | Whether the requirement is met (true) or not (false) |
| `confidence` | float | Confidence level (0.0-1.0) in the determination |
| `explanation` | string | Brief explanation (<150 chars) of the analysis |
| `evidence` | string | Direct quote from the document supporting the determination, or empty string if not found |
| `method` | string | Always "ai_general_analysis" |

## Checklist Items

The API evaluates the following 26 institutional requirements:

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
    "method": "ai_general_analysis"
  },
  {
    "present": true,
    "confidence": 0.9,
    "explanation": "Course objectives are listed and numbered.",
    "evidence": "Learning Objectives:\n1. Understand basic psychological theories and concepts\n2. Apply critical thinking to psychological research",
    "method": "ai_general_analysis"
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