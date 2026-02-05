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
