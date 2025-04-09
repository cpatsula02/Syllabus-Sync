import unittest
import tempfile
import json
import os
from app import app

class TestAPIAnalyze(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.tempdir = tempfile.mkdtemp()
        app.config['UPLOAD_FOLDER'] = self.tempdir
        
    def test_analyze_with_document_text(self):
        """Test the API endpoint with document text in JSON body"""
        # Create a simple sample course outline text
        outline_text = """
        COURSE OUTLINE
        PSYC 201 - Introduction to Psychology
        
        Instructor: Dr. John Smith
        Email: john.smith@ucalgary.ca
        Office: EDT 123
        Office Hours: Mondays 2-4pm or by appointment
        
        Course Description:
        This course provides an introduction to the scientific study of behavior and mind.
        
        Learning Objectives:
        1. Understand basic psychological theories and concepts
        2. Apply critical thinking to psychological research
        3. Develop scientific writing and communication skills
        
        Required Textbook:
        Introduction to Psychology, 2nd Edition, by James Williams
        
        Grading Scale:
        A+ (90-100%)
        A (85-89%)
        A- (80-84%)
        B+ (75-79%)
        B (70-74%)
        B- (65-69%)
        C+ (60-64%)
        C (55-59%)
        C- (50-54%)
        D+ (45-49%)
        D (40-44%)
        F (0-39%)
        
        Evaluation:
        Midterm Examination: 30% (October 15, in class)
        Research Paper: 25% (Due November 10)
        Final Examination: 35% (December 15, location TBA)
        Participation: 10% (Throughout semester)
        
        Course Schedule:
        Week 1: Introduction to Psychology
        Week 2: Research Methods
        Week 3: Biological Psychology
        Week 4: Sensation and Perception
        Week 5: Learning
        Week 6: Memory
        Week 7: Midterm Exam (October 15)
        Week 8: Cognition and Intelligence
        Week 9: Human Development
        Week 10: Personality
        Week 11: Social Psychology
        Week 12: Psychological Disorders
        Week 13: Treatment Approaches
        Week 14: Review and Final Thoughts
        
        Late Policy:
        Late assignments will be penalized 5% per day. No assignments will be accepted more than 7 days late.
        
        Missed Examinations:
        If you miss an examination due to illness or emergency, contact the instructor within 48 hours to arrange a makeup.
        
        Academic Integrity:
        All work submitted must be your own. Plagiarism and cheating will result in a grade of F for the assignment or course.
        
        Additional Resources:
        Visit the course website at https://d2l.ucalgary.ca for additional materials and updates.
        """
        
        # Make request to API
        response = self.client.post(
            '/api/analyze-course-outline',
            data=json.dumps({'document_text': outline_text}),
            content_type='application/json'
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Validate response format
        self.assertTrue(isinstance(data, list))
        self.assertEqual(len(data), 26)  # Should have exactly 26 items
        
        # Validate structure of first item
        first_item = data[0]
        self.assertIn('present', first_item)
        self.assertIn('confidence', first_item)
        self.assertIn('explanation', first_item)
        self.assertIn('evidence', first_item)
        self.assertIn('method', first_item)
        
        # Check that booleans are proper Python booleans
        self.assertTrue(isinstance(first_item['present'], bool))
        
        # Check that confidence is a float between 0 and 1
        self.assertTrue(0 <= first_item['confidence'] <= 1)
        
        # Check method value
        self.assertEqual(first_item['method'], 'ai_general_analysis')
    
    def test_analyze_with_file_upload(self):
        """Test the API endpoint with file upload"""
        # Create a temporary file with sample content
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"""
            COURSE OUTLINE
            PSYC 201 - Introduction to Psychology
            
            Instructor: Dr. Jane Doe
            Email: jane.doe@ucalgary.ca
            Office: Science B 123
            Office Hours: Tuesdays and Thursdays 1-3pm
            
            Course Description:
            This course explores the fundamentals of psychology as a science.
            
            Learning Outcomes:
            1. Describe major psychological theories
            2. Evaluate psychological research methods
            3. Apply psychological concepts to real-world situations
            
            Required Materials:
            - Psychology: The Science of Mind and Behavior, 3rd Edition
            - Access to D2L course website
            
            Grade Distribution:
            Midterm Exam: 25% (October 20)
            Research Assignment: 30% (Due November 15)
            Final Exam: 35% (During exam period)
            Participation: 10% (Throughout term)
            
            Grading Scale:
            A+ (95-100%)
            A (90-94%)
            A- (85-89%)
            B+ (80-84%)
            B (75-79%)
            B- (70-74%)
            C+ (65-69%)
            C (60-64%)
            C- (55-59%)
            D+ (50-54%)
            D (45-49%)
            F (0-44%)
            
            Course Schedule:
            Week 1: Course Introduction
            Week 7: Midterm Examination
            Week 14: Final Review
            
            Late Policy:
            Assignments submitted late will receive a 10% penalty per day.
            
            Missed Exam Policy:
            Students who miss exams due to documented illness may write a makeup exam.
            
            Academic Integrity:
            Students are expected to comply with university policies on academic integrity.
            
            Course Website:
            https://d2l.ucalgary.ca/psychology201
            """.encode('utf-8'))
            temp_file_path = f.name
        
        try:
            with open(temp_file_path, 'rb') as f:
                response = self.client.post(
                    '/api/analyze-course-outline',
                    data={
                        'outline': (f, 'course_outline.txt')
                    },
                    content_type='multipart/form-data'
                )
            
            # Check response
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            
            # Validate response format
            self.assertTrue(isinstance(data, list))
            self.assertEqual(len(data), 26)  # Should have exactly 26 items
            
        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    def test_analyze_with_no_data(self):
        """Test the API endpoint with no data provided"""
        response = self.client.post('/api/analyze-course-outline')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def tearDown(self):
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.tempdir)

if __name__ == '__main__':
    unittest.main()