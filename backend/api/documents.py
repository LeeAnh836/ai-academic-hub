"""
Document routes - CRUD operations
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import hashlib
import os
import re

from core.databases import get_db
from api.dependencies import get_current_user, CurrentUser
from schemas.document import (
    DocumentResponse, DocumentCreateRequest, DocumentUpdateRequest,
    DocumentShareRequest, DocumentShareResponse, DocumentDetailResponse
)
from models.users import User
from models.documents import Document, DocumentShare
from services.minio_service import minio_service
from services.ai_service import ai_service

router = APIRouter(
    prefix="/api/documents", 
    tags=["documents"],
    dependencies=[Depends(get_current_user)]  # Apply authentication to all endpoints
)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif"}
SPREADSHEET_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CODE_EXTENSIONS = {
    ".py", ".java", ".js", ".ts", ".tsx", ".jsx", ".cpp", ".c", ".h", ".hpp",
    ".go", ".rs", ".html", ".css", ".md", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh"
}
IMAGE_MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/gif": ".gif",
}


def _looks_like_generic_image_name(stem: str) -> bool:
    normalized = re.sub(r"\s+", " ", (stem or "").strip().lower())
    normalized = re.sub(r"\s*\(\d+\)$", "", normalized)
    return bool(re.match(r"^(image|img|screenshot|pasted image)([-_ ]?\d+)?$", normalized))


def _normalize_upload_filename(file_name: Optional[str], content_type: Optional[str]) -> str:
    raw_name = os.path.basename((file_name or "").strip()) or "upload"
    stem, ext = os.path.splitext(raw_name)
    ext = ext.lower()

    inferred_ext = IMAGE_MIME_TO_EXT.get((content_type or "").lower(), "")
    if not ext and inferred_ext:
        ext = inferred_ext

    is_image = ((content_type or "").lower().startswith("image/") or ext in IMAGE_EXTENSIONS)
    if is_image and _looks_like_generic_image_name(stem):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_id = uuid4().hex[:8]
        final_ext = ext or inferred_ext or ".png"
        return f"image_{ts}_{short_id}{final_ext}"

    return raw_name if ext else f"{raw_name}{inferred_ext}"


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
    current_user: CurrentUser,
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
# Batch processing status check
# ============================================
@router.get("/batch-status")
async def get_batch_document_status(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    document_ids: str = Query(..., description="Comma-separated document IDs"),
):
    """
    Kiểm tra trạng thái xử lý của nhiều documents cùng lúc.
    Trả về danh sách {id, is_processed, processing_status}.
    """
    ids_raw = [i.strip() for i in document_ids.split(",") if i.strip()]
    if not ids_raw:
        return []

    try:
        parsed_ids = [UUID(i) for i in ids_raw]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    docs = db.query(Document).filter(
        Document.id.in_(parsed_ids),
        Document.user_id == current_user.id
    ).all()

    return [
        {
            "id": str(doc.id),
            "is_processed": doc.is_processed,
            "processing_status": doc.processing_status
        }
        for doc in docs
    ]


# ============================================
# Upload document file
# ============================================
@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # JSON string: '["tag1", "tag2"]'
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
        "text/plain",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/html",
        "text/javascript",
        "text/x-python",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/jpg"
    ]
    
    normalized_file_name = _normalize_upload_filename(file.filename, file.content_type)
    ext = os.path.splitext(normalized_file_name)[1].lower()
    is_image_upload = ((file.content_type or "").startswith("image/") or ext in IMAGE_EXTENSIONS)

    allowed_exts = ['.pdf', '.docx', '.txt', '.csv', '.xlsx', '.xls', '.py', '.java', '.js', '.ts', '.html', '.css', '.md', '.cpp', '.jpg', '.jpeg', '.png', '.webp', '.heic']
    
    if file.content_type not in allowed_types and ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} (ext {ext}) not supported. Allowed: PDF, DOCX, TXT, CSV, Code, Tables"
        )

    # Validate file size (max 20 MB)
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB in bytes
    
    try:
        # 1. Read file and compute content hash (dedup key)
        file_data = await file.read()
        content_hash = hashlib.sha256(file_data).hexdigest()

        if len(file_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File quá lớn. Kích thước tối đa là 20 MB (file hiện tại: {len(file_data) / (1024*1024):.1f} MB)"
            )
        
        # 2. Auto-detect category if not provided
        detected_category = category
        if not detected_category:
            content_type = (file.content_type or "").lower()

            # Auto-detect based on MIME + extension
            if ext in SPREADSHEET_EXTENSIONS or content_type in {
                "text/csv",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }:
                detected_category = "csv"
            elif ext in CODE_EXTENSIONS or content_type in {
                "text/javascript",
                "application/javascript",
                "text/x-python",
                "application/x-python-code",
            }:
                detected_category = "code"
            elif file.content_type == "application/pdf" or ext == ".pdf":
                detected_category = "document"
            elif (
                file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                or ext in {".doc", ".docx"}
            ):
                detected_category = "document"
            elif content_type.startswith("image/"):
                detected_category = "image"
            elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.heic']:
                detected_category = "image"
            elif content_type.startswith("text/") or ext in {".txt", ".md"}:
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

        # 4. Dedup lookup within the same user: if same hash already processed,
        # reuse canonical vectors/chunks and skip re-embedding.
        # NOTE: images are intentionally processed separately so each upload
        # has its own document_id/source identity for citations.
        existing_processed = None
        if not is_image_upload:
            existing_processed = db.query(Document).filter(
                Document.user_id == current_user.id,
                Document.content_hash == content_hash,
                Document.is_processed == True,
                Document.processing_status == "completed"
            ).order_by(Document.created_at.asc()).first()

        if existing_processed:
            canonical_id = existing_processed.canonical_document_id or existing_processed.id
            dedup_document = Document(
                user_id=current_user.id,
                title=title or normalized_file_name,
                file_name=normalized_file_name,
                # Reuse physical object to avoid duplicate MinIO storage.
                file_path=existing_processed.file_path,
                content_hash=content_hash,
                canonical_document_id=canonical_id,
                file_size=existing_processed.file_size,
                file_type=existing_processed.file_type,
                category=detected_category,
                tags=parsed_tags,
                is_processed=True,
                processing_status="completed"
            )
            db.add(dedup_document)
            db.commit()
            db.refresh(dedup_document)
            return dedup_document

        # 5. Upload new file to MinIO (no dedup match)
        upload_result = minio_service.upload_file(
            file_data=file_data,
            file_name=normalized_file_name,
            content_type=file.content_type,
            user_id=str(current_user.id)
        )
        
        # 6. Create document record in PostgreSQL
        new_document = Document(
            user_id=current_user.id,
            title=title or normalized_file_name,  # Auto-use filename if no title
            file_name=normalized_file_name,
            file_path=upload_result["file_path"],
            content_hash=content_hash,
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

        # Canonical document for newly processed file is itself.
        new_document.canonical_document_id = new_document.id
        db.commit()
        db.refresh(new_document)
        
        # 7. Trigger background task to process document
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
    current_user: CurrentUser,
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
        from urllib.parse import quote
        encoded_name = quote(document.file_name, safe='')
        return StreamingResponse(
            BytesIO(file_data),
            media_type=document.file_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )


# ============================================
# Preview document file (inline – no force download)
# ============================================
@router.get("/{document_id}/preview")
async def preview_document(
    document_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Serve file inline (for browser preview, no Content-Disposition: attachment)
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

    if document.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this document"
        )

    try:
        object_name = document.file_path.split("/", 1)[1]
        file_data = minio_service.download_file(object_name)

        from io import BytesIO
        from urllib.parse import quote
        encoded_name = quote(document.file_name, safe='')
        return StreamingResponse(
            BytesIO(file_data),
            media_type=document.file_type,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                "Cache-Control": "private, max-age=300",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(e)}"
        )


# ============================================
# Get document detail
# ============================================
@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
        canonical_id = document.canonical_document_id or document.id

        # 1. Delete vectors only when this is the last document referencing
        # the canonical vector set.
        remaining_canonical_refs = db.query(Document).filter(
            Document.id != document.id,
            Document.canonical_document_id == canonical_id,
        ).count()
        if document.is_processed and remaining_canonical_refs == 0:
            await ai_service.delete_document_vectors(canonical_id, db)

        # 2. Delete file object only when no other document references it.
        remaining_file_refs = db.query(Document).filter(
            Document.id != document.id,
            Document.file_path == document.file_path,
        ).count()
        if remaining_file_refs == 0:
            object_name = document.file_path.split("/", 1)[1]
            minio_service.delete_file(object_name)

        # 3. Delete from PostgreSQL (cascade deletes chunks & embeddings of this row)
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
    current_user: CurrentUser,
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
