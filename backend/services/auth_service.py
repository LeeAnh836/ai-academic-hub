"""
Authentication Service - Business Logic Layer
Xử lý các nghiệp vụ liên quan đến authentication: register, login, logout, etc.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import HTTPException, status

from models.users import User
from utils.password import hash_password, verify_password
from utils.validators import is_valid_email, is_valid_username, sanitize_string
from services.token_service import token_service
from services.user_presence import user_presence
from core.config import settings


class AuthService:
    """
    Service xử lý business logic cho authentication
    """
    
    @staticmethod
    async def get_current_user_from_token(token: str, db: Session) -> User:
        """
        Lấy thông tin user từ JWT token
        
        Args:
            token: JWT access token
            db: Database session
        
        Returns:
            User object
        
        Raises:
            HTTPException: Nếu token invalid, blacklisted, hoặc user không tồn tại
        """
        # Verify token
        try:
            payload = token_service.verify_token(token, token_type="access")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Check if token is blacklisted
        try:
            is_blacklisted = await token_service.is_token_blacklisted(token)
            if is_blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
        except Exception:
            pass  # If blacklist check fails, continue
        
        # Get user from database
        user = db.query(User).filter(User.id == payload.get("user_id")).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
    
    @staticmethod
    def register_user(
        email: str,
        username: str,
        password: str,
        full_name: str,
        student_id: str,
        db: Session
    ) -> Dict[str, any]:
        """
        Đăng ký user mới
        
        Args:
            email: Email của user
            username: Username
            password: Plain password
            full_name: Họ tên
            student_id: Mã sinh viên
            db: Database session
        
        Returns:
            Dict chứa user và tokens
        
        Raises:
            HTTPException: Nếu validation fail hoặc user đã tồn tại
        """
        # Validate email
        if not is_valid_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate username
        if not is_valid_username(username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be 3-30 characters and contain only letters, numbers, and underscores"
            )
        
        # Sanitize inputs
        email = email.lower().strip()
        username = sanitize_string(username)
        full_name = sanitize_string(full_name)
        student_id = student_id.strip().upper()
        
        # Kiểm tra email đã tồn tại
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Kiểm tra username đã tồn tại
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Kiểm tra student_id đã tồn tại
        existing_student = db.query(User).filter(User.student_id == student_id).first()
        if existing_student:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student ID already registered"
            )
        
        # Xác định role: admin nếu email trong ADMIN_EMAIL, còn lại là user
        admin_emails = settings.get_admin_emails()
        user_role = "admin" if email in admin_emails else "user"
        
        # Tạo user mới
        new_user = User(
            email=email,
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            student_id=student_id,
            is_verified=False,
            is_active=True,
            role=user_role  # Tự động gán admin nếu email trong danh sách admin
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Đăng ký xong KHÔNG tự động login, user phải gọi /login để lấy token
        return {
            "user": new_user,
            "message": "Registration successful. Please login to continue."
        }
    
    @staticmethod
    def login_user(
        email: str,
        password: str,
        db: Session
    ) -> Dict[str, any]:
        """
        Đăng nhập user
        
        Args:
            email: Email của user
            password: Plain password
            db: Database session
        
        Returns:
            Dict chứa user và tokens
        
        Raises:
            HTTPException: Nếu credentials không hợp lệ
        """
        # Sanitize email
        email = email.lower().strip()
        
        # Tìm user theo email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Kiểm tra password
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Kiểm tra user active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Cập nhật last_login_at
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        
        # Tạo token pair
        tokens = token_service.create_token_pair({
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username,
        })
        
        return {
            "user": user,
            "tokens": tokens
        }
    
    @staticmethod
    async def logout_user(
        access_token: str,
        refresh_token: str,
        user_id: str
    ) -> bool:
        """
        Logout user - blacklist tokens và mark offline
        
        Args:
            access_token: Access token cần blacklist
            refresh_token: Refresh token cần blacklist
            user_id: ID của user
        
        Returns:
            True nếu logout thành công
        
        Raises:
            HTTPException: Nếu có lỗi khi logout
        """
        try:
            # Xác minh tokens
            access_payload = token_service.verify_token(access_token, token_type="access")
            refresh_payload = token_service.verify_token(refresh_token, token_type="refresh")
            
            # Lấy expiration time từ payload
            access_expires_at = datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc)
            refresh_expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc)
            
            # Thêm tokens vào blacklist
            await token_service.blacklist_token(access_token, access_expires_at)
            await token_service.blacklist_token(refresh_token, refresh_expires_at)
            
            # Đánh dấu user offline
            await user_presence.mark_user_offline(user_id)
            
            return True
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Logout failed: {str(e)}"
            )
    
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
    def verify_user_token(token: str, token_type: str = "access") -> Dict[str, any]:
        """
        Verify JWT token và lấy payload
        
        Args:
            token: JWT token
            token_type: Loại token ("access" hoặc "refresh")
        
        Returns:
            Payload dict
        
        Raises:
            HTTPException: Nếu token invalid
        """
        return token_service.verify_token(token, token_type=token_type)


# Global auth service instance
auth_service = AuthService()
