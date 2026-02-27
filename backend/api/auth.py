"""
Authentication routes - Register, Login, Logout, Token Management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer
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
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Đăng nhập - Set tokens vào HttpOnly cookies
    
    Args:
        request: LoginRequest schema
        response: Response object để set cookies
        db: Database session
    
    Returns:
        Token pair (cũng set vào cookies)
    """
    result = await auth_service.login_user(
        email=request.email,
        password=request.password,
        db=db
    )
    
    access_token = result["tokens"]["access_token"]
    refresh_token = result["tokens"]["refresh_token"]
    
    # Set access token cookie (expires in 15 minutes)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN
    )
    
    # Set refresh token cookie (expires in 7 days)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ============================================
# Refresh token endpoint
# ============================================
@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request_obj: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Làm mới access token - Đọc refresh token từ cookie hoặc body
    
    Args:
        request_obj: Request object để đọc cookies
        response: Response object để set cookies mới
        db: Database session
    
    Returns:
        New access token
    """
    try:
        # Lấy refresh token từ cookie trước, nếu không có thì từ body (backward compatible)
        refresh_token = request_obj.cookies.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        
        new_access_token = await token_service.refresh_access_token(refresh_token)
        
        # Set new access token cookie
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=settings.COOKIE_HTTPONLY,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            domain=settings.COOKIE_DOMAIN
        )
        
        return {
            "access_token": new_access_token,
            "refresh_token": refresh_token,
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
    request_obj: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout - thêm tokens vào blacklist và xóa cookies
    
    Tự động lấy access_token từ cookie hoặc header.
    
    Args:
        request_obj: Request object để đọc cookies
        response: Response object để xóa cookies
        current_user: Current user (tự động lấy từ token)
        db: Database session
    
    Returns:
        Success message
    """
    # Lấy access_token từ cookie hoặc header (get_current_user đã verify)
    access_token = request_obj.cookies.get("access_token")
    if not access_token:
        # Try header if cookie not found
        auth_header = request_obj.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
    
    # Lấy refresh_token từ cookie (nếu có)
    refresh_token = request_obj.cookies.get("refresh_token")
    
    if access_token:
        await auth_service.logout_user(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(current_user.id)
        )
    
    # Clear cookies
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key="refresh_token", domain=settings.COOKIE_DOMAIN)
    
    return {"message": "Logout successful"}
