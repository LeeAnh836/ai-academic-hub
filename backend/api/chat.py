"""
Chat routes - Chat sessions, messages
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from core.databases import get_db
from api.dependencies import get_current_user
from services.chat_service import chat_service
from schemas.chat import (
    ChatSessionResponse, ChatSessionCreateRequest, ChatMessageResponse,
    ChatMessageCreateRequest, MessageFeedbackRequest, ChatSessionDetailResponse,
    AIUsageResponse
)
from models.users import User

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================
# List chat sessions
# ============================================
@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    
    db.delete(session)
    db.commit()
