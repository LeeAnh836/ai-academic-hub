"""
AI Service - FastAPI Application
Microservice xử lý AI operations: Embeddings, RAG, Document Processing
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from core.config import settings
from core.qdrant import qdrant_manager
from core.memory import memory_manager
from routers import embedding, rag, document

# Import GraphRAG router if enabled
try:
    from routers import graphrag
    from core.neo4j_manager import neo4j_manager
    GRAPHRAG_AVAILABLE = True
except ImportError:
    GRAPHRAG_AVAILABLE = False
    print("⚠️ GraphRAG router not available")

# Import new multi-agent router
try:
    from routers import agent
    MULTI_AGENT_ENABLED = True
except ImportError:
    MULTI_AGENT_ENABLED = False
    print("⚠️ Multi-Agent router not available")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - startup and shutdown"""
    # Startup
    print("=" * 60)
    print(f"🚀 Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")
    print("=" * 60)
    
    # Connect to Qdrant
    print("📦 Connecting to Qdrant...")
    qdrant_manager.connect()
    
    # Connect to Neo4j (if enabled)
    if GRAPHRAG_AVAILABLE and settings.ENABLE_GRAPH_RAG:
        print("🕸️ Connecting to Neo4j...")
        try:
            neo4j_manager.connect()
            if neo4j_manager.enabled:
                print("✅ Neo4j GraphRAG ready")
        except Exception as e:
            print(f"⚠️ Neo4j connection failed: {e}")
            print("💡 GraphRAG will be disabled. Vector RAG will still work.")
    
    # Connect to Redis (Memory Manager)
    if settings.ENABLE_MULTI_AGENT:
        print("💾 Connecting to Redis Memory...")
        memory_manager.connect()
        
        if memory_manager.enabled:
            print("✅ Redis Memory Manager ready")
        else:
            print("⚠️ Redis unavailable - Memory features disabled")
    
    print("✅ AI Service started successfully!")
    print(f"📡 Listening on {settings.HOST}:{settings.PORT}")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Service...")
    qdrant_manager.disconnect()
    
    if GRAPHRAG_AVAILABLE and settings.ENABLE_GRAPH_RAG:
        neo4j_manager.disconnect()
    
    if settings.ENABLE_MULTI_AGENT:
        memory_manager.disconnect()
    
    print("👋 AI Service stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="AI Processing Service - Embeddings, RAG, Document Processing",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(embedding.router)
app.include_router(rag.router)
app.include_router(document.router)

# Include GraphRAG router if available
if GRAPHRAG_AVAILABLE:
    app.include_router(graphrag.router)
    print("✅ GraphRAG API enabled")

# Include Multi-Agent router if available
if MULTI_AGENT_ENABLED:
    app.include_router(agent.router)
    print("✅ Multi-Agent API enabled")


# ============================================
# Health Check
# ============================================
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Qdrant connection
        qdrant_status = "healthy"
        try:
            qdrant_manager.client.get_collections()
        except:
            qdrant_status = "unhealthy"
        
        # Check Cohere (basic check)
        cohere_status = "configured" if settings.COHERE_API_KEY else "not_configured"
        
        return {
            "status": "healthy" if qdrant_status == "healthy" else "degraded",
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "qdrant_status": qdrant_status,
            "cohere_status": cohere_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
