# Course Outline Analysis API

This API allows you to analyze a course outline against 26 standard checklist items based on University of Calgary requirements.

## API Endpoint

```
POST /api/analyze-course-outline
```

## Request Formats

The API accepts two formats for requests:

### 1. JSON Request with Document Text

```bash
curl -X POST http://localhost:5000/api/analyze-course-outline \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "COURSE OUTLINE\nPSYC 201 - Introduction to Psychology\n\nInstructor: Dr. John Smith\nEmail: john.smith@ucalgary.ca\n..."
  }'
```

### 2. Multipart Form Data with File Upload

```bash
curl -X POST http://localhost:5000/api/analyze-course-outline \
  -F "outline=@/path/to/course_outline.pdf"
```

## Response Format

The API returns a JSON array of 26 objects, one for each checklist item. Each object has the following structure:

```json
[
  {
    "present": true,
    "confidence": 0.95,
    "explanation": "Instructor email john.smith@ucalgary.ca is included and contains the domain ucalgary.ca",
    "evidence": "Instructor: Dr. John Smith\nEmail: john.smith@ucalgary.ca",
    "method": "ai_general_analysis"
  },
  {
    "present": false,
    "confidence": 0.8,
    "explanation": "No policy regarding prohibited materials or tools was found in the document",
    "evidence": "",
    "method": "ai_general_analysis"
  },
  ...
]
```

## Response Fields

Each object in the response array contains:

- `present`: Boolean indicating whether the checklist item is present in the course outline
- `confidence`: Number between 0.0 and 1.0 indicating the confidence in the assessment
- `explanation`: Brief explanation (under 150 characters) of why the item was marked as present or not
- `evidence`: Direct quote from the outline supporting the assessment, or empty string if not found
- `method`: Always set to "ai_general_analysis"

## Error Responses

The API returns appropriate error messages with HTTP status codes when issues occur:

```json
{
  "error": "No outline file or document text provided"
}
```

## Checklist Items

The API analyzes the course outline against these 26 hardcoded checklist items:

1. Instructor Email: Acceptable email must end with "ucalgary.ca"
2. Course Objectives: Listed and numbered
3. Textbooks & Other Course Material: Any readings or materials listed
4. Prohibited Materials: Information about prohibited platforms, resources, and tools
5. Course Workload: Section describing workload expectations
6. Grading Scale: Table mapping percentages to letter grades
7. Grade Distribution Table: Weights assigned to assessments
8. Group Work Weight: If included, doesn't exceed 40% of final grade
9. Assessment-Objectives Alignment: Assessments linked to course objectives
10. Due Dates in Grade Table: Due dates for assignments and examinations
11. 30% Before Last Class: At least 30% of grade earned before last day
12. No Post-Term Assignments: No assignments due after last day of classes
13. Missed Assessment Policy: Policy for missed assessments
14. Late Submission Policy: Explains penalties for late submissions
15. Participation Grading Criteria: Details on how participation is evaluated
16. Assignment Submission Instructions: How and where to submit work
17. Group Project Guidelines: Details and first group work deadline
18. Midterm/Quiz Information: Timing, location, format, permitted materials
19. Final Exam Details: Information on timing, location, modality
20. Final Exam Weight Limit: Final exam counts for less than 50% of grade
21. Take-Home Final Identification: Clearly identified if present
22. Instructor Contact Guidelines: Guidelines for communication
23. Class Schedule Inclusion: Weekly topics and activities
24. Due Dates in Schedule: Assignment due dates referenced
25. Exam Dates in Schedule: Quiz, test, or exam dates
26. Functional Web Links: All links valid and working