"""
Dịch vụ xử lý JWT Access Token và Refresh Token
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from fastapi import HTTPException, status

from core.config import settings
from core.redis import redis_blacklist
from utils.jwt import encode_jwt, decode_jwt
from schemas.jwt import JWTUserData, JWTAccessPayload, JWTRefreshPayload, TokenPair, create_jwt_user_data


class TokenService:
    """
    Dịch vụ quản lý JWT tokens (Access Token & Refresh Token)
    """
    
    @staticmethod
    def create_access_token(
        data: JWTUserData,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Tạo Access Token
        
        Args:
            data: Dict chứa payload (user_id, email, etc.)
            expires_delta: Thời gian hết hạn (nếu None dùng mặc định)
        
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        to_encode["type"] = "access"
        
        if not expires_delta:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        return encode_jwt(
            payload=to_encode,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
            expires_delta=expires_delta
        )
    
    @staticmethod
    def create_refresh_token(
        data: JWTUserData,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Tạo Refresh Token
        
        Args:
            data: Dict chứa payload (user_id, email, etc.)
            expires_delta: Thời gian hết hạn (nếu None dùng mặc định)
        
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        to_encode["type"] = "refresh"
        
        if not expires_delta:
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        return encode_jwt(
            payload=to_encode,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
            expires_delta=expires_delta
        )
    
    @staticmethod
    async def create_token_pair(data: JWTUserData) -> TokenPair:
        """
        Tạo cặp Access Token & Refresh Token + Store mapping trong Redis
        
        Args:
            data: Dict chứa payload (user_id, email, etc.)
        
        Returns:
            Dict chứa access_token và refresh_token
        """
        access_token = TokenService.create_access_token(data)
        refresh_token = TokenService.create_refresh_token(data)
        
        # Store token pair mapping trong Redis để có thể blacklist refresh token khi logout
        from datetime import timedelta
        from core.config import settings
        from core.redis import redis_blacklist
        
        refresh_ttl = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await redis_blacklist.store_token_pair(access_token, refresh_token, refresh_ttl)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Union[JWTAccessPayload, JWTRefreshPayload]:
        """
        Xác minh và giải mã token
        
        Args:
            token: JWT token string
            token_type: Loại token ("access" hoặc "refresh")
        
        Returns:
            Payload của token
        
        Raises:
            HTTPException: Nếu token không hợp lệ
        """
        payload = decode_jwt(
            token=token,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Kiểm tra loại token
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return payload
    
    @staticmethod
    async def is_token_blacklisted(token: str) -> bool:
        """
        Kiểm tra token có bị blacklist không
        
        Args:
            token: JWT token string
        
        Returns:
            True nếu token bị blacklist
        """
        return await redis_blacklist.is_blacklisted(token)
    
    @staticmethod
    async def blacklist_token(
        token: str,
        expires_at: datetime
    ) -> bool:
        """
        Thêm token vào blacklist khi logout
        
        Args:
            token: JWT token string
            expires_at: Thời gian token hết hạn
        
        Returns:
            True nếu thêm vào blacklist thành công
        """
        # Tính TTL (thời gian từ giờ đến khi token hết hạn)
        now = datetime.now(timezone.utc)
        ttl = expires_at - now
        
        # Đảm bảo TTL không âm
        if ttl.total_seconds() <= 0:
            return True
        
        return await redis_blacklist.add_to_blacklist(token, ttl)
    
    @staticmethod
    async def refresh_access_token(refresh_token: str) -> str:
        """
        Làm mới Access Token bằng Refresh Token
        
        Args:
            refresh_token: JWT refresh token
        
        Returns:
            Access token mới
        
        Raises:
            HTTPException: Nếu refresh token không hợp lệ
        """
        # Xác minh refresh token
        payload = TokenService.verify_token(refresh_token, token_type="refresh")
        
        # Kiểm tra refresh token có bị blacklist không
        if await TokenService.is_token_blacklisted(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Tạo access token mới từ payload
        user_data = create_jwt_user_data(
            user_id=payload.get("user_id", ""),
            email=payload.get("email", ""),
            username=payload.get("username", "")
        )
        access_token = TokenService.create_access_token(user_data)
        
        return access_token


# Global token service instance
token_service = TokenService()
