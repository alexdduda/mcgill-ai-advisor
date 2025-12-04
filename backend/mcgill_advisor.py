import pandas as pd
import logging
from typing import Dict, List, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class DifficultyLevel(Enum):
    EASY = 1
    MODERATE = 2  
    CHALLENGING = 3
    VERY_HARD = 4

@dataclass
class CourseRecommendation:
    course_code: str
    predicted_grade: float
    difficulty_score: float
    reasons: List[str]

class McGillAdvisorAI:
    """
    Stateless Advisory Logic.
    Now requires the student_profile and course_data to be passed in.
    """
    def __init__(self):
        pass # No state initialization needed

    def predict_student_grade(self, course_row: dict, student_profile: dict) -> Tuple[float, float]:
        """
        Predict student's likely grade.
        course_row: Dict containing 'class_average', 'code', etc.
        student_profile: Dict containing 'current_gpa', 'strong_subjects', etc.
        """
        base_average = course_row.get('class_average', 3.0)
        if not base_average or pd.isna(base_average):
            return 0.0, 0.0
            
        predicted_grade = base_average
        confidence = 0.3
        
        if student_profile:
            current_gpa = student_profile.get('current_gpa', 3.0)
            # Heuristic: Pull grade towards student's GPA
            predicted_grade = (base_average + current_gpa) / 2
            confidence += 0.2
            
            # Subject strength adjustment
            course_code = course_row.get('code', '')
            subject = course_code[:4] if len(course_code) >= 4 else ""
            if subject in student_profile.get('strong_subjects', []):
                predicted_grade += 0.2
                confidence += 0.1
                
        return min(4.0, max(0.0, predicted_grade)), confidence

    def calculate_difficulty(self, class_average: float) -> float:
        if not class_average: return 2.5
        if class_average >= 3.7: return 1.5
        elif class_average >= 3.3: return 2.0
        elif class_average >= 3.0: return 2.5
        elif class_average >= 2.7: return 3.0
        else: return 3.5