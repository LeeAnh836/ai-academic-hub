"""
Document routes - CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from core.databases import get_db
from api.dependencies import get_current_user
from schemas.document import (
    DocumentResponse, DocumentCreateRequest, DocumentUpdateRequest,
    DocumentShareRequest, DocumentShareResponse, DocumentDetailResponse
)
from models.users import User
from models.documents import Document, DocumentShare

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ============================================
# List user documents
# ============================================
@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Lấy danh sách documents của user
    """
    documents = db.query(Document).filter(
        Document.user_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    return documents


# ============================================
# Create document
# ============================================
@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    request: DocumentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Tạo document mới
    """
    new_document = Document(
        user_id=current_user.id,
        title=request.title,
        file_name=request.title,  # TODO: Lấy từ upload file
        file_path="",  # TODO: Lấy từ upload file
        file_size=0,  # TODO: Lấy từ upload file
        file_type="",  # TODO: Lấy từ upload file
        category=request.category,
        tags=request.tags or [],
        is_processed=False,
        processing_status="pending"
    )
    
    db.add(new_document)
    db.commit()
    db.refresh(new_document)
    
    return new_document


# ============================================
# Get document detail
# ============================================
@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy chi tiết document
    """
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Kiểm tra quyền truy cập
    if document.user_id != current_user.id:
        # TODO: Kiểm tra document có được share không
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this document"
        )
    
    return document


# ============================================
# Update document
# ============================================
@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    request: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cập nhật document
    """
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this document"
        )
    
    # Cập nhật fields
    if request.title is not None:
        document.title = request.title
    if request.category is not None:
        document.category = request.category
    if request.tags is not None:
        document.tags = request.tags
    
    db.commit()
    db.refresh(document)
    
    return document


# ============================================
# Delete document
# ============================================
@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Xóa document
    """
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this document"
        )
    
    db.delete(document)
    db.commit()


# ============================================
# Share document
# ============================================
@router.post("/{document_id}/share", response_model=DocumentShareResponse)
async def share_document(
    document_id: UUID,
    request: DocumentShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chia sẻ document với user khác
    """
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to share this document"
        )
    
    # Kiểm tra user được share tồn tại
    shared_user = db.query(User).filter(
        User.id == request.shared_with_user_id
    ).first()
    
    if not shared_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Kiểm tra đã share chưa
    existing_share = db.query(DocumentShare).filter(
        DocumentShare.document_id == document_id,
        DocumentShare.shared_with_user_id == request.shared_with_user_id
    ).first()
    
    if existing_share:
        # Cập nhật permission
        existing_share.permission = request.permission
        db.commit()
        db.refresh(existing_share)
        return existing_share
    
    # Tạo share mới
    new_share = DocumentShare(
        document_id=document_id,
        shared_with_user_id=request.shared_with_user_id,
        permission=request.permission
    )
    
    db.add(new_share)
    db.commit()
    db.refresh(new_share)
    
    return new_share
