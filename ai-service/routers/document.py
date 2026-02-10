"""
Document Processing Router
API endpoints cho document processing (load, split, embed, upsert)
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional
import json

from services.document_service import document_processing_service
from services.embedding_service import embedding_service


router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/process")
async def process_document(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    user_id: str = Form(...),
    metadata: Optional[str] = Form(None)  # JSON string
):
    """
    Process document: load -> split -> embed -> upsert to Qdrant
    
    Args:
        file: Upload file
        document_id: Document UUID
        user_id: User UUID
        metadata: JSON string với title, category, tags
    
    Returns:
        Processing result
    """
    try:
        # Parse metadata
        meta = json.loads(metadata) if metadata else {}
        
        # Read file bytes
        file_content = await file.read()
        
        # 1. Load document
        docs = document_processing_service.load_document_from_bytes(
            file_data=file_content,
            file_name=file.filename,
            file_type=file.content_type
        )
        
        # 2. Split into chunks
        chunks = document_processing_service.split_documents(docs)
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chunks generated from document"
            )
        
        # 3. Prepare chunks data
        chunks_data, chunk_texts = document_processing_service.prepare_chunks_data(
            chunks=chunks,
            document_id=document_id,
            user_id=user_id,
            file_name=file.filename,
            metadata=meta
        )
        
        # 4. Generate embeddings
        embeddings = embedding_service.embed_texts(
            texts=chunk_texts,
            input_type="search_document"
        )
        
        # 5. Generate chunk IDs (backend sẽ tạo trong DB, nhưng ta cần unique IDs)
        import uuid
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        
        # 6. Upsert to Qdrant
        document_processing_service.upsert_to_qdrant(
            chunk_ids=chunk_ids,
            embeddings=embeddings,
            chunks_data=chunks_data,
            metadata=meta
        )
        
        return {
            "success": True,
            "message": "Document processed successfully",
            "chunks_count": len(chunks),
            "vectors_count": len(embeddings)
        }
    
    except Exception as e:
        # Log detailed error
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Document processing error:")
        print(f"Error: {str(e)}")
        print(f"Traceback:\n{error_traceback}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {str(e)}"
        )


@router.delete("/vectors/{document_id}")
async def delete_document_vectors(document_id: str):
    """
    Delete all vectors của document từ Qdrant
    
    Args:
        document_id: Document UUID
    
    Returns:
        Deletion result
    """
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from core.qdrant import qdrant_manager
        
        # Delete by filter
        qdrant_manager.client.delete(
            collection_name=qdrant_manager.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )
        )
        
        return {
            "success": True,
            "message": f"Vectors for document {document_id} deleted"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector deletion failed: {str(e)}"
        )
