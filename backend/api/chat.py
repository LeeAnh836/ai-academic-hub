"""
Chat routes - Chat sessions, messages
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from core.databases import get_db
from api.dependencies import get_current_user, CurrentUser
from services.chat_service import chat_service
from schemas.chat import (
    ChatSessionResponse, ChatSessionCreateRequest, ChatMessageResponse,
    ChatMessageCreateRequest, MessageFeedbackRequest, ChatSessionDetailResponse,
    AIUsageResponse, ChatAskRequest, ChatAskResponse, ContextChunkResponse
)
from models.users import User
from models.chat import ChatSession, ChatMessage, MessageFeedback, AIUsageHistory
import httpx
import time
from core.config import settings

router = APIRouter(
    prefix="/api/chat", 
    tags=["chat"],
    dependencies=[Depends(get_current_user)]  # Apply authentication to all endpoints
)


# ============================================
# List chat sessions
# ============================================
@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Lấy danh sách chat sessions của user
    """
    sessions = chat_service.get_user_chat_sessions(
        user_id=str(current_user.id),
        db=db,
        skip=skip,
        limit=limit
    )
    
    return sessions


# ============================================
# Create chat session
# ============================================
@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: ChatSessionCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Tạo chat session mới
    """
    new_session = chat_service.create_chat_session(
        user_id=str(current_user.id),
        title=request.title,
        session_type=request.session_type,
        context_documents=request.context_documents or [],
        model_name=request.model_name,
        db=db
    )
    
    return new_session


# ============================================
# Get chat session detail
# ============================================
@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Lấy chi tiết chat session
    """
    session = chat_service.get_chat_session_by_id(
        session_id=session_id,
        user_id=str(current_user.id),
        db=db
    )
    
    return session


# ============================================
# Send chat message
# ============================================
@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    request: ChatMessageCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Gửi tin nhắn trong chat session
    """
    # Kiểm tra session tồn tại và user có quyền
    session = db.query(ChatSession).filter(
        ChatSession.id == request.session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to send messages to this session"
        )
    
    # Tạo message
    new_message = ChatMessage(
        session_id=request.session_id,
        user_id=current_user.id,
        role="user",
        content=request.content,
        retrieved_chunks=request.retrieved_chunks or []
    )
    
    db.add(new_message)
    
    # Cập nhật message count
    session.message_count += 1
    
    db.commit()
    db.refresh(new_message)
    
    return new_message


# ============================================
# Get session messages
# ============================================
@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50
):
    """
    Lấy danh sách tin nhắn trong session
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this session"
        )
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
    
    return messages


