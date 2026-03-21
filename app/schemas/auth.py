from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "employee"
