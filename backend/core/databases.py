"""
Cấu hình kết nối Database PostgreSQL
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from .config import settings

# Import all models to register them before creating tables
from models import base, users, documents, chat, groups, conversations, notifications  # noqa: F401


# Tạo engine kết nối database
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # Kiểm tra connection trước khi sử dụng
    pool_size=20,
    max_overflow=0,
)

# Tạo session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection để lấy database session
    
    Yield:
        Session: SQLAlchemy session object
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """
    Khởi tạo database - tạo tất cả tables
    """
    from models.base import Base
    
    Base.metadata.create_all(bind=engine)


async def close_db():
    """
    Đóng kết nối database
    """
    engine.dispose()
