import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel


class Conversation(BaseModel):
    """Bảng lưu trữ cuộc trò chuyện trực tiếp giữa hai người"""
    __tablename__ = "conversations"

    participant_1 = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_2 = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_message_content = Column(Text, nullable=True)

    # Relationships
    user_1 = relationship("User", foreign_keys=[participant_1], back_populates="sent_conversations_1")
    user_2 = relationship("User", foreign_keys=[participant_2], back_populates="sent_conversations_2")
    messages = relationship("DirectMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="DirectMessage.created_at")


class DirectMessage(BaseModel):
    """Bảng lưu trữ tin nhắn trực tiếp"""
    __tablename__ = "direct_messages"

    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(String(20), default="text", nullable=False)  # text, image, file
    file_url = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    reply_to_id = Column(UUID(as_uuid=True), ForeignKey("direct_messages.id", ondelete="SET NULL"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    @hybrid_property
    def status(self):
        """Sent -> Delivered -> Seen"""
        if self.is_read:
            return "seen"
        if self.delivered_at:
            return "delivered"
        return "sent"

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    reply_to = relationship("DirectMessage", remote_side="DirectMessage.id", foreign_keys=[reply_to_id], uselist=False)
    reactions = relationship("MessageReaction", back_populates="direct_message", cascade="all, delete-orphan",
                             primaryjoin="DirectMessage.id == MessageReaction.direct_message_id")


class Friendship(BaseModel):
    """Bảng quản lý kết bạn"""
    __tablename__ = "friendships"

    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    addressee_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, accepted, declined

    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])


class MessageReaction(BaseModel):
    """Bảng lưu trữ reaction cho tin nhắn (direct + group)"""
    __tablename__ = "message_reactions"
    __table_args__ = (
        UniqueConstraint("direct_message_id", "user_id", name="uq_dm_reaction_user"),
        UniqueConstraint("group_message_id", "user_id", name="uq_gm_reaction_user"),
    )

    direct_message_id = Column(UUID(as_uuid=True), ForeignKey("direct_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    group_message_id = Column(UUID(as_uuid=True), ForeignKey("group_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction = Column(String(20), nullable=False)  # like, heart, haha, wow, sad, angry

    # Relationships
    direct_message = relationship("DirectMessage", back_populates="reactions")
    group_message = relationship("GroupMessage", back_populates="reactions")
    user = relationship("User")
