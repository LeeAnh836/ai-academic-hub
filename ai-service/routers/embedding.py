"""
Embedding Router
API endpoints cho embedding operations
"""
from fastapi import APIRouter, HTTPException, status
from typing import List

from models.schemas import EmbedRequest, EmbedResponse
from services.embedding_service import embedding_service
from core.config import settings


router = APIRouter(prefix="/api/embed", tags=["embedding"])


@router.post("", response_model=EmbedResponse)
async def generate_embeddings(request: EmbedRequest):
    """
    Generate embeddings cho texts
    
    Args:
        request: EmbedRequest với texts và input_type
    
    Returns:
        EmbedResponse với embeddings
    """
    try:
        embeddings = embedding_service.embed_texts(
            texts=request.texts,
            input_type=request.input_type
        )
        
        return EmbedResponse(
            embeddings=embeddings,
            model=settings.COHERE_EMBEDDING_MODEL,
            dimension=settings.VECTOR_DIMENSION
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )


@router.post("/query", response_model=List[float])
async def embed_query(query: str):
    """
    Generate embedding cho single query (tiện dụng cho search)
    
    Args:
        query: Query string
    
    Returns:
        Embedding vector
    """
    try:
        embedding = embedding_service.embed_query(query)
        return embedding
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query embedding failed: {str(e)}"
        )
