# JVB Backend API

## Cấu trúc thư mục

```
backend/
├── core/
│   ├── __init__.py
│   ├── config.py              # Cấu hình chính ứng dụng
│   ├── databases.py           # Kết nối PostgreSQL
│   └── redis.py               # Quản lý Redis blacklist
├── models/
│   ├── __init__.py
│   ├── base.py                # BaseModel với UUID
│   ├── users.py               # User, UserSession, LoginHistory
│   ├── documents.py           # Document models
│   ├── chat.py                # Chat models
│   ├── conversations.py       # Direct message models
│   ├── groups.py              # Group models
│   ├── notifications.py       # Notification models
│   ├── audit.py               # Audit log models
│   └── STRUCTURE.md
├── schemas/                   # Pydantic schemas (response/request)
├── services/
│   ├── __init__.py
│   └── token_service.py       # JWT token management
├── main.py                    # FastAPI main application
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker image definition
├── .env                       # Environment variables (git ignored)
└── .env.example               # Example environment variables

```

## Chức năng chính

### 1. **Config (core/config.py)**
- Quản lý tất cả cấu hình ứng dụng
- Database URL, Redis URL
- JWT secret key và thuật toán
- Thời gian expire tokens
- CORS origins

### 2. **Database (core/databases.py)**
- Kết nối PostgreSQL qua SQLAlchemy
- Hàm `get_db()` dùng làm dependency injection
- Hàm `init_db()` tạo tất cả tables
- Hàm `close_db()` đóng kết nối

### 3. **Redis (core/redis.py)**
- Quản lý token blacklist
- Lưu tokens bị logout để không thể dùng lại
- TTL tự động = thời gian token còn hết hạn
- Hàm:
  - `add_to_blacklist()`: Thêm token vào blacklist
  - `is_blacklisted()`: Kiểm tra token bị blacklist
  - `remove_from_blacklist()`: Xóa token khỏi blacklist

### 4. **Token Service (services/token_service.py)**
- Tạo JWT access token và refresh token
- Xác minh token
- Kiểm tra blacklist
- Làm mới access token từ refresh token
- Hàm chính:
  - `create_access_token()`: Tạo access token
  - `create_refresh_token()`: Tạo refresh token
  - `create_token_pair()`: Tạo cả 2 token
  - `verify_token()`: Xác minh và giải mã token
  - `blacklist_token()`: Logout (thêm vào blacklist)
  - `refresh_access_token()`: Làm mới access token

## Cách sử dụng

### Setup Environment

1. Copy file .env.example:
```bash
cp .env.example .env
```

2. Chỉnh sửa .env với các thông tin thực tế (nếu cần)

### Docker Compose

1. Build và chạy với Docker:
```bash
docker-compose up -d
```

2. Kiểm tra các services:
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- MinIO: http://localhost:9001
- Qdrant: http://localhost:6333

### Database Migrations

Các tables tự động được tạo khi ứng dụng startup qua `init_db()`

### Sử dụng Token

```python
from services.token_service import token_service
from core.databases import get_db

# 1. Tạo token pair khi login
tokens = token_service.create_token_pair({
    "user_id": "user-uuid",
    "email": "user@example.com",
    "username": "username"
})

# 2. Xác minh access token
payload = token_service.verify_token(access_token, token_type="access")

# 3. Logout - thêm token vào blacklist
await token_service.blacklist_token(access_token, expires_at)

# 4. Làm mới access token
new_access_token = await token_service.refresh_access_token(refresh_token)
```

## Triển khai Production

Để triển khai trên production:

1. Đổi `SECRET_KEY` thành một key ngẫu nhiên mạnh:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. Đặt `DEBUG=False`

3. Cấu hình CORS_ORIGINS với domains thực tế

4. Sử dụng database credentials mạnh

5. Sử dụng https cho API endpoints

## Thời gian Token

- **Access Token**: 15 phút (có thể điều chỉnh qua `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Token**: 7 ngày (có thể điều chỉnh qua `REFRESH_TOKEN_EXPIRE_DAYS`)

Khi logout, token sẽ được thêm vào Redis blacklist với TTL = thời gian token còn hết hạn.
