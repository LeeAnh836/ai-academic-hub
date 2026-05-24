# Backend

Backend là lớp API nghiệp vụ chính của hệ thống. Thư mục này chịu trách nhiệm xác thực, quản lý người dùng, tài liệu, hội thoại, nhóm, nhắn tin, admin và tích hợp với các dịch vụ hạ tầng.

## Vai trò chính

- Cung cấp REST API cho frontend.
- Xác thực JWT và quản lý phiên đăng nhập.
- Làm việc với PostgreSQL, MongoDB, Redis, MinIO và Qdrant.
- Đồng bộ dữ liệu liên quan tới chat history và nguồn tài liệu.
- Đóng vai trò trung gian giữa frontend và ai-service.

## Cấu trúc thư mục

```text
backend/
├── api/            # Router FastAPI theo từng domain
├── core/           # Cấu hình và kết nối hạ tầng
├── migrations/     # SQL migration bổ sung
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic request/response schemas
├── scripts/        # Script hỗ trợ vận hành/bổ sung dữ liệu
├── services/       # Business logic và tích hợp dịch vụ
├── utils/          # Hàm tiện ích dùng chung
├── main.py         # Entry point FastAPI
├── requirements.txt
├── Dockerfile
└── README.md
```

## Các phần quan trọng

### `api/`

Chứa các router theo chức năng:

- `auth.py`: đăng ký, đăng nhập, làm mới token, logout.
- `users.py`: hồ sơ và quản lý người dùng.
- `documents.py`: upload, liệt kê, xử lý và xóa tài liệu.
- `chat.py`: hội thoại, chat sessions, timeline và hỏi đáp.
- `groups.py`: nhóm, thành viên và tương tác theo nhóm.
- `messaging.py`: nhắn tin trực tiếp hoặc theo ngữ cảnh nhóm.
- `admin.py`: endpoint quản trị.
- `dependencies.py`: dependency dùng chung cho API.

### `core/`

Tập trung toàn bộ phần hạ tầng:

- `config.py`: cấu hình môi trường, URL dịch vụ, CORS, secret, feature flags.
- `databases.py`: kết nối PostgreSQL và lifecycle database.
- `mongo.py`: kết nối MongoDB cho chat history/source-of-truth.
- `redis.py`: Redis cho blacklist và cache liên quan.
- `minio.py`: kết nối object storage.
- `qdrant.py`: kết nối vector database.

### `models/`

Định nghĩa các bảng chính của hệ thống:

- người dùng và phiên đăng nhập.
- tài liệu và metadata.
- hội thoại, conversation, message và notification.
- nhóm và các quan hệ liên quan.

### `schemas/`

Pydantic schemas cho request/response. Đây là lớp dữ liệu mà API trả về cho frontend và nhận từ client.

### `services/`

Chứa business logic tách khỏi router:

- `auth_service.py`: quy trình xác thực.
- `token_service.py`: tạo, kiểm tra và blacklist token.
- `chat_service.py` và `chat_history_service.py`: luồng chat, lưu lịch sử, timeline.
- `document_service.py`: xử lý tài liệu.
- `group_service.py`, `messaging_service.py`, `user_service.py`: nghiệp vụ theo domain.
- `minio_service.py`, `qdrant_service.py`, `ai_service.py`: tích hợp các service nền.
- `user_presence.py`: theo dõi trạng thái người dùng.

### `scripts/`

Script vận hành, ví dụ backfill dữ liệu chat history sang Mongo.

### `migrations/`

Các thay đổi SQL thủ công bổ sung cho schema hoặc dữ liệu.

## Luồng khởi động

Khi `main.py` chạy, backend:

1. Khởi tạo PostgreSQL.
2. Kết nối Redis blacklist.
3. Kết nối user presence tracker.
4. Kết nối MinIO.
5. Kết nối Qdrant.
6. Kết nối Mongo chat history nếu feature được bật.

## Chạy backend

### Local bằng Docker Compose

```powershell
docker compose up -d backend
```

### Chạy trực tiếp

```powershell
python main.py
```

API mặc định ở `http://localhost:8000`, tài liệu Swagger ở `http://localhost:8000/docs`.

## Quản lý token

Backend dùng access token và refresh token để xác thực:

- access token ngắn hạn cho request API.
- refresh token để cấp lại access token.
- token đã logout được đưa vào Redis blacklist.

## Gợi ý triển khai production

- Dùng secret mạnh cho `SECRET_KEY`.
- Bật cấu hình CORS đúng domain thật.
- Dùng credentials riêng cho PostgreSQL, Redis và MinIO.
- Kiểm tra kỹ biến môi trường khi build production image.

## Điểm cần lưu ý

- Backend hiện là nơi gom logic nghiệp vụ, không nên dồn trực tiếp logic AI vào router.
- Với chat history, Mongo đang đóng vai trò nguồn dữ liệu ưu tiên hơn Redis.
- Nếu thay đổi schema, cần đồng bộ model, schema và các service liên quan.
