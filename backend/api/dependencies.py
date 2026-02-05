"""
API Dependencies - Shared dependencies for all API routes
Chứa các dependency dùng chung: authentication, authorization, etc.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.databases import get_db
from services.auth_service import auth_service
from models.users import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI Dependency: Lấy thông tin user hiện tại từ JWT token
    
    Args:
        credentials: HTTPAuthorizationCredentials from HTTPBearer
        db: Database session
    
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid, blacklisted, or user not found
        
    Usage:
        @router.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}
    """
    token = credentials.credentials
    return await auth_service.get_current_user_from_token(token, db)


def verify_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI Dependency: Kiểm tra user có role admin không
    
    Args:
        current_user: User object từ get_current_user dependency
    
    Returns:
        Current user object (nếu là admin)
        
    Raises:
        HTTPException 403: Nếu user không phải admin
        
    Usage:
        @router.delete("/admin/users/{user_id}")
        def delete_user(
            user_id: str,
            admin: User = Depends(verify_admin)
        ):
            # Chỉ admin mới vào được đây
            return {"message": "User deleted"}
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user
