"""
Document Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến documents: CRUD, sharing, permissions
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status

from models.documents import Document, DocumentShare
from models.users import User


class DocumentService:
    """
    Service xử lý business logic cho documents
    """
    
    @staticmethod
    def create_document(
        user_id: str,
        title: str,
        category: str,
        tags: List[str],
        file_name: str = "",
        file_path: str = "",
        file_size: int = 0,
        file_type: str = "",
        db: Session
    ) -> Document:
        """
        Tạo document mới
        
        Args:
            user_id: ID của user
            title: Tiêu đề document
            category: Category
            tags: Danh sách tags
            file_name: Tên file
            file_path: Đường dẫn file
            file_size: Kích thước file
            file_type: Loại file
            db: Database session
        
        Returns:
            Document object mới
        """
        new_document = Document(
            user_id=user_id,
            title=title,
            file_name=file_name or title,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            category=category,
            tags=tags or [],
            is_processed=False,
            processing_status="pending"
        )
        
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        
        return new_document
    
    @staticmethod
    def get_user_documents(
        user_id: str,
        db: Session,
        skip: int = 0,
        limit: int = 10
    ) -> List[Document]:
        """
        Lấy danh sách documents của user
        
        Args:
            user_id: ID của user
            db: Database session
            skip: Số lượng bỏ qua (pagination)
            limit: Số lượng tối đa (pagination)
        
        Returns:
            List of Document objects
        """
        documents = db.query(Document).filter(
            Document.user_id == user_id
        ).offset(skip).limit(limit).all()
        
        return documents
    
    @staticmethod
    def get_document_by_id(
        document_id: UUID,
        user_id: str,
        db: Session
    ) -> Document:
        """
        Lấy chi tiết document
        
        Args:
            document_id: ID của document
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            Document object
        
        Raises:
            HTTPException: Nếu document không tồn tại hoặc user không có quyền
        """
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Kiểm tra quyền truy cập (owner hoặc được share)
        if document.user_id != user_id:
            # Kiểm tra document có được share với user không
            share = db.query(DocumentShare).filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_user_id == user_id
            ).first()
            
            if not share:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to access this document"
                )
        
        return document
    
    @staticmethod
    def update_document(
        document_id: UUID,
        user_id: str,
        title: Optional[str],
        category: Optional[str],
        tags: Optional[List[str]],
        db: Session
    ) -> Document:
        """
        Cập nhật document
        
        Args:
            document_id: ID của document
            user_id: ID của user (để check quyền)
            title: Tiêu đề mới
            category: Category mới
            tags: Tags mới
            db: Database session
        
        Returns:
            Document object đã cập nhật
        
        Raises:
            HTTPException: Nếu document không tồn tại hoặc user không có quyền
        """
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if document.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this document"
            )
        
        # Cập nhật fields
        if title is not None:
            document.title = title
        if category is not None:
            document.category = category
        if tags is not None:
            document.tags = tags
        
        db.commit()
        db.refresh(document)
        
        return document
    
    @staticmethod
    def delete_document(
        document_id: UUID,
        user_id: str,
        db: Session
    ) -> bool:
        """
        Xóa document
        
        Args:
            document_id: ID của document
            user_id: ID của user (để check quyền)
            db: Database session
        
        Returns:
            True nếu xóa thành công
        
        Raises:
            HTTPException: Nếu document không tồn tại hoặc user không có quyền
        """
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if document.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this document"
            )
        
        db.delete(document)
        db.commit()
        
        return True
    
    @staticmethod
    def share_document(
        document_id: UUID,
        owner_user_id: str,
        shared_with_user_id: str,
        permission: str,
        db: Session
    ) -> DocumentShare:
        """
        Chia sẻ document với user khác
        
        Args:
            document_id: ID của document
            owner_user_id: ID của owner (để check quyền)
            shared_with_user_id: ID của user được share
            permission: Quyền (view/edit)
            db: Database session
        
        Returns:
            DocumentShare object
        
        Raises:
            HTTPException: Nếu document không tồn tại hoặc user không có quyền
        """
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if document.user_id != owner_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to share this document"
            )
        
        # Kiểm tra user được share tồn tại
        shared_user = db.query(User).filter(
            User.id == shared_with_user_id
        ).first()
        
        if not shared_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Kiểm tra đã share chưa
        existing_share = db.query(DocumentShare).filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == shared_with_user_id
        ).first()
        
        if existing_share:
            # Cập nhật permission
            existing_share.permission = permission
            db.commit()
            db.refresh(existing_share)
            return existing_share
        
        # Tạo share mới
        new_share = DocumentShare(
            document_id=document_id,
            shared_with_user_id=shared_with_user_id,
            permission=permission
        )
        
        db.add(new_share)
        db.commit()
        db.refresh(new_share)
        
        return new_share


# Global document service instance
document_service = DocumentService()
