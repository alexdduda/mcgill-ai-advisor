from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    # Storing profile as JSON allows flexibility without strict schema changes
    profile_data = Column(JSON, default={}) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Course(Base):
    __tablename__ = "courses"
    
    code = Column(String, primary_key=True, index=True) # e.g. COMP 202
    title = Column(String)
    class_average = Column(Float)
    credits = Column(Integer)
    term = Column(String)
    # Store raw CSV data or extra fields here
    meta_data = Column(JSON, default={})