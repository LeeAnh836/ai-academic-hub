import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from .base import BaseModel


class ChatSession(BaseModel):
    """Bảng lưu trữ phiên chat AI"""
    __tablename__ = "chat_sessions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    session_type = Column(String(50), default="general", nullable=False)  # general, document_qa
    context_documents = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])
    model_name = Column(String(100), nullable=False, default="gpt-3.5-turbo")
    message_count = Column(Integer, default=0, nullable=False)
    total_tokens_used = Column(Integer, default=0, nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(BaseModel):
    """Bảng lưu trữ các tin nhắn trong phiên chat"""
    __tablename__ = "chat_messages"

    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    retrieved_chunks = Column(ARRAY(UUID(as_uuid=True)), nullable=True, default=[])
    total_tokens = Column(Integer, nullable=False, default=0)
    confidence_score = Column(Numeric(3, 2), nullable=True)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    user = relationship("User", back_populates="chat_messages")
    feedback = relationship("MessageFeedback", back_populates="message", cascade="all, delete-orphan", uselist=False)


class MessageFeedback(BaseModel):
    """Bảng lưu trữ phản hồi người dùng về tin nhắn AI"""
    __tablename__ = "message_feedback"

    message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating = Column(Integer, nullable=True)  # 1-5 star rating
    is_helpful = Column(String(20), nullable=True)  # helpful, not_helpful
    comment = Column(Text, nullable=True)
    feedback_type = Column(String(50), nullable=True)

    # Relationships
    message = relationship("ChatMessage", back_populates="feedback")


class AIUsageHistory(BaseModel):
    """Bảng ghi lại lịch sử sử dụng AI"""
    __tablename__ = "ai_usage_history"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True)
    model_name = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=False)
    request_type = Column(String(50), nullable=False)  # message, embedding, etc
    cost = Column(Numeric(10, 6), nullable=True)
    status = Column(String(20), default="success", nullable=False)  # success, failed
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="ai_usage_history")
    session = relationship("ChatSession", foreign_keys=[session_id])
