"""
Validation utilities
Pure technical functions - validate email, phone, format, etc.
"""
import re
from typing import Optional


def is_valid_email(email: str) -> bool:
    """
    Kiểm tra email format có hợp lệ không
    
    Args:
        email: Email string
    
    Returns:
        True nếu valid, False nếu không
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_username(username: str, min_length: int = 3, max_length: int = 30) -> bool:
    """
    Kiểm tra username format (alphanumeric + underscore)
    
    Args:
        username: Username string
        min_length: Độ dài tối thiểu
        max_length: Độ dài tối đa
    
    Returns:
        True nếu valid, False nếu không
    """
    if not username or len(username) < min_length or len(username) > max_length:
        return False
    
    pattern = r'^[a-zA-Z0-9_]+$'
    return bool(re.match(pattern, username))


def is_valid_password(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = False,
    require_lowercase: bool = False,
    require_digit: bool = False,
    require_special: bool = False
) -> tuple[bool, Optional[str]]:
    """
    Kiểm tra password strength
    
    Args:
        password: Password string
        min_length: Độ dài tối thiểu
        require_uppercase: Yêu cầu chữ hoa
        require_lowercase: Yêu cầu chữ thường
        require_digit: Yêu cầu số
        require_special: Yêu cầu ký tự đặc biệt
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    
    if require_uppercase and not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if require_lowercase and not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if require_digit and not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, None


def is_valid_student_id(student_id: str, pattern: Optional[str] = None) -> bool:
    """
    Kiểm tra student ID format
    
    Args:
        student_id: Student ID string
        pattern: Regex pattern tùy chỉnh (nếu None dùng pattern mặc định)
    
    Returns:
        True nếu valid, False nếu không
    """
    if not student_id:
        return False
    
    # Pattern mặc định: chữ + số, ví dụ: "B20DCCN123" hoặc chỉ số
    default_pattern = r'^[A-Z0-9]+$'
    check_pattern = pattern if pattern else default_pattern
    
    return bool(re.match(check_pattern, student_id))


def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """
    Làm sạch string: trim, remove multiple spaces, limit length
    
    Args:
        text: Text cần sanitize
        max_length: Độ dài tối đa (nếu None thì không limit)
    
    Returns:
        Cleaned string
    """
    # Trim và remove multiple spaces
    cleaned = ' '.join(text.split())
    
    # Limit length nếu cần
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    return cleaned


def is_valid_uuid(uuid_string: str) -> bool:
    """
    Kiểm tra UUID format có hợp lệ không
    
    Args:
        uuid_string: UUID string
    
    Returns:
        True nếu valid UUID, False nếu không
    """
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, uuid_string.lower()))
