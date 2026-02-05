"""
Pydantic schemas cho Chat
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal


# ============================================
# Request Schemas
# ============================================
class ChatSessionCreateRequest(BaseModel):
    """Schema cho request tạo chat session"""
    title: Optional[str] = Field(None, max_length=255)
    session_type: str = Field(default="general", pattern="^(general|document_qa)$")
    context_documents: Optional[List[UUID]] = []
    model_name: str = Field(default="gpt-3.5-turbo")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Java Learning Session",
                "session_type": "document_qa",
                "context_documents": ["550e8400-e29b-41d4-a716-446655440000"],
                "model_name": "gpt-4"
            }
        }


class ChatMessageCreateRequest(BaseModel):
    """Schema cho request gửi tin nhắn chat"""
    session_id: UUID
    content: str = Field(..., min_length=1)
    retrieved_chunks: Optional[List[UUID]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "How to implement Java generics?",
                "retrieved_chunks": ["550e8400-e29b-41d4-a716-446655440001"]
            }
        }


class MessageFeedbackRequest(BaseModel):
    """Schema cho request feedback tin nhắn"""
    message_id: UUID
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_helpful: Optional[str] = Field(None, pattern="^(helpful|not_helpful)$")
    comment: Optional[str] = None
    feedback_type: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "rating": 5,
                "is_helpful": "helpful",
                "comment": "Very helpful response",
                "feedback_type": "positive"
            }
        }


# ============================================
# Response Schemas
# ============================================
class MessageFeedbackResponse(BaseModel):
    """Schema cho response message feedback"""
    id: UUID
    message_id: UUID
    rating: Optional[int]
    is_helpful: Optional[str]
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    """Schema cho response chat message"""
    id: UUID
    session_id: UUID
    user_id: UUID
    role: str
    content: str
    retrieved_chunks: List[UUID]
    total_tokens: int
    confidence_score: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "session_id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "role": "user",
                "content": "How to implement Java generics?",
                "retrieved_chunks": ["550e8400-e29b-41d4-a716-446655440003"],
                "total_tokens": 45,
                "confidence_score": 0.95,
                "created_at": "2024-02-01T10:00:00"
            }
        }


class ChatSessionResponse(BaseModel):
    """Schema cho response chat session"""
    id: UUID
    user_id: UUID
    title: Optional[str]
    session_type: str
    context_documents: List[UUID]
    model_name: str
    message_count: int
    total_tokens_used: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
                "title": "Java Learning Session",
                "session_type": "document_qa",
                "context_documents": ["550e8400-e29b-41d4-a716-446655440002"],
                "model_name": "gpt-4",
                "message_count": 5,
                "total_tokens_used": 250,
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T10:00:00"
            }
        }


class ChatSessionDetailResponse(ChatSessionResponse):
    """Schema cho response chi tiết chat session"""
    messages: Optional[List[ChatMessageResponse]] = []

    class Config:
        from_attributes = True


class AIUsageResponse(BaseModel):
    """Schema cho response AI usage history"""
    id: UUID
    user_id: UUID
    session_id: Optional[UUID]
    model_name: str
    tokens_used: int
    request_type: str
    cost: Optional[Decimal]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