# ============================================
# Send feedback for message
# ============================================
@router.post("/messages/{message_id}/feedback")
async def send_message_feedback(
    message_id: UUID,
    request: MessageFeedbackRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Gửi feedback cho tin nhắn
    """
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if message.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to send feedback for this message"
        )
    
    # Kiểm tra feedback đã tồn tại
    feedback = db.query(MessageFeedback).filter(
        MessageFeedback.message_id == message_id
    ).first()
    
    if not feedback:
        feedback = MessageFeedback(message_id=message_id)
        db.add(feedback)
    
    # Cập nhật feedback
    if request.rating is not None:
        feedback.rating = request.rating
    if request.is_helpful is not None:
        feedback.is_helpful = request.is_helpful
    if request.comment is not None:
        feedback.comment = request.comment
    if request.feedback_type is not None:
        feedback.feedback_type = request.feedback_type
    
    db.commit()
    db.refresh(feedback)
    
    return {"message": "Feedback sent successfully"}


# ============================================
# Delete chat session
# ============================================
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Xóa chat session
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this session"
        )


# ============================================
# Ask AI in chat session (Integration Endpoint)
# ============================================
@router.post("/sessions/{session_id}/ask", response_model=ChatAskResponse)
async def ask_in_chat_session(
    session_id: UUID,
    request: ChatAskRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Hỏi AI trong chat session - Tự động lưu messages và gọi AI Service
    
    Flow:
    1. Validate session & user permission
    2. Save user message to chat_messages
    3. Call AI Service internally
    4. Save AI response to chat_messages
    5. Update session stats
    6. Track usage to ai_usage_history
    7. Return complete conversation
    """
    start_time = time.time()
    
    # 1. Validate session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to use this session"
        )
    
    # 2. Save user message
    user_message = ChatMessage(
        session_id=session_id,
        user_id=current_user.id,
        role="user",
        content=request.question,
        retrieved_chunks=[],
        total_tokens=0
    )
    db.add(user_message)
    db.flush()  # Get ID without committing
    
    try:
        # 3. Call AI Service internally (Multi-Agent System)
        ai_service_url = f"{settings.AI_SERVICE_URL}/api/agent/query"
        
        # Prepare request for AI Service
        # Logic: 
        # - document_ids=[] → Direct chat (no RAG)
        # - document_ids=None → Use session's context_documents (no cross-session fallback)
        # - document_ids=[...] → Use specified documents AND persist to session
        if request.document_ids is not None:
            # User explicitly specified (including [])
            doc_ids_to_use = [str(doc_id) for doc_id in request.document_ids] if request.document_ids else None
            # Persist non-empty doc lists to session so follow-up questions remember context
            if request.document_ids:
                session.context_documents = [str(doc_id) for doc_id in request.document_ids]
                db.flush()
        else:
            # Use session's persistent context (no global cross-session fallback)
            if session.context_documents:
                doc_ids_to_use = [str(doc_id) for doc_id in session.context_documents]
            else:
                doc_ids_to_use = None

        # Build chat history from last 6 DB messages for this session (for context continuity)
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(6).all()
        chat_history_for_ai = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent_messages)
        ]

        ai_request = {
            "query": request.question,
            "user_id": str(current_user.id),
            "session_id": str(session_id),
            "document_ids": doc_ids_to_use,
            "top_k": request.top_k,
            "score_threshold": request.score_threshold,
            "chat_history": chat_history_for_ai
        }
        
        # Add optional parameters
        if request.temperature is not None:
            ai_request["temperature"] = request.temperature
        if request.max_tokens is not None:
            ai_request["max_tokens"] = request.max_tokens
        
        # Call AI Service with timeout
        async with httpx.AsyncClient(timeout=120.0) as client:
            ai_response = await client.post(
                ai_service_url,
                json=ai_request
            )
            ai_response.raise_for_status()
            ai_data = ai_response.json()
        
        # 4. Save AI response message (Multi-Agent response format)
        # Extract context information from metadata if available
        metadata = ai_data.get("metadata", {})
        retrieved_contexts = metadata.get("contexts", [])
        
        ai_message = ChatMessage(
            session_id=session_id,
            user_id=current_user.id,
            role="assistant",
            content=ai_data["answer"],
            retrieved_chunks=[ctx.get("chunk_id", "") for ctx in retrieved_contexts],
            total_tokens=metadata.get("tokens_used", 0),
            confidence_score=None
        )
        db.add(ai_message)
        
        # 5. Update session stats
        session.message_count += 2  # User + AI messages
        session.total_tokens_used += metadata.get("tokens_used", 0)
        
        # 6. Track usage
        usage_record = AIUsageHistory(
            user_id=current_user.id,
            session_id=session_id,
            model_name=metadata.get("model", session.model_name),
            tokens_used=metadata.get("tokens_used", 0),
            request_type="chat_message",
            status="success"
        )
        db.add(usage_record)
        
        # Commit all changes
        db.commit()
        db.refresh(user_message)
        db.refresh(ai_message)
        
        # 7. Build response
        processing_time = time.time() - start_time
        
        # Convert contexts to response format (from metadata)
        contexts = [
            ContextChunkResponse(
                chunk_id=ctx.get("chunk_id", ""),
                document_id=ctx.get("document_id", ""),
                chunk_text=ctx.get("chunk_text", ""),
                chunk_index=ctx.get("chunk_index", 0),
                score=ctx.get("score", 0.0),
                file_name=ctx.get("file_name", ""),
                title=ctx.get("title")
            )
            for ctx in retrieved_contexts
        ]
        
        return ChatAskResponse(
            session_id=session_id,
            user_message=user_message,
            ai_message=ai_message,
            contexts=contexts,
            processing_time=processing_time,
            model_used=metadata.get("model", session.model_name)
        )
    
    except httpx.HTTPError as e:
        # AI Service call failed
        db.rollback()
        
        # Log error to usage history
        error_record = AIUsageHistory(
            user_id=current_user.id,
            session_id=session_id,
            model_name=session.model_name,
            tokens_used=0,
            request_type="chat_message",
            status="failed",
            error_message=str(e)
        )
        db.add(error_record)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI Service unavailable: {str(e)}"
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}"
        )
    
    db.delete(session)
    db.commit()
