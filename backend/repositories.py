# backend/repositories.py
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, ChatMessage, Course
from typing import List, Optional
import logging
import csv
import os

logger = logging.getLogger(__name__)

class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_course(self, course_code: str) -> Optional[Course]:
        result = await self.db.execute(select(Course).where(Course.code == course_code))
        return result.scalars().first()

    async def get_all_courses(self) -> List[Course]:
        result = await self.db.execute(select(Course))
        return result.scalars().all()
    
    async def seed_from_csv(self, csv_path: str):
        """
        Robust CSV parser specifically for the ClassAverageCrowdSourcing.csv format.
        """
        if not os.path.exists(csv_path):
            logger.error(f"CSV file not found: {csv_path}")
            return

        logger.info("🗑️  Clearing old course data...")
        await self.db.execute(delete(Course))
        
        logger.info(f"📖 Reading {csv_path}...")
        
        courses_added = 0
        
        # We use a manual parsing approach because the headers are messy
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            
            for row in reader:
                # Skip empty rows or short rows
                if not row or len(row) < 5:
                    continue
                
                # valid rows look like: 
                # ['ACCT351-201601', 'ACCT351', 'W2016', 'B', '3.00', '3.00', '#REF!']
                
                course_code = row[1].strip().upper()
                
                # Basic validation: Course code should look like 'ACCT351'
                if len(course_code) < 6 or not course_code[:4].isalpha():
                    continue

                try:
                    # Column 4 is the GPA (e.g., '3.00')
                    avg_grade = float(row[4])
                    credits = int(float(row[5])) if row[5] else 3
                    term = row[2]
                except ValueError:
                    continue # Skip header rows or invalid numbers

                # Check if we already added this course in this session
                # (The CSV has duplicates for different terms, we'll average them)
                existing_course = await self.get_course(course_code)
                
                if existing_course:
                    # Update running average
                    # (This is a simple average of averages)
                    new_avg = (existing_course.class_average + avg_grade) / 2
                    existing_course.class_average = round(new_avg, 2)
                    # Update term to most recent (simple logic)
                    if term > existing_course.term:
                        existing_course.term = term
                else:
                    # Create new course
                    course = Course(
                        code=course_code,
                        title=f"{course_code} (Crowdsourced)", # CSV doesn't have titles, so we use code
                        class_average=avg_grade,
                        credits=credits,
                        term=term,
                        meta_data={} 
                    )
                    self.db.add(course)
                    courses_added += 1
        
        await self.db.commit()
        logger.info(f"✅ Successfully seeded {courses_added} unique courses from CSV.")

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_user(self, username: str) -> User:
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if not user:
            user = User(username=username, profile_data={})
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def update_profile(self, username: str, profile_data: dict):
        user = await self.get_or_create_user(username)
        # Merge existing profile with new data
        current_data = dict(user.profile_data) if user.profile_data else {}
        current_data.update(profile_data)
        user.profile_data = current_data
        
        self.db.add(user)
        await self.db.commit()
        return user

class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def add_message(self, user_id: int, role: str, content: str):
        msg = ChatMessage(user_id=user_id, role=role, content=content)
        self.db.add(msg)
        await self.db.commit()
        
    async def get_history(self, user_id: int, limit: int = 10):
        stmt = select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.timestamp.desc()).limit(limit)
        result = await self.db.execute(stmt)
        # Return reversed so it's chronological (oldest -> newest)
        return list(reversed(result.scalars().all()))