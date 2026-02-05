"""
User routes - Profile, Settings
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.databases import get_db
from api.dependencies import get_current_user
from services.user_service import user_service
from schemas.user import UserResponse, UserUpdateRequest, UserSettingsResponse, UserSettingsUpdateRequest
from models.users import User

router = APIRouter(prefix="/api/users", tags=["users"])


# ============================================
# Get current user
# ============================================
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin user hiện tại
    """
    return current_user


# ============================================
# Update current user
# ============================================
@router.put("/me", response_model=UserResponse)
async def update_current_user(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cập nhật thông tin user hiện tại
    Lưu ý: KHÔNG cho phép thay đổi email (email là tài khoản đăng nhập)
    """
    updated_user = user_service.update_user_profile(
        user_id=str(current_user.id),
        full_name=request.full_name,
        db=db
    )
    
    return updated_user


# ============================================
# Get user by ID
# ============================================
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy thông tin user theo ID (public profile)
    """
    user = user_service.get_user_by_id(user_id, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


# ============================================
# Get current user settings
# ============================================
@router.get("/me/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy cài đặt của user hiện tại
    """
    settings = user_service.get_user_settings(str(current_user.id), db)
    return settings


# ============================================
# Update current user settings
# ============================================
@router.put("/me/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    request: UserSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cập nhật cài đặt của user hiện tại
    """
    settings = user_service.update_user_settings(
        user_id=str(current_user.id),
        theme=request.theme,
        language=request.language,
        notifications_enabled=request.notifications_enabled,
        email_notifications=request.email_notifications,
        two_factor_enabled=request.two_factor_enabled,
        db=db
    )
    
    return settings
