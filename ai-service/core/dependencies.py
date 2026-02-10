"""
FastAPI Dependencies
Các dependency dùng chung cho AI Service
"""
from fastapi import HTTPException, status
from typing import Optional


def validate_api_key(api_key: Optional[str] = None):
    """
    Validate API key nếu cần bảo mật giữa backend và ai-service
    Hiện tại cho phép tất cả requests (internal network)
    """
    # TODO: Thêm API key validation nếu expose ra ngoài
    pass


def get_qdrant_client():
    """
    Get Qdrant client instance
    """
    from core.qdrant import qdrant_manager
    
    if not qdrant_manager.client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant service not available"
        )
    
    return qdrant_manager.client
