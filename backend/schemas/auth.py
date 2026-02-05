"""
Pydantic schemas cho Authentication
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ============================================
# Request Schemas
# ============================================
class RegisterRequest(BaseModel):
    """Schema cho request đăng ký"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=72, description="Mật khẩu (tối đa 72 ký tự cho bcrypt)")
    full_name: Optional[str] = Field(None, max_length=255)
    student_id: str = Field(..., min_length=8, max_length=8)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "john_doe",
                "password": "secure_password123",
                "full_name": "John Doe",
                "student_id": "12345678"
            }
        }


class LoginRequest(BaseModel):
    """Schema cho request đăng nhập"""
    email: EmailStr
    password: str = Field(..., max_length=72, description="Mật khẩu (tối đa 72 ký tự cho bcrypt)")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "secure_password123"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Schema cho request làm mới access token"""
    refresh_token: str

    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGc..."
            }
        }


class LogoutRequest(BaseModel):
    """Schema cho request logout"""
    access_token: str
    refresh_token: str

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGc...",
                "refresh_token": "eyJhbGc..."
            }
        }


# ============================================
# Response Schemas
# ============================================
class TokenResponse(BaseModel):
    """Schema cho token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGc...",
                "refresh_token": "eyJhbGc...",
                "token_type": "bearer",
                "expires_in": 900
            }
        }


class AccessTokenResponse(BaseModel):
    """Schema cho access token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGc...",
                "token_type": "bearer",
                "expires_in": 900
            }
        }


class MessageResponse(BaseModel):
    """Schema cho message response"""
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation successful"
            }
        }
