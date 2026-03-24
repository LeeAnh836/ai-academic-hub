"""
Pydantic schemas cho Admin API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================
# Response Schemas
# ============================================

class AdminStatsResponse(BaseModel):
    """Thống kê tổng quan cho admin dashboard"""
    total_users: int
    active_today: int
    total_groups: int
    total_files: int
    total_ai_chats: int
    storage_used: str  # Human-readable format, e.g. "124.5 GB"


class AdminUserResponse(BaseModel):
    """User item trong admin user list"""
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: str
    student_id: Optional[str]
    is_active: bool
    is_verified: bool
    online: bool
    last_seen: Optional[str]  # "Now", "2h ago", etc.
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """Paginated user list"""
    users: List[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminGroupResponse(BaseModel):
    """Group item trong admin group list"""
    id: UUID
    name: str
    description: Optional[str]
    members: int
    files: int
    last_active: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AdminGroupListResponse(BaseModel):
    """Paginated group list"""
    groups: List[AdminGroupResponse]
    total: int
    page: int
    page_size: int


class AdminDocumentResponse(BaseModel):
    """Document item trong admin file list"""
    id: UUID
    name: str
    file_type: str
    size: str  # Human-readable, "2.4 MB"
    owner: str  # Full name or username
    owner_id: UUID
    shared: bool
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AdminDocumentListResponse(BaseModel):
    """Paginated document list"""
    documents: List[AdminDocumentResponse]
    total: int
    page: int
    page_size: int


class AdminActivityLogResponse(BaseModel):
    """Activity log entry"""
    id: UUID
    user: str  # Full name or username
    action: str
    target: Optional[str]
    ip_address: Optional[str]
    timestamp: str  # "2 minutes ago"
    created_at: datetime

    class Config:
        from_attributes = True


class AdminActivityLogListResponse(BaseModel):
    """Paginated activity log list"""
    logs: List[AdminActivityLogResponse]
    total: int
    page: int
    page_size: int


# ============================================
# Request Schemas
# ============================================

class ChangeUserRoleRequest(BaseModel):
    """Schema cho request thay đổi role user"""
    role: str = Field(..., pattern="^(admin|user)$")
