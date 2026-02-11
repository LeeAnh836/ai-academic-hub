"""
Pydantic Models for AI Service
Request/Response schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================
# Embedding Models
# ============================================
class EmbedRequest(BaseModel):
    """Request để generate embeddings"""
    texts: List[str] = Field(..., description="Danh sách texts cần embed")
    input_type: str = Field(default="search_document", description="Input type: search_document hoặc search_query")


class EmbedResponse(BaseModel):
    """Response từ embedding"""
    embeddings: List[List[float]] = Field(..., description="Danh sách embedding vectors")
    model: str = Field(..., description="Model đã sử dụng")
    dimension: int = Field(..., description="Vector dimension")


# ============================================
# Document Processing Models
# ============================================
class DocumentChunk(BaseModel):
    """Document chunk data"""
    chunk_index: int
    chunk_text: str
    chunk_metadata: Dict[str, Any]
    token_count: int


class ProcessDocumentRequest(BaseModel):
    """Request để xử lý document"""
    file_content: bytes = Field(..., description="Binary content của file")
    file_name: str = Field(..., description="Tên file")
    file_type: str = Field(..., description="MIME type hoặc extension")
    document_id: str = Field(..., description="UUID của document trong DB")
    user_id: str = Field(..., description="UUID của user")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata bổ sung")


class ProcessDocumentResponse(BaseModel):
    """Response sau khi xử lý document"""
    success: bool
    message: str
    chunks_count: int
    vectors_count: int


# ============================================
# RAG Models
# ============================================
class RAGQueryRequest(BaseModel):
    """Request để query RAG system"""
    question: str = Field(..., description="Câu hỏi của user")
    user_id: str = Field(..., description="UUID của user để filter documents")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter theo document IDs cụ thể")
    top_k: int = Field(default=5, description="Số lượng context chunks")
    score_threshold: float = Field(default=0.5, description="Ngưỡng similarity score (tự động fallback nếu cần)")
    include_sources: bool = Field(default=True, description="Có trả về sources không")


class ContextChunk(BaseModel):
    """Context chunk từ vector search"""
    chunk_id: str
    document_id: str
    chunk_text: str
    chunk_index: int
    score: float
    file_name: str
    title: Optional[str] = None


class RAGQueryResponse(BaseModel):
    """Response từ RAG query"""
    answer: str = Field(..., description="Câu trả lời từ LLM")
    contexts: List[ContextChunk] = Field(..., description="Context chunks đã sử dụng")
    model: str = Field(..., description="LLM model đã dùng")
    tokens_used: Optional[int] = Field(default=None, description="Số tokens đã sử dụng")
    processing_time: float = Field(..., description="Thời gian xử lý (giây)")
    query_type: Optional[str] = Field(default="factual", description="Loại câu hỏi: factual/creative/analytical")


# ============================================
# Chat Models
# ============================================
class ChatMessage(BaseModel):
    """Chat message"""
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., description="Nội dung message")


class ChatRequest(BaseModel):
    """Request để chat với AI"""
    messages: List[ChatMessage] = Field(..., description="Chat history")
    user_id: str = Field(..., description="UUID của user")
    document_ids: Optional[List[str]] = Field(default=None, description="Context documents")
    model: Optional[str] = Field(default=None, description="LLM model")
    temperature: float = Field(default=0.7, description="Temperature (0-1)")
    max_tokens: int = Field(default=2000, description="Max tokens response")
    stream: bool = Field(default=False, description="Stream response")


class ChatResponse(BaseModel):
    """Response từ chat"""
    message: str = Field(..., description="AI response")
    contexts: Optional[List[ContextChunk]] = Field(default=None, description="Context sử dụng")
    model: str = Field(..., description="Model đã dùng")
    tokens_used: Optional[int] = Field(default=None, description="Tokens used")


# ============================================
# Vector Search Models
# ============================================
class VectorSearchRequest(BaseModel):
    """Request để search vectors"""
    query_text: str = Field(..., description="Text query")
    user_id: Optional[str] = Field(default=None, description="Filter by user")
    document_ids: Optional[List[str]] = Field(default=None, description="Filter by documents")
    top_k: int = Field(default=5, description="Số kết quả")
    score_threshold: float = Field(default=0.7, description="Ngưỡng score")


class VectorSearchResponse(BaseModel):
    """Response từ vector search"""
    results: List[ContextChunk] = Field(..., description="Kết quả tìm kiếm")
    query_vector_dimension: int = Field(..., description="Dimension của query vector")


# ============================================
# Health Check Models
# ============================================
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    qdrant_status: str
    cohere_status: str
    timestamp: datetime
