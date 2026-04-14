"""
Document Processing Router
API endpoints cho document processing (load, split, embed, upsert)
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional
import json

from services.document_service import document_processing_service
from services.embedding_service import embedding_service
from services.graph_rag_service import graph_rag_service
from core.config import settings


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
        import logging
        logger = logging.getLogger(__name__)
        
        # Parse metadata
        meta = json.loads(metadata) if metadata else {}
        
        # Read file bytes
        file_content = await file.read()
        
        logger.info(f"📥 Processing document: name={file.filename}, type={file.content_type}, "
                     f"size={len(file_content)/1024:.1f}KB, doc_id={document_id}")
        
        # 1. Load document (includes OCR for images/scanned PDFs)
        docs = document_processing_service.load_document_from_bytes(
            file_data=file_content,
            file_name=file.filename,
            file_type=file.content_type
        )
        
        logger.info(f"📄 Loaded {len(docs)} document(s) from '{file.filename}'")
        
        # 2. Split into chunks
        chunks = document_processing_service.split_documents(docs)
        
        logger.info(f"🔪 Split into {len(chunks)} chunks from '{file.filename}'")
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No chunks generated from document '{file.filename}' (type={file.content_type}). "
                       f"Loaded {len(docs)} raw documents but all were empty after splitting."
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
        
        # 7. Index to Neo4j for GraphRAG (only when enabled)
        graph_stats = {}
        if settings.ENABLE_GRAPH_RAG and settings.ENABLE_NEO4J:
            try:
                graph_stats = await graph_rag_service.index_document_to_graph(
                    document_id=document_id,
                    user_id=user_id,
                    chunks=chunks,
                    file_name=file.filename,
                    metadata=meta
                )
                print(f"✅ Graph indexed: {graph_stats.get('entities_extracted', 0)} entities, "
                      f"{graph_stats.get('relationships_created', 0)} relationships")
            except Exception as graph_err:
                # Graph indexing failure must NOT block Qdrant result
                print(f"⚠️ Graph indexing skipped (non-fatal): {graph_err}")
                graph_stats = {"error": str(graph_err)}
        
        # 8. Return chunk data to Backend for PostgreSQL storage
        chunks_for_backend = [
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk_data["chunk_index"],
                "chunk_text": chunk_data["chunk_text"],
                "chunk_metadata": chunk_data.get("chunk_metadata", {}),
                "token_count": chunk_data["token_count"]
            }
            for chunk_id, chunk_data in zip(chunk_ids, chunks_data)
        ]
        
        return {
            "success": True,
            "message": "Document processed successfully",
            "chunks_count": len(chunks),
            "vectors_count": len(embeddings),
            "graph_indexed": bool(graph_stats.get("success")),
            "graph_stats": graph_stats,
            "chunks": chunks_for_backend  # ← TRẢ VỀ CHUNK DATA
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
