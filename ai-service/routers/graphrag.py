"""
GraphRAG Router
API endpoints cho GraphRAG operations
"""
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import Optional, List
import json

from core.config import settings
from core.neo4j_manager import neo4j_manager
from services.document_service import document_processing_service
from services.graph_rag_service import graph_rag_service
from services.hybrid_rag_service import hybrid_rag_service


router = APIRouter(prefix="/api/graph", tags=["graphrag"])


@router.post("/index")
async def index_document_to_graph(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    user_id: str = Form(...),
    metadata: Optional[str] = Form(None)
):
    """
    Index document into knowledge graph (Neo4j)
    
    Process:
    1. Load and split document
    2. Extract entities using Gemini Flash (FREE)
    3. Build knowledge graph in Neo4j
    
    NOTE: This is separate from vector indexing (Qdrant)
    Use both /documents/process AND /graph/index for full hybrid RAG
    
    Args:
        file: Document file
        document_id: Document UUID
        user_id: User UUID
        metadata: JSON metadata
    
    Returns:
        Indexing statistics
    """
    if not settings.ENABLE_GRAPH_RAG:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphRAG is not enabled. Set ENABLE_GRAPH_RAG=true in .env"
        )
    
    if not neo4j_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j is not connected. Check Neo4j credentials in .env"
        )
    
    try:
        # Parse metadata
        meta = json.loads(metadata) if metadata else {}
        
        # Read file
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
        
        # 3. Index to graph (extract entities and build graph)
        result = await graph_rag_service.index_document_to_graph(
            document_id=document_id,
            user_id=user_id,
            chunks=chunks,
            file_name=file.filename,
            metadata=meta
        )
        
        return {
            "success": True,
            "message": "Document indexed to knowledge graph",
            **result
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Graph indexing error:")
        print(f"Error: {str(e)}")
        print(f"Traceback:\n{error_traceback}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph indexing failed: {str(e)}"
        )


@router.post("/search")
async def graph_search(
    query: str = Form(...),
    user_id: str = Form(...),
    document_ids: Optional[str] = Form(None),  # JSON array string
    top_k: int = Form(10)
):
    """
    Search knowledge graph for entities and relationships
    
    Args:
        query: Search query
        user_id: User ID
        document_ids: Optional JSON array of document IDs
        top_k: Max results
    
    Returns:
        Graph search results
    """
    if not settings.ENABLE_GRAPH_RAG or not neo4j_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphRAG is not available"
        )
    
    try:
        # Parse document_ids
        doc_ids = None
        if document_ids:
            doc_ids = json.loads(document_ids)
        
        # Search graph
        results = graph_rag_service.retrieve_graph_context(
            query=query,
            user_id=user_id,
            document_ids=doc_ids,
            top_k=top_k,
            traversal_depth=settings.GRAPH_TRAVERSAL_DEPTH
        )
        
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph search failed: {str(e)}"
        )


@router.post("/hybrid-search")
async def hybrid_search(
    query: str = Form(...),
    user_id: str = Form(...),
    document_ids: Optional[str] = Form(None),
    top_k: int = Form(5),
    score_threshold: float = Form(0.5)
):
    """
    Hybrid search combining Vector RAG + Graph RAG
    
    This combines:
    - Semantic search from Qdrant (vector similarity)
    - Entity/relationship search from Neo4j (graph traversal)
    
    Args:
        query: Search query
        user_id: User ID
        document_ids: Optional JSON array of document IDs
        top_k: Max results
        score_threshold: Min similarity score for vector search
    
    Returns:
        Combined search results
    """
    try:
        # Parse document_ids
        doc_ids = None
        if document_ids:
            doc_ids = json.loads(document_ids)
        
        # Hybrid search
        results = await hybrid_rag_service.hybrid_retrieve(
            query=query,
            user_id=user_id,
            document_ids=doc_ids,
            top_k=top_k,
            score_threshold=score_threshold
        )
        
        return {
            "success": True,
            "query": query,
            "mode": hybrid_rag_service.mode,
            "results_count": len(results),
            "results": results
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid search failed: {str(e)}"
        )


@router.delete("/document/{document_id}")
async def delete_document_graph(document_id: str):
    """
    Delete document from knowledge graph
    
    Args:
        document_id: Document UUID
    
    Returns:
        Deletion confirmation
    """
    if not settings.ENABLE_GRAPH_RAG or not neo4j_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GraphRAG is not available"
        )
    
    try:
        graph_rag_service.delete_document_graph(document_id)
        
        return {
            "success": True,
            "message": f"Document {document_id} deleted from knowledge graph"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph deletion failed: {str(e)}"
        )


@router.get("/stats")
async def get_graph_stats():
    """
    Get Neo4j knowledge graph statistics
    
    Returns:
        Graph stats (nodes, relationships, etc.)
    """
    if not settings.ENABLE_GRAPH_RAG or not neo4j_manager.enabled:
        return {
            "enabled": False,
            "message": "GraphRAG is not available"
        }
    
    try:
        stats = neo4j_manager.get_stats()
        
        return {
            "success": True,
            "stats": stats,
            "config": {
                "mode": settings.GRAPH_RAG_MODE,
                "max_entities": settings.GRAPH_MAX_ENTITIES,
                "traversal_depth": settings.GRAPH_TRAVERSAL_DEPTH
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/health")
async def graph_health_check():
    """
    Check Neo4j connection health
    
    Returns:
        Health status
    """
    return {
        "enabled": settings.ENABLE_GRAPH_RAG,
        "connected": neo4j_manager.check_connection() if neo4j_manager.enabled else False,
        "mode": settings.GRAPH_RAG_MODE,
        "uri": settings.NEO4J_URI if settings.NEO4J_URI else "Not configured"
    }
