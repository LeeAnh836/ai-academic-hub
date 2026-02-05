"""
Pydantic schemas cho Group
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================
# Request Schemas
# ============================================
class GroupCreateRequest(BaseModel):
    """Schema cho request tạo group"""
    group_name: str = Field(..., min_length=1, max_length=255)
    group_type: str = Field(default="public", pattern="^(public|private)$")
    description: Optional[str] = None
    is_public: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "Java Developers",
                "group_type": "public",
                "description": "A group for Java developers",
                "is_public": True
            }
        }


class GroupUpdateRequest(BaseModel):
    """Schema cho request cập nhật group"""
    group_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_public: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "Advanced Java Developers",
                "description": "For advanced Java developers only",
                "is_public": False
            }
        }


class GroupMemberAddRequest(BaseModel):
    """Schema cho request thêm member vào group"""
    user_id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class GroupMessageCreateRequest(BaseModel):
    """Schema cho request gửi tin nhắn group"""
    group_id: UUID
    message_type: str = Field(default="text", pattern="^(text|file|image)$")
    content: str = Field(..., min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "550e8400-e29b-41d4-a716-446655440000",
                "message_type": "text",
                "content": "Hello everyone!"
            }
        }


class GroupFileShareRequest(BaseModel):
    """Schema cho request chia sẻ file trong group"""
    group_id: UUID
    document_id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": "550e8400-e29b-41d4-a716-446655440001"
            }
        }


# ============================================
# Response Schemas
# ============================================
class GroupMemberResponse(BaseModel):
    """Schema cho response group member"""
    id: UUID
    group_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class GroupMessageResponse(BaseModel):
    """Schema cho response group message"""
    id: UUID
    group_id: UUID
    user_id: UUID
    message_type: str
    content: str
    is_pinned: bool
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "group_id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "message_type": "text",
                "content": "Hello everyone!",
                "is_pinned": False,
                "created_at": "2024-02-01T10:00:00"
            }
        }


class GroupFileResponse(BaseModel):
    """Schema cho response group file"""
    id: UUID
    group_id: UUID
    document_id: UUID
    uploaded_by_user_id: Optional[UUID]
    shared_at: datetime

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    """Schema cho response group"""
    id: UUID
    group_name: str
    group_type: str
    is_public: bool
    join_code: Optional[str]
    description: Optional[str]
    member_count: int
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "group_name": "Java Developers",
                "group_type": "public",
                "is_public": True,
                "join_code": "ABC123DEF",
                "description": "A group for Java developers",
                "member_count": 10,
                "created_by": "550e8400-e29b-41d4-a716-446655440001",
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T10:00:00"
            }
        }


class GroupDetailResponse(GroupResponse):
    """Schema cho response chi tiết group"""
    members: Optional[List[GroupMemberResponse]] = []
    messages: Optional[List[GroupMessageResponse]] = []
    files: Optional[List[GroupFileResponse]] = []

    class Config:
        from_attributes = True
