import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, EmailStr, Field

# Token expiration time
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(min_length=6, max_length=128)
    password_confirm: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response (no password)."""
    id: int
    created_at: datetime


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: int
    email: str
