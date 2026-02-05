"""
Authentication routes - Register, Login, Logout, Token Management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.databases import get_db
from core.config import settings
from api.dependencies import get_current_user
from services.auth_service import auth_service
from services.token_service import token_service
from models.users import User
from schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, 
    RefreshTokenRequest, LogoutRequest, MessageResponse
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# HTTP Bearer security scheme - hiển thị trong Swagger UI
security = HTTPBearer(description="Bearer token (JWT)")


# ============================================
# Register endpoint
# ============================================
@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Đăng ký tài khoản mới
    
    Args:
        request: RegisterRequest schema
        db: Database session
    
    Returns:
        Success message (KHÔNG trả token, phải login sau khi đăng ký)
    """
    result = auth_service.register_user(
        email=request.email,
        username=request.username,
        password=request.password,
        full_name=request.full_name,
        student_id=request.student_id,
        db=db
    )
    
    return {
        "message": result["message"]
    }


# ============================================
# Login endpoint
# ============================================
@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Đăng nhập
    
    Args:
        request: LoginRequest schema
        db: Database session
    
    Returns:
        Token pair
    """
    result = auth_service.login_user(
        email=request.email,
        password=request.password,
        db=db
    )
    
    return {
        "access_token": result["tokens"]["access_token"],
        "refresh_token": result["tokens"]["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ============================================
# Refresh token endpoint
# ============================================
@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Làm mới access token
    
    Args:
        request: RefreshTokenRequest schema
        db: Database session
    
    Returns:
        New access token
    """
    try:
        new_access_token = await token_service.refresh_access_token(request.refresh_token)
        
        return {
            "access_token": new_access_token,
            "refresh_token": request.refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


# ============================================
# Logout endpoint
# ============================================
@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout - thêm tokens vào blacklist
    
    Args:
        request: LogoutRequest schema
        current_user: Current user
        db: Database session
    
    Returns:
        Success message
    """
    await auth_service.logout_user(
        access_token=request.access_token,
        refresh_token=request.refresh_token,
        user_id=str(current_user.id)
    )
    
    return {"message": "Logout successful"}
