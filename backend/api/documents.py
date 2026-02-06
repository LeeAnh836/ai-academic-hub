"""
Document routes - CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from core.databases import get_db
from api.dependencies import get_current_user
from schemas.document import (
    DocumentResponse, DocumentCreateRequest, DocumentUpdateRequest,
    DocumentShareRequest, DocumentShareResponse, DocumentDetailResponse
)
from models.users import User
from models.documents import Document, DocumentShare
from services.minio_service import minio_service
from services.ai_service import ai_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ============================================
# Helper function for background processing
# ============================================
def process_document_background(document_id: UUID):
    """
    Wrapper function to process document in background with new DB session
    """
    from core.databases import SessionLocal
    
    db = SessionLocal()
    try:
        ai_service.process_document(document_id, db)
    except Exception as e:
        print(f"❌ Background processing error: {e}")
    finally:
        db.close()


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
# Upload document file
# ============================================
@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string: '["tag1", "tag2"]'
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload tài liệu: Upload file lên MinIO, lưu metadata vào PostgreSQL, 
    và trigger background task để xử lý AI (split, embed, lưu Qdrant)
    
    Args:
        file: File upload (REQUIRED)
        title: Tiêu đề (OPTIONAL - mặc định dùng file name)
        category: Category (OPTIONAL - auto-detect từ file type)
        tags: Tags (OPTIONAL - có thể để trống, JSON string: '["tag1", "tag2"]')
        
    Note: Chỉ cần upload file! Metadata sẽ tự động được điền hoặc có thể edit sau.
    
    Returns:
        DocumentResponse với metadata và processing status
        category: Category
        tags: Tags (JSON string)
    """
    import json
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not supported. Allowed: PDF, DOCX, TXT"
        )
    
    try:
        # 1. Upload file to MinIO
        file_data = await file.read()
        upload_result = minio_service.upload_file(
            file_data=file_data,
            file_name=file.filename,
            content_type=file.content_type,
            user_id=str(current_user.id)
        )
        
        # 2. Auto-detect category if not provided
        detected_category = category
        if not detected_category:
            # Auto-detect based on file type
            if file.content_type == "application/pdf":
                detected_category = "document"
            elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                detected_category = "document"
            elif file.content_type == "text/plain":
                # Try to detect from extension
                if file.filename.endswith(('.py', '.js', '.java', '.cpp', '.c', '.go', '.rs')):
                    detected_category = "code"
                else:
                    detected_category = "text"
            else:
                detected_category = "general"
        
        # 3. Parse tags (optional)
        parsed_tags = []
        if tags:
            try:
                parsed_tags = json.loads(tags)
            except:
                parsed_tags = [tag.strip() for tag in tags.split(",")]
        
        # 4. Create document record in PostgreSQL
        new_document = Document(
            user_id=current_user.id,
            title=title or file.filename,  # Auto-use filename if no title
            file_name=file.filename,
            file_path=upload_result["file_path"],
            file_size=upload_result["size"],
            file_type=file.content_type,
            category=detected_category,  # Auto-detected or user-provided
            tags=parsed_tags,  # Optional - can be empty
            is_processed=False,
            processing_status="pending"
        )
        
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        
        # 5. Trigger background task to process document
        # Use wrapper function to create new DB session for background task
        background_tasks.add_task(
            process_document_background,
            document_id=new_document.id
        )
        
        return new_document
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


# ============================================
# Download document file
# ============================================
@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download file gốc từ MinIO
    """
    from fastapi.responses import StreamingResponse
    
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
    
    try:
        # Get object name from file_path (remove bucket prefix)
        object_name = document.file_path.split("/", 1)[1]
        
        # Download from MinIO
        file_data = minio_service.download_file(object_name)
        
        # Return as streaming response
        from io import BytesIO
        return StreamingResponse(
            BytesIO(file_data),
            media_type=document.file_type,
            headers={
                "Content-Disposition": f'attachment; filename="{document.file_name}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )


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
    Xóa document (bao gồm file từ MinIO và vectors từ Qdrant)
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
    
    try:
        # 1. Delete vectors from Qdrant (if processed)
        if document.is_processed:
            ai_service.delete_document_vectors(document_id, db)
        
        # 2. Delete file from MinIO
        object_name = document.file_path.split("/", 1)[1]  # Remove bucket name
        minio_service.delete_file(object_name)
        
        # 3. Delete from PostgreSQL (cascade will delete chunks & embeddings)
        db.delete(document)
        db.commit()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


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
