"""
JWT Token Schemas - Định nghĩa cấu trúc JWT payload với TypedDict
"""
from typing import TypedDict, Optional, Literal
from datetime import datetime


class JWTBasePayload(TypedDict, total=False):
    """Base JWT payload structure - chứa các field cơ bản của JWT"""
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: Literal["access", "refresh"]  # Token type


class JWTAccessPayload(JWTBasePayload):
    """Access Token payload structure"""
    user_id: str
    email: str
    username: str


class JWTRefreshPayload(JWTBasePayload):
    """Refresh Token payload structure"""
    user_id: str
    email: str
    username: str


class JWTUserData(TypedDict):
    """User data structure dùng để tạo token"""
    user_id: str
    email: str
    username: str


class TokenPair(TypedDict):
    """Token pair structure"""
    access_token: str
    refresh_token: str
    token_type: str


def create_jwt_user_data(user_id: str, email: str, username: str) -> JWTUserData:
    """
    Helper function để tạo JWTUserData type-safe
    
    Args:
        user_id: User ID
        email: User email
        username: Username
    
    Returns:
        JWTUserData TypedDict
    """
    return JWTUserData(
        user_id=user_id,
        email=email,
        username=username
    )
