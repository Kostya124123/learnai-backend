from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CourseOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    generated_at: Optional[datetime] = None
    module_count: int = 0
    document_id: Optional[int] = None

    model_config = {"from_attributes": True}


class CourseModuleOut(BaseModel):
    id: int
    course_id: int
    module_type: str
    order_index: int
    title: str
    content: str

    model_config = {"from_attributes": True}


class TestQuestionOut(BaseModel):
    id: int
    module_id: int
    question: str
    options: List[str]
    points: int

    model_config = {"from_attributes": True}


class TestAttemptIn(BaseModel):
    answer: str


class TestAttemptOut(BaseModel):
    test_id: int
    answer: str
    is_correct: bool
    score: int
    correct_answer: str
    explanation: str = ""

    model_config = {"from_attributes": True}


class EnrollmentOut(BaseModel):
    id: int
    course_id: int
    course_title: str
    enrolled_at: Optional[datetime] = None
    status: str
    progress_pct: float
    last_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ProgressUpdate(BaseModel):
    progress_pct: float


class GenerateCourseIn(BaseModel):
    document_id: Optional[int] = None
    title: str


class ChatIn(BaseModel):
    question: str


class ChatOut(BaseModel):
    answer: str
    source: str = ""


class ChatMessageOut(BaseModel):
    id: int
    role: str = "assistant"
    content: str
    source: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AnalyticsOut(BaseModel):
    total_enrolled: int
    avg_score: float
    courses_generated: int
    incomplete_count: int
    weak_topics: List[dict]
    recent_activity: List[dict]


class DocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    uploaded_at: Optional[datetime] = None
    chunk_count: int

    model_config = {"from_attributes": True}
