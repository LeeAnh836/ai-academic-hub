"""
API Dependencies - Shared dependencies for all API routes
Chứa các dependency dùng chung: authentication, authorization, etc.
"""
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.databases import get_db
from services.auth_service import auth_service
from models.users import User

security = HTTPBearer(auto_error=False)  # Don't auto error, we'll check cookie too


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI Dependency: Lấy thông tin user hiện tại từ JWT token
    
    Ưu tiên: 
    1. Token từ Authorization header (Bearer)
    2. Token từ HttpOnly cookie
    
    Args:
        request: Request object để đọc cookies
        credentials: HTTPAuthorizationCredentials from HTTPBearer (optional)
        db: Database session
    
    Returns:
        Current user object
        
    Raises:
        HTTPException: If token is invalid, blacklisted, or user not found
        
    Usage:
        @router.get("/protected")
        async def protected_route(current_user: CurrentUser):
            return {"user_id": current_user.id}
    """
    # Try to get token from Authorization header first
    token = None
    if credentials:
        token = credentials.credentials
    
    # If no header token, try cookie
    if not token:
        token = request.cookies.get("access_token")
    
    # If still no token, return 401
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
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
            admin: AdminUser = Depends(verify_admin)
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


# ============================================
# Type Aliases - Sử dụng Annotated để giảm code lặp
# ============================================

# CurrentUser: Authenticated user từ JWT token
CurrentUser = Annotated[User, Depends(get_current_user)]

# AdminUser: Authenticated user với role admin
AdminUser = Annotated[User, Depends(verify_admin)]
