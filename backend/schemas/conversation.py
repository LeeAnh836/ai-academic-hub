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
    content: Optional[str] = None
    message_type: str = "text"  # text, image, file

    class Config:
        json_schema_extra = {
            "example": {
                "receiver_id": "550e8400-e29b-41d4-a716-446655440000",
                "content": "Hi, how are you?",
                "message_type": "text"
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
# Friendship Schemas
# ============================================
class FriendRequestCreate(BaseModel):
    addressee_id: UUID


class FriendRequestAction(BaseModel):
    action: str  # accept, decline


class FriendSearchResult(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    student_id: Optional[str] = None
    avatar_url: Optional[str] = None
    friendship_status: Optional[str] = None  # pending, accepted, none

    class Config:
        from_attributes = True


# ============================================
# Response Schemas
# ============================================
class MessageSenderResponse(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class DirectMessageResponse(BaseModel):
    """Schema cho response direct message"""
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    is_read: bool
    created_at: datetime
    sender: Optional[MessageSenderResponse] = None

    class Config:
        from_attributes = True


class ConversationParticipantResponse(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    student_id: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Schema cho response conversation"""
    id: UUID
    participant_1: UUID
    participant_2: UUID
    last_message_at: datetime
    last_message_content: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    other_user: Optional[ConversationParticipantResponse] = None
    unread_count: int = 0

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    """Schema cho response chi tiết conversation"""
    messages: Optional[List[DirectMessageResponse]] = []

    class Config:
        from_attributes = True


# ============================================
# Group Message Schemas
# ============================================
class GroupMessageSenderResponse(BaseModel):
    id: UUID
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class GroupMessageResponse(BaseModel):
    id: UUID
    group_id: UUID
    user_id: UUID
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    is_pinned: bool = False
    created_at: datetime
    sender: Optional[GroupMessageSenderResponse] = None

    class Config:
        from_attributes = True


class GroupConversationResponse(BaseModel):
    """Group hiển thị trong danh sách trò chuyện"""
    id: UUID
    group_name: str
    last_message_at: Optional[datetime] = None
    last_message_content: Optional[str] = None
    member_count: int = 0
    unread_count: int = 0

    class Config:
        from_attributes = True


class UnifiedConversationResponse(BaseModel):
    """Response thống nhất cho cả direct và group conversations"""
    id: UUID
    type: str  # "direct" or "group"
    name: str
    avatar_url: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    is_online: Optional[bool] = None
    last_activity: Optional[str] = None  # "5 phút trước"
    member_count: Optional[int] = None  # For groups
    other_user_id: Optional[UUID] = None  # For direct
