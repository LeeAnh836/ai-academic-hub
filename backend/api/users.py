"""
User routes - Profile, Settings
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from core.databases import get_db
from api.dependencies import get_current_user, CurrentUser
from services.user_service import user_service
from services.minio_service import minio_service
from schemas.user import UserResponse, UserUpdateRequest, UserSettingsResponse, UserSettingsUpdateRequest, ChangePasswordRequest
from models.users import User

router = APIRouter(
    prefix="/api/users", 
    tags=["users"],
    dependencies=[Depends(get_current_user)]  # Apply authentication to all endpoints
)


# ============================================
# Get current user
# ============================================
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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


# ============================================
# Change password
# ============================================
@router.post("/me/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """
    Đổi mật khẩu của user hiện tại
    """
    try:
        user_service.change_password(
            user_id=str(current_user.id),
            current_password=request.current_password,
            new_password=request.new_password,
            db=db
        )
        return {"message": "Password changed successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )


# ============================================
# Upload avatar
# ============================================
@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload avatar cho user hiện tại
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Validate file size (5MB max)
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5MB limit"
        )
    
    try:
        # Upload to MinIO
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        object_name = f"avatars/{current_user.id}.{file_extension}"
        
        avatar_url = minio_service.upload_file_bytes(
            file_content=file_content,
            object_name=object_name,
            content_type=file.content_type
        )
        
        # Update user avatar URL
        updated_user = user_service.update_avatar(
            user_id=str(current_user.id),
            avatar_url=avatar_url,
            db=db
        )
        
        return updated_user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload avatar: {str(e)}"
        )
