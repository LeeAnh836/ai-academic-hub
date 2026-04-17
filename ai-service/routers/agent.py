"""
Multi-Agent Router
API endpoints for Multi-Agent AI System
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional, List
from pydantic import BaseModel
import json

from services.master_orchestrator import master_orchestrator
from core.config import settings


router = APIRouter(prefix="/api/agent", tags=["multi-agent"])


# ============================================
# Request/Response Models
# ============================================

class AgentQueryRequest(BaseModel):
    """
    Request for multi-agent query
    """
    query: str
    user_id: str
    session_id: str
    document_ids: Optional[List[str]] = None
    top_k: Optional[int] = 5
    score_threshold: Optional[float] = 0.5
    chat_history: Optional[List[dict]] = None
    conversation_summary: Optional[str] = None
    source_ids: Optional[List[str]] = None
    source_metadata: Optional[List[dict]] = None
    trace_id: Optional[str] = None
    persisted_by_backend: Optional[bool] = False


class AgentQueryResponse(BaseModel):
    """
    Response from multi-agent system
    """
    answer: str
    intent: str
    agent_used: str
    preprocessing: dict
    metadata: dict
    processing_time: float


class DataAnalysisRequest(BaseModel):
    """
    Request for data analysis
    """
    query: str
    user_id: str
    session_id: str
    file_path: Optional[str] = None
    file_name: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    """
    Chat history response
    """
    messages: List[dict]
    session_id: str
    user_id: str


# ============================================
# Endpoints
# ============================================

@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(request: AgentQueryRequest):
    """
    Multi-Agent Query - Main endpoint
    
    Handles:
        - Document QA (RAG)
        - General QA
        - Data Analysis (if file_path provided in context)
        - Code generation
        - Homework solving
    
    Features:
        - Automatic intent classification
        - Ambiguous query preprocessing
        - Memory-aware responses
        - Agent orchestration
    
    Args:
        request: AgentQueryRequest
    
    Returns:
        AgentQueryResponse with answer and metadata
    """
    try:
        # Check if multi-agent is enabled
        if not settings.ENABLE_MULTI_AGENT:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Multi-Agent system is not enabled"
            )
        
        # Build context
        context = {
            "document_ids": request.document_ids or [],
            "top_k": request.top_k,
            "score_threshold": request.score_threshold,
            "chat_history": request.chat_history or [],
            "conversation_summary": request.conversation_summary,
            "source_ids": request.source_ids or [],
            "source_metadata": request.source_metadata or [],
            "trace_id": request.trace_id,
            "persisted_by_backend": bool(request.persisted_by_backend),
        }
        
        # Process query
        result = await master_orchestrator.process_query(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            context=context
        )
        
        return AgentQueryResponse(
            answer=result.get("answer", ""),
            intent=result.get("intent", "unknown"),
            agent_used=result.get("agent_used", "unknown"),
            preprocessing=result.get("preprocessing", {}),
            metadata=result.get("metadata", {}),
            processing_time=result.get("processing_time", 0)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent query failed: {str(e)}"
        )


@router.post("/analyze-data")
async def analyze_data(
    query: str = Form(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Data Analysis with CSV/Excel files
    
    Upload a data file and ask analysis questions
    
    Args:
        query: Analysis question (e.g., "Phân tích doanh thu theo tháng")
        user_id: User ID
        session_id: Session ID
        file: CSV or Excel file
    
    Returns:
        Analysis results with generated code and output
    """
    try:
        if not settings.ENABLE_DATA_ANALYSIS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Data Analysis is not enabled"
            )
        
        # Read file data
        file_data = await file.read()
        file_name = file.filename
        
        # Build context
        context = {
            "file_data": file_data,
            "file_name": file_name,
            "file_path": None  # Not using file_path, using file_data directly
        }
        
        # Process with orchestrator
        result = await master_orchestrator.process_query(
            query=query,
            user_id=user_id,
            session_id=session_id,
            context=context
        )
        
        return {
            "success": True,
            "answer": result.get("answer", ""),
            "agent_used": result.get("agent_used", ""),
            "metadata": result.get("metadata", {}),
            "processing_time": result.get("processing_time", 0)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data analysis failed: {str(e)}"
        )


@router.get("/history/{user_id}/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    user_id: str,
    session_id: str,
    limit: int = 10
):
    """
    Get chat history for a session
    
    Args:
        user_id: User ID
        session_id: Session ID
        limit: Max number of messages
    
    Returns:
        Chat history
    """
    try:
        messages = master_orchestrator.get_chat_history(
            user_id=user_id,
            session_id=session_id,
            limit=limit
        )
        
        return ChatHistoryResponse(
            messages=messages,
            session_id=session_id,
            user_id=user_id
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


@router.delete("/history/{user_id}/{session_id}")
async def clear_chat_history(
    user_id: str,
    session_id: str
):
    """
    Clear chat history for a session
    
    Args:
        user_id: User ID
        session_id: Session ID
    
    Returns:
        Success status
    """
    try:
        success = master_orchestrator.clear_session(
            user_id=user_id,
            session_id=session_id
        )
        
        return {
            "success": success,
            "message": "Session cleared successfully" if success else "Failed to clear session"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear session: {str(e)}"
        )


@router.get("/status")
async def agent_status():
    """
    Get multi-agent system status
    
    Returns:
        System status and available agents
    """
    try:
        from agents.code_executor import code_executor
        from core.memory import memory_manager
        
        return {
            "multi_agent_enabled": settings.ENABLE_MULTI_AGENT,
            "memory_enabled": memory_manager.enabled,
            "code_execution_enabled": code_executor.enabled,
            "data_analysis_enabled": settings.ENABLE_DATA_ANALYSIS,
            "prompt_preprocessing_enabled": settings.ENABLE_PROMPT_PREPROCESSING,
            "agents_available": [
                "document_qa_agent",
                "data_analysis_agent",
                "general_qa_agent"
            ],
            "features": {
                "rag": True,
                "data_analysis": code_executor.enabled,
                "memory": memory_manager.enabled,
                "ambiguous_query_handling": settings.ENABLE_PROMPT_PREPROCESSING
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )
