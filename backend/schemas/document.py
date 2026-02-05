"""
Pydantic schemas cho Document
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================
# Request Schemas
# ============================================
class DocumentCreateRequest(BaseModel):
    """Schema cho request tạo document"""
    title: str = Field(..., max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "title": "My Java Document",
                "category": "programming",
                "tags": ["java", "tutorial"]
            }
        }


class DocumentUpdateRequest(BaseModel):
    """Schema cho request cập nhật document"""
    title: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Java Document",
                "category": "programming",
                "tags": ["java", "advanced"]
            }
        }


class DocumentShareRequest(BaseModel):
    """Schema cho request chia sẻ document"""
    shared_with_user_id: UUID
    permission: str = Field(default="view", pattern="^(view|edit|admin)$")

    class Config:
        json_schema_extra = {
            "example": {
                "shared_with_user_id": "550e8400-e29b-41d4-a716-446655440000",
                "permission": "view"
            }
        }


# ============================================
# Response Schemas
# ============================================
class DocumentChunkResponse(BaseModel):
    """Schema cho response document chunk"""
    id: UUID
    chunk_index: int
    chunk_text: str
    token_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentEmbeddingResponse(BaseModel):
    """Schema cho response document embedding"""
    id: UUID
    embedding_model: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentShareResponse(BaseModel):
    """Schema cho response document share"""
    id: UUID
    document_id: UUID
    shared_with_user_id: UUID
    permission: str
    shared_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Schema cho response document"""
    id: UUID
    user_id: UUID
    title: str
    file_name: str
    file_size: int
    file_type: str
    is_processed: bool
    processing_status: str
    category: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
                "title": "Java Programming Guide",
                "file_name": "java_guide.pdf",
                "file_size": 1024000,
                "file_type": "application/pdf",
                "is_processed": True,
                "processing_status": "completed",
                "category": "programming",
                "tags": ["java", "guide"],
                "created_at": "2024-02-01T10:00:00",
                "updated_at": "2024-02-01T10:00:00"
            }
        }


class DocumentDetailResponse(DocumentResponse):
    """Schema cho response chi tiết document"""
    chunks: Optional[List[DocumentChunkResponse]] = []
    embeddings: Optional[List[DocumentEmbeddingResponse]] = []
    shares: Optional[List[DocumentShareResponse]] = []

    class Config:
        from_attributes = True
