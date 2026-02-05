"""
FastAPI main application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.databases import init_db, close_db
from core.redis import redis_blacklist
from services.token_service import token_service
from services.user_presence import user_presence
from api.auth import router as auth_router
from api.users import router as users_router
from api.documents import router as documents_router
from api.chat import router as chat_router
from api.groups import router as groups_router


# ============================================
# Lifespan Events
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Quản lý vòng đời ứng dụng
    """
    # Startup
    print("🚀 Starting up application...")
    await init_db()
    await redis_blacklist.connect()
    await user_presence.connect()
    print("✅ Database initialized")
    print("✅ Redis blacklist connected")
    print("✅ User presence tracker connected")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down application...")
    await user_presence.disconnect()
    await redis_blacklist.disconnect()
    await close_db()
    print("✅ Resources cleaned up")


# ============================================
# Create FastAPI Application
# ============================================
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan
)


# ============================================
# CORS Middleware
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




app.include_router(auth_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(groups_router)


# ============================================
# Routes
# ============================================
@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": settings.API_TITLE,
        "version": settings.API_VERSION
    }


@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "message": "Welcome to JVB API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


# ============================================
# Error Handlers
# ============================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler
    """
    from fastapi.responses import JSONResponse
    import traceback
    
    print(f"❌ Unhandled exception: {exc}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "status_code": 500
        }
    )


# ============================================
# Run Application
# ============================================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
