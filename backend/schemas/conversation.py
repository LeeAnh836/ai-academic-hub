"""
Pydantic schemas cho Direct Message (Conversation)
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================
# Request Schemas
# ============================================
class DirectMessageCreateRequest(BaseModel):
    """Schema cho request gửi tin nhắn trực tiếp"""
    receiver_id: UUID
    content: str = Field(..., min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "receiver_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hi, how are you?"
            }
        }


class ConversationCreateRequest(BaseModel):
    """Schema cho request tạo conversation"""
    participant_2_id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "participant_2_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


# ============================================
# Response Schemas
# ============================================
class DirectMessageResponse(BaseModel):
    """Schema cho response direct message"""
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
                "sender_id": "550e8400-e29b-41d4-a716-446655440002",
                "receiver_id": "550e8400-e29b-41d4-a716-446655440003",
                "content": "Hi, how are you?",
                "is_read": True,
                "created_at": "2024-02-01T10:00:00"
            }
        }


class ConversationResponse(BaseModel):
    """Schema cho response conversation"""
    id: UUID
    participant_1: UUID
    participant_2: UUID
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "participant_1": "550e8400-e29b-41d4-a716-446655440001",
                "participant_2": "550e8400-e29b-41d4-a716-446655440002",
                "last_message_at": "2024-02-01T15:30:00",
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T15:30:00"
            }
        }


class ConversationDetailResponse(ConversationResponse):
    """Schema cho response chi tiết conversation"""
    messages: Optional[List[DirectMessageResponse]] = []

    class Config:
        from_attributes = True
