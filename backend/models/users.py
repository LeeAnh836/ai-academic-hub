import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class User(BaseModel):
    """Bảng người dùng - trung tâm của hệ thống"""
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Vai trò người dùng
    role = Column(String(20), default="user", nullable=False)  # user, admin
    
    # Mã sinh viên (8 số)
    student_id = Column(String(8), nullable=False, unique=True, index=True)
    
    # Xác minh email
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    
    # Trạng thái
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    user_sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user", cascade="all, delete-orphan")
    user_settings = relationship("UserSettings", back_populates="user", cascade="all, delete-orphan")
    
    # Documents
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    
    # Chat
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    ai_usage_history = relationship("AIUsageHistory", back_populates="user", cascade="all, delete-orphan")
    
    # Groups
    created_groups = relationship("Group", foreign_keys="Group.created_by", back_populates="creator")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    group_messages = relationship("GroupMessage", back_populates="user", cascade="all, delete-orphan")
    
    # Direct Messages
    sent_conversations_1 = relationship(
        "Conversation",
        foreign_keys="Conversation.participant_1",
        back_populates="user_1"
    )
    sent_conversations_2 = relationship(
        "Conversation",
        foreign_keys="Conversation.participant_2",
        back_populates="user_2"
    )
    sent_messages = relationship("DirectMessage", foreign_keys="DirectMessage.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_messages = relationship("DirectMessage", foreign_keys="DirectMessage.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    
    # Notifications
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    
    # Audit
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class UserSession(BaseModel):
    """Bảng lưu trữ phiên đăng nhập người dùng"""
    __tablename__ = "user_sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String(500), unique=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_sessions")


class LoginHistory(BaseModel):
    """Bảng ghi lại lịch sử đăng nhập"""
    __tablename__ = "login_history"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(String(20), default="success", nullable=False)  # success, failed
    failed_reason = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User", back_populates="login_history")


class UserSettings(BaseModel):
    """Bảng cài đặt người dùng"""
    __tablename__ = "user_settings"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    theme = Column(String(20), default="light", nullable=False)
    language = Column(String(10), default="en", nullable=False)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    email_notifications = Column(Boolean, default=True, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="user_settings", uselist=False)
