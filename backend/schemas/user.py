"""
Pydantic schemas cho User
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# ============================================
# Request Schemas
# ============================================
class UserUpdateRequest(BaseModel):
    """Schema cho request cập nhật user - CHỈ cho phép sửa full_name"""
    full_name: Optional[str] = Field(None, max_length=255, description="Họ tên người dùng")
    # avatar_url: Optional[str] = None  # TODO: Thêm sau này
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "Nguyễn Văn A"
            }
        }


class UserSettingsUpdateRequest(BaseModel):
    """Schema cho request cập nhật cài đặt user"""
    theme: Optional[str] = Field(None, max_length=20)
    language: Optional[str] = Field(None, max_length=10)
    notifications_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "theme": "dark",
                "language": "vi",
                "notifications_enabled": True,
                "email_notifications": True,
                "two_factor_enabled": False
            }
        }


# ============================================
# Response Schemas
# ============================================
class UserSettingsResponse(BaseModel):
    """Schema cho response cài đặt user"""
    user_id: UUID
    theme: str
    language: str
    notifications_enabled: bool
    email_notifications: bool
    two_factor_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "theme": "light",
                "language": "en",
                "notifications_enabled": True,
                "email_notifications": True,
                "two_factor_enabled": False,
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T10:00:00"
            }
        }


class UserResponse(BaseModel):
    """Schema cho response user"""
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    role: str
    student_id: str
    is_verified: bool
    email_verified_at: Optional[datetime]
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "username": "john_doe",
                "full_name": "John Doe",
                "role": "user",
                "student_id": "12345678",
                "is_verified": True,
                "email_verified_at": "2024-02-01T10:00:00",
                "is_active": True,
                "last_login_at": "2024-02-01T15:30:00",
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T10:00:00"
            }
        }


class UserDetailResponse(UserResponse):
    """Schema cho response chi tiết user (với settings)"""
    settings: Optional[UserSettingsResponse] = None

    class Config:
        from_attributes = True
