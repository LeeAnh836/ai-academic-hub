import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, BigInteger, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from .base import BaseModel


class Document(BaseModel):
    """Bảng lưu trữ tài liệu người dùng"""
    __tablename__ = "documents"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(100), nullable=False)
    
    # Trạng thái xử lý
    is_processed = Column(Boolean, default=False, nullable=False)
    processing_status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    
    # Phân loại
    category = Column(String(100), nullable=True)
    tags = Column(ARRAY(String), nullable=True, default=[])

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    embeddings = relationship("DocumentEmbedding", back_populates="document", cascade="all, delete-orphan")
    shares = relationship("DocumentShare", back_populates="document", cascade="all, delete-orphan")
    group_files = relationship("GroupFile", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(BaseModel):
    """Bảng lưu trữ các phần nhỏ của tài liệu (chunks)"""
    __tablename__ = "document_chunks"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_metadata = Column(JSON, nullable=True)
    token_count = Column(Integer, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="chunks")
    embedding = relationship("DocumentEmbedding", back_populates="chunk", uselist=False)


class DocumentEmbedding(BaseModel):
    """Bảng lưu trữ vector embeddings cho các chunks"""
    __tablename__ = "document_embeddings"

    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(JSON, nullable=False)  # Lưu vector dưới dạng JSON hoặc có thể dùng pgvector
    embedding_model = Column(String(100), nullable=False, default="text-embedding-3-small")

    # Relationships
    chunk = relationship("DocumentChunk", back_populates="embedding")
    document = relationship("Document", back_populates="embeddings")


class DocumentShare(BaseModel):
    """Bảng quản lý việc chia sẻ tài liệu"""
    __tablename__ = "document_shares"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(20), default="view", nullable=False)  # view, edit, admin
    shared_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="shares")
    shared_user = relationship("User", foreign_keys=[shared_with_user_id])
