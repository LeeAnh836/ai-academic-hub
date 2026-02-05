"""
Pydantic schemas cho Notification
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# ============================================
# Request Schemas
# ============================================
class NotificationMarkAsReadRequest(BaseModel):
    """Schema cho request đánh dấu notification đã đọc"""
    notification_id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


# ============================================
# Response Schemas
# ============================================
class NotificationResponse(BaseModel):
    """Schema cho response notification"""
    id: UUID
    user_id: UUID
    notification_type: str
    title: str
    content: str
    is_read: bool
    related_object_type: Optional[str]
    related_object_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
                "notification_type": "message",
                "title": "New message",
                "content": "You have a new message from John Doe",
                "is_read": False,
                "related_object_type": "user",
                "related_object_id": "550e8400-e29b-41d4-a716-446655440002",
                "created_at": "2024-02-01T10:00:00"
            }
        }
