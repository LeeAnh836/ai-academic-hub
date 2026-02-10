"""
RAG Router
API endpoints cho RAG (Retrieval Augmented Generation)
"""
from fastapi import APIRouter, HTTPException, status

from models.schemas import (
    RAGQueryRequest, RAGQueryResponse, ContextChunk,
    ChatRequest, ChatResponse,
    VectorSearchRequest, VectorSearchResponse
)
from services.rag_service import rag_service


router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """
    Query RAG system - tìm contexts và generate answer
    
    Args:
        request: RAGQueryRequest với question, user_id, filters
    
    Returns:
        RAGQueryResponse với answer, contexts, metadata
    """
    try:
        result = rag_service.query(
            question=request.question,
            user_id=request.user_id,
            document_ids=request.document_ids,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        
        # Convert contexts to ContextChunk objects
        contexts = [
            ContextChunk(
                chunk_id=ctx["chunk_id"],
                document_id=ctx["document_id"],
                chunk_text=ctx["chunk_text"],
                chunk_index=ctx["chunk_index"],
                score=ctx["score"],
                file_name=ctx["file_name"],
                title=ctx.get("title")
            )
            for ctx in result["contexts"]
        ]
        
        return RAGQueryResponse(
            answer=result["answer"],
            contexts=contexts,
            model=result["model"],
            tokens_used=result["tokens_used"],
            processing_time=result["processing_time"]
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat với AI có context từ documents
    
    Args:
        request: ChatRequest với messages, user_id, document_ids
    
    Returns:
        ChatResponse với AI response
    """
    try:
        # Convert ChatMessage objects to dicts
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        result = rag_service.chat(
            messages=messages,
            user_id=request.user_id,
            document_ids=request.document_ids,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Convert contexts if present
        contexts = None
        if result.get("contexts"):
            contexts = [
                ContextChunk(
                    chunk_id=ctx["chunk_id"],
                    document_id=ctx["document_id"],
                    chunk_text=ctx["chunk_text"],
                    chunk_index=ctx["chunk_index"],
                    score=ctx["score"],
                    file_name=ctx["file_name"],
                    title=ctx.get("title")
                )
                for ctx in result["contexts"]
            ]
        
        return ChatResponse(
            message=result["message"],
            contexts=contexts,
            model=result["model"],
            tokens_used=result.get("tokens_used")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}"
        )


@router.post("/search", response_model=VectorSearchResponse)
async def vector_search(request: VectorSearchRequest):
    """
    Tìm kiếm semantic trong documents (không generate answer)
    
    Args:
        request: VectorSearchRequest
    
    Returns:
        VectorSearchResponse với results
    """
    try:
        contexts = rag_service.search_relevant_contexts(
            query=request.query_text,
            user_id=request.user_id or "",
            document_ids=request.document_ids,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        
        results = [
            ContextChunk(
                chunk_id=ctx["chunk_id"],
                document_id=ctx["document_id"],
                chunk_text=ctx["chunk_text"],
                chunk_index=ctx["chunk_index"],
                score=ctx["score"],
                file_name=ctx["file_name"],
                title=ctx.get("title")
            )
            for ctx in contexts
        ]
        
        return VectorSearchResponse(
            results=results,
            query_vector_dimension=1024  # Cohere dimension
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {str(e)}"
        )
