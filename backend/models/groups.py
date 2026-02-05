import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class Group(BaseModel):
    """Bảng lưu trữ thông tin nhóm"""
    __tablename__ = "groups"

    group_name = Column(String(255), nullable=False)
    group_type = Column(String(50), default="public", nullable=False)  # public, private
    is_public = Column(Boolean, default=False, nullable=False)
    join_code = Column(String(50), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    member_count = Column(Integer, default=0, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_groups")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan")
    files = relationship("GroupFile", back_populates="group", cascade="all, delete-orphan")


class GroupMember(BaseModel):
    """Bảng quản lý thành viên của nhóm"""
    __tablename__ = "group_members"

    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="member", nullable=False)  # owner, admin, member
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")


class GroupMessage(BaseModel):
    """Bảng lưu trữ tin nhắn trong nhóm"""
    __tablename__ = "group_messages"

    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_type = Column(String(50), default="text", nullable=False)  # text, file, image
    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)

    # Relationships
    group = relationship("Group", back_populates="messages")
    user = relationship("User", back_populates="group_messages")


class GroupFile(BaseModel):
    """Bảng quản lý tệp chia sẻ trong nhóm"""
    __tablename__ = "group_files"

    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shared_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    group = relationship("Group", back_populates="files")
    document = relationship("Document", back_populates="group_files")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])
