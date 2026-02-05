"""
User Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến user: profile, settings, etc.
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict
from fastapi import HTTPException, status

from models.users import User, UserSettings
from utils.validators import is_valid_email, sanitize_string


class UserService:
    """
    Service xử lý business logic cho user management
    """
    
    @staticmethod
    def get_user_by_id(user_id: str, db: Session) -> Optional[User]:
        """
        Lấy user theo ID
        
        Args:
            user_id: ID của user
            db: Database session
        
        Returns:
            User object hoặc None
        """
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(email: str, db: Session) -> Optional[User]:
        """
        Lấy user theo email
        
        Args:
            email: Email của user
            db: Database session
        
        Returns:
            User object hoặc None
        """
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def update_user_profile(
        user_id: str,
        full_name: Optional[str],
        db: Session
    ) -> User:
        """
        Cập nhật thông tin profile của user
        Lưu ý: EMAIL KHÔNG ĐƯỢC CẬP NHẬT vì là định danh tài khoản
        
        Args:
            user_id: ID của user
            full_name: Họ tên mới (optional)
            db: Database session
        
        Returns:
            User object đã cập nhật
        
        Raises:
            HTTPException: Nếu user không tồn tại
        """
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Cập nhật full_name
        if full_name is not None:
            user.full_name = sanitize_string(full_name)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_user_settings(user_id: str, db: Session) -> UserSettings:
        """
        Lấy settings của user (tạo mới nếu chưa có)
        
        Args:
            user_id: ID của user
            db: Database session
        
        Returns:
            UserSettings object
        """
        settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()
        
        if not settings:
            # Tạo default settings nếu chưa có
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        
        return settings
    
    @staticmethod
    def update_user_settings(
        user_id: str,
        theme: Optional[str],
        language: Optional[str],
        notifications_enabled: Optional[bool],
        email_notifications: Optional[bool],
        two_factor_enabled: Optional[bool],
        db: Session
    ) -> UserSettings:
        """
        Cập nhật settings của user
        
        Args:
            user_id: ID của user
            theme: Theme (light/dark)
            language: Ngôn ngữ (vi/en)
            notifications_enabled: Bật/tắt notifications
            email_notifications: Bật/tắt email notifications
            two_factor_enabled: Bật/tắt 2FA
            db: Database session
        
        Returns:
            UserSettings object đã cập nhật
        """
        settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()
        
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
        
        # Cập nhật các fields
        if theme is not None:
            settings.theme = theme
        if language is not None:
            settings.language = language
        if notifications_enabled is not None:
            settings.notifications_enabled = notifications_enabled
        if email_notifications is not None:
            settings.email_notifications = email_notifications
        if two_factor_enabled is not None:
            settings.two_factor_enabled = two_factor_enabled
        
        db.commit()
        db.refresh(settings)
        
        return settings
    
    @staticmethod
    def deactivate_user(user_id: str, db: Session) -> bool:
        """
        Vô hiệu hóa user account
        
        Args:
            user_id: ID của user
            db: Database session
        
        Returns:
            True nếu thành công
        
        Raises:
            HTTPException: Nếu user không tồn tại
        """
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = False
        db.commit()
        
        return True
    
    @staticmethod
    def activate_user(user_id: str, db: Session) -> bool:
        """
        Kích hoạt user account
        
        Args:
            user_id: ID của user
            db: Database session
        
        Returns:
            True nếu thành công
        
        Raises:
            HTTPException: Nếu user không tồn tại
        """
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = True
        db.commit()
        
        return True


# Global user service instance
user_service = UserService()
