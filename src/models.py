from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: Literal["student", "faculty", "admin"]

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class FacultyDetailResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime
    uploaded_docs_count: int

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

class CourseCreate(BaseModel):
    code: str
    title: str
    semester: int

class CourseUpdate(BaseModel):
    title: str
    semester: int

class CourseResponse(BaseModel):
    code: str
    title: str
    semester: int
    faculty_id: Optional[UUID] = None

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    course_id: str
    doc_type: str
    created_at: datetime

class ChatQueryRequest(BaseModel):
    course_code: str
    query: str
    session_id: Optional[UUID] = None
    mode: Literal["ask", "generate_exam"] = "ask"

class ChatSessionResponse(BaseModel):
    id: UUID
    course_code: str
    title: str
    created_at: datetime
    
class ClassificationResponse(BaseModel):
    suggested_course: str
    suggested_type: str
    confidence: float
    rationale: str