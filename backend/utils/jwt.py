"""
JWT token encoding and decoding utilities
Pure technical functions - chỉ encode/decode JWT, không có business logic
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from fastapi import HTTPException, status


def encode_jwt(
    payload: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Encode payload thành JWT token
    
    Args:
        payload: Dict chứa data cần encode
        secret_key: Secret key để sign token
        algorithm: Algorithm dùng để sign (default: HS256)
        expires_delta: Thời gian hết hạn (nếu None thì không có exp)
    
    Returns:
        JWT token string
    """
    to_encode = payload.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        })
    
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_jwt(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    verify_exp: bool = True
) -> Dict[str, Any]:
    """
    Decode và verify JWT token
    
    Args:
        token: JWT token string
        secret_key: Secret key để verify
        algorithm: Algorithm đã dùng để sign
        verify_exp: Có verify expiration time không
    
    Returns:
        Payload dict
    
    Raises:
        HTTPException: Nếu token invalid hoặc expired
    """
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options=options
        )
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_token_expiration(token: str, secret_key: str, algorithm: str = "HS256") -> Optional[datetime]:
    """
    Lấy thời gian hết hạn của token (không verify)
    
    Args:
        token: JWT token string
        secret_key: Secret key
        algorithm: Algorithm
    
    Returns:
        Datetime object hoặc None nếu không có exp
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"verify_exp": False}
        )
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None
    except Exception:
        return None
