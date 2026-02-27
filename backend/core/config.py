"""
Cấu hình ứng dụng FastAPI
"""
from pydantic_settings import BaseSettings
from datetime import timedelta
from typing import Optional
import json


class Settings(BaseSettings):
    """Cấu hình chính của ứng dụng - Load từ .env file"""
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    REDIS_BLACKLIST_DB: int
    
    # JWT Settings (⚠️ KHÔNG hardcode SECRET_KEY - phải từ .env)
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    
    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Cookie Settings for JWT
    COOKIE_SECURE: bool = False  # Set to True in production with HTTPS
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"  # 'lax', 'strict', or 'none'
    COOKIE_DOMAIN: Optional[str] = None  # None = current domain
    
    # API Settings
    API_TITLE: str = "JVB API"
    API_DESCRIPTION: str = "AI-powered Java Virtual Bot API"
    API_VERSION: str = "1.0.0"
    
    # Admin Settings - Parse JSON string from .env
    ADMIN_EMAIL: str = '[]'
    
    def get_admin_emails(self) -> list[str]:
        """Parse ADMIN_EMAIL JSON string to list"""
        try:
            if isinstance(self.ADMIN_EMAIL, list):
                return self.ADMIN_EMAIL
            return json.loads(self.ADMIN_EMAIL)
        except Exception:
            return []
    
    # CORS Settings - string from .env, convert to list
    CORS_ORIGINS: str = "*"
    
    # Server Settings
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # MinIO Settings (Object Storage)
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_NAME: str = "jvb-documents"
    MINIO_SECURE: bool = False
    MINIO_URL: str  # Public URL for accessing uploaded files (e.g., http://localhost:9000)
    
    # Qdrant Settings (Vector Database)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "jvb_embeddings"
    QDRANT_API_KEY: Optional[str] = None
    
    # Cohere Settings (Embeddings)
    COHERE_API_KEY: str
    COHERE_EMBEDDING_MODEL: str = "embed-multilingual-v3.0"
    VECTOR_DIMENSION: int = 1024
    
    # AI Service URL (Microservice)
    AI_SERVICE_URL: str = "http://ai-service:8001"
    
    def get_cors_origins(self) -> list[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
