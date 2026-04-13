from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, JSON, Boolean, func
from app.core.database import Base

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="published")
    generated_at = Column(DateTime, server_default=func.now())

class CourseModule(Base):
    __tablename__ = "course_modules"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    module_type = Column(String, nullable=False)
    order_index = Column(Integer, default=0)
    title = Column(String, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

class TestQuestion(Base):
    __tablename__ = "tests"
    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("course_modules.id"), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct_answer = Column(String, nullable=False)
    points = Column(Integer, default=10)

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime, server_default=func.now())
    status = Column(String, default="active")
    progress_pct = Column(Float, default=0.0)
    last_score = Column(Float, nullable=True)

class TestAttempt(Base):
    __tablename__ = "test_attempts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    answer = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    attempted_at = Column(DateTime, server_default=func.now())

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class CaseAnswer(Base):
    __tablename__ = "case_answers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module_id = Column(Integer, ForeignKey("course_modules.id"), nullable=False)
    answer = Column(Text, nullable=False)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
