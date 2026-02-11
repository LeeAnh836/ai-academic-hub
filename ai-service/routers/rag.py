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
    Query RAG system with Multi-Model Orchestrator
    
    NEW FEATURES:
    - Intent classification (direct_chat, rag_query, summarization, etc.)
    - Multi-model routing (Gemini Flash/Pro, Groq)
    - Smart fallback strategy
    - Supports chat without documents
    
    Args:
        request: RAGQueryRequest với question, user_id, filters
    
    Returns:
        RAGQueryResponse với answer, contexts, intent, model used
    """
    try:
        # Call new orchestrator method
        result = await rag_service.query_with_orchestrator(
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
            for ctx in result.get("contexts", [])
        ]
        
        return RAGQueryResponse(
            answer=result["answer"],
            contexts=contexts,
            model=result.get("model", "unknown"),
            tokens_used=result.get("tokens_used", 0),
            processing_time=result.get("processing_time", 0),
            query_type=result.get("intent", "unknown")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat với AI - Supports both direct chat and RAG
    
    NEW: Can work WITHOUT documents for general questions/homework
    
    Args:
        request: ChatRequest với messages, user_id, document_ids (optional)
    
    Returns:
        ChatResponse với AI response
    """
    try:
        # Get last user message
        if not request.messages or len(request.messages) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Messages cannot be empty"
            )
        
        last_message = request.messages[-1].content
        
        # Use orchestrator for processing
        result = await rag_service.query_with_orchestrator(
            question=last_message,
            user_id=request.user_id,
            document_ids=request.document_ids,
            top_k=3,  # Fewer contexts for chat
            score_threshold=0.5,
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
            message=result.get("answer", result.get("message", "")),  # Support both keys
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
