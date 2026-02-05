"""
Chat Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến chat: sessions, messages, feedback
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status

from models.chat import ChatSession, ChatMessage, MessageFeedback
from models.users import User


class ChatService:
    """
    Service xử lý business logic cho chat
    """
    
    @staticmethod
    def create_chat_session(
        user_id: str,
        title: str,
        session_type: str,
        context_documents: List[str],
        model_name: str,
        db: Session
    ) -> ChatSession:
        """
        Tạo chat session mới
        
        Args:
            user_id: ID của user
            title: Tiêu đề session
            session_type: Loại session (general/document/group)
            context_documents: Danh sách document IDs
            model_name: Tên model AI
            db: Database session
        
        Returns:
            ChatSession object mới
        """
        new_session = ChatSession(
            user_id=user_id,
            title=title,
            session_type=session_type,
            context_documents=context_documents or [],
            model_name=model_name
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return new_session
    
    @staticmethod
    def get_user_chat_sessions(
        user_id: str,
        db: Session,
        skip: int = 0,
        limit: int = 10
    ) -> List[ChatSession]:
        """
        Lấy danh sách chat sessions của user
        
        Args:
            user_id: ID của user
            db: Database session
            skip: Số lượng bỏ qua (pagination)
            limit: Số lượng tối đa (pagination)
        
        Returns:
            List of ChatSession objects
        """
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
        
        return sessions
    
    @staticmethod
    def get_chat_session_by_id(
        session_id: UUID,
        user_id: str,
        db: Session
    ) -> ChatSession:
        """
        Lấy chi tiết chat session
        
        Args:
            session_id: ID của session
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            ChatSession object
        
        Raises:
            HTTPException: Nếu session không tồn tại hoặc user không có quyền
        """
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this session"
            )
        
        return session
    
    @staticmethod
    def create_chat_message(
        session_id: UUID,
        user_id: str,
        content: str,
        retrieved_chunks: List[dict],
        db: Session
    ) -> ChatMessage:
        """
        Tạo message mới trong session
        
        Args:
            session_id: ID của session
            user_id: ID của user
            content: Nội dung tin nhắn
            retrieved_chunks: Các chunks được retrieve từ RAG
            db: Database session
        
        Returns:
            ChatMessage object mới
        
        Raises:
            HTTPException: Nếu session không tồn tại hoặc user không có quyền
        """
        # Kiểm tra session tồn tại và user có quyền
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to send messages to this session"
            )
        
        # Tạo message
        new_message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=content,
            retrieved_chunks=retrieved_chunks or []
        )
        
        db.add(new_message)
        
        # Cập nhật message count
        session.message_count += 1
        
        db.commit()
        db.refresh(new_message)
        
        return new_message
    
    @staticmethod
    def get_session_messages(
        session_id: UUID,
        user_id: str,
        db: Session,
        skip: int = 0,
        limit: int = 50
    ) -> List[ChatMessage]:
        """
        Lấy danh sách messages trong session
        
        Args:
            session_id: ID của session
            user_id: ID của user (để check quyền)
            db: Database session
            skip: Số lượng bỏ qua (pagination)
            limit: Số lượng tối đa (pagination)
        
        Returns:
            List of ChatMessage objects
        
        Raises:
            HTTPException: Nếu session không tồn tại hoặc user không có quyền
        """
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this session"
            )
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()
        
        return messages
    
    @staticmethod
    def create_or_update_message_feedback(
        message_id: UUID,
        user_id: str,
        rating: Optional[int],
        is_helpful: Optional[bool],
        comment: Optional[str],
        feedback_type: Optional[str],
        db: Session
    ) -> MessageFeedback:
        """
        Tạo hoặc cập nhật feedback cho message
        
        Args:
            message_id: ID của message
            user_id: ID của user
            rating: Đánh giá (1-5)
            is_helpful: Message có hữu ích không
            comment: Comment
            feedback_type: Loại feedback
            db: Database session
        
        Returns:
            MessageFeedback object
        
        Raises:
            HTTPException: Nếu message không tồn tại hoặc user không có quyền
        """
        message = db.query(ChatMessage).filter(
            ChatMessage.id == message_id
        ).first()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        if message.user_id != user_id:
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
        if rating is not None:
            feedback.rating = rating
        if is_helpful is not None:
            feedback.is_helpful = is_helpful
        if comment is not None:
            feedback.comment = comment
        if feedback_type is not None:
            feedback.feedback_type = feedback_type
        
        db.commit()
        db.refresh(feedback)
        
        return feedback
    
    @staticmethod
    def delete_chat_session(
        session_id: UUID,
        user_id: str,
        db: Session
    ) -> bool:
        """
        Xóa chat session
        
        Args:
            session_id: ID của session
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            True nếu xóa thành công
        
        Raises:
            HTTPException: Nếu session không tồn tại hoặc user không có quyền
        """
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
        
        if session.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this session"
            )
        
        db.delete(session)
        db.commit()
        
        return True


# Global chat service instance
chat_service = ChatService()
