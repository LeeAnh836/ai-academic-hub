"""
AI Service Configuration
Cấu hình cho AI Service - xử lý embedding, RAG, LLM
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Cấu hình AI Service - Load từ .env file"""
    
    # Service Info
    SERVICE_NAME: str = "JVB AI Service"
    SERVICE_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = True
    
    # Qdrant Settings (Vector Database)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "jvb_embeddings"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_GRPC_PORT: int = 6334
    
    # Cohere Settings (Embeddings & LLM)
    COHERE_API_KEY: str
    COHERE_EMBEDDING_MODEL: str = "embed-multilingual-v3.0"
    COHERE_LLM_MODEL: str = "command-r-plus"
    VECTOR_DIMENSION: int = 1024
    
    # RAG Settings
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.7
    RAG_MAX_CONTEXT_LENGTH: int = 8000
    
    # LLM Settings
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 60
    
    # Chunking Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # CORS Settings
    CORS_ORIGINS: str = "*"
    
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
