"""
Password hashing and verification utilities
Pure technical functions - không phụ thuộc vào business logic

Quy trình:
1. Lấy password người dùng nhập (vd: !hugAfi35sg...)
2. Hash qua SHA-256 tạo chuỗi 64 ký tự hex (luôn < 72 bytes)
3. Đưa chuỗi 64 ký tự vào bcrypt để băm và lưu DB
"""
import bcrypt
import hashlib


def _prepare_password(password: str) -> bytes:
    """
    Chuẩn bị password: LUÔN LUÔN hash qua SHA256 trước.
    
    Bước 1: Password người dùng → SHA256 → chuỗi hex 64 ký tự
    Bước 2: Chuỗi hex này sẽ được đưa vào bcrypt
    
    Lợi ích:
    - Consistent: Mọi password đều qua SHA256
    - Safe: 64 ký tự hex < 72 bytes (giới hạn bcrypt)
    - Secure: SHA256 giúp tránh các vấn đề với password đặc biệt
    
    Args:
        password: Plain text password từ user
    
    Returns:
        SHA256 hex string dưới dạng bytes (64 chars = 64 bytes)
    """
    # Bước 1: Hash password qua SHA256 → chuỗi hex 64 ký tự
    password_bytes = password.encode("utf-8")
    sha256_hex = hashlib.sha256(password_bytes).hexdigest()
    
    # Bước 2: Convert hex string thành bytes để đưa vào bcrypt
    return sha256_hex.encode("utf-8")


def hash_password(password: str) -> str:
    """
    Hash password using SHA256 + bcrypt.
    
    Quy trình:
    1. Password → SHA256 → 64 chars hex
    2. 64 chars hex → bcrypt → hash cuối cùng lưu DB
    
    Args:
        password: Plain text password từ user (vd: !hugAfi35sg...)
    
    Returns:
        Bcrypt hashed string để lưu vào database
    
    Example:
        >>> hash_password("MyPassword123!")
        '$2b$12$...'  # Bcrypt hash của SHA256(MyPassword123!)
    """
    # Bước 1: Password → SHA256 hex (64 chars)
    prepared_password = _prepare_password(password)
    
    # Bước 2: SHA256 hex → bcrypt
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(prepared_password, salt)
    
    # Return as string
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password: dùng cùng quy trình SHA256 + bcrypt.
    
    Quy trình:
    1. Password user nhập → SHA256 → 64 chars hex
    2. So sánh bcrypt(SHA256) với hash trong DB
    
    Args:
        plain_password: Password người dùng nhập khi login
        hashed_password: Bcrypt hash từ database
    
    Returns:
        True nếu password đúng, False nếu sai
    """
    try:
        # Bước 1: Áp dụng cùng quy trình SHA256
        prepared_password = _prepare_password(plain_password)
        hashed_bytes = hashed_password.encode("utf-8")
        
        # Bước 2: Verify với bcrypt
        return bcrypt.checkpw(prepared_password, hashed_bytes)
    except Exception:
        # Return False if verification fails for any reason
        return False
