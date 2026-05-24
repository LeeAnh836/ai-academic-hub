# JVB Final

Nền tảng học tập và trao đổi nội dung có tích hợp AI, gồm ba khối chính: frontend React, backend FastAPI và ai-service xử lý RAG, embedding và multi-agent. Dự án chạy được bằng Docker Compose ở môi trường development và production.

## Tổng quan

Luồng chính của hệ thống là:

1. Người dùng thao tác ở frontend.
2. Frontend gọi backend qua JWT.
3. Backend xử lý xác thực, dữ liệu người dùng, tài liệu, hội thoại, nhóm và thông báo.
4. Backend gọi ai-service cho các tác vụ AI như embedding, truy vấn tài liệu, chat theo ngữ cảnh và xử lý agent.

Hệ thống dùng các dịch vụ nền như PostgreSQL, MongoDB, Redis, MinIO và Qdrant.

## Cấu trúc thư mục

### `frontend/`

Ứng dụng web React + TypeScript + Vite. Đây là giao diện chính cho đăng nhập, quản lý tài liệu, chat AI, nhóm, hồ sơ cá nhân và trang quản trị.

### `backend/`

API chính bằng FastAPI. Thư mục này xử lý auth, user, documents, chat, messaging, groups, admin và các kết nối hạ tầng.

### `ai-service/`

Microservice AI. Thư mục này chứa embedding, RAG, router AI, agent đa tác vụ, bộ nhớ hội thoại, cache LLM và các service truy xuất vector.

### Các file gốc

- `docker-compose.yml`: cấu hình local development.
- `docker-compose.prod.yml`: cấu hình production.
- `README.md`: tài liệu tổng quan này.
- `ai_rag_system_architecture_report.md`: báo cáo kiến trúc.
- `debug_qdrant.py`: script debug Qdrant.
- `minio-cors-config.json`: cấu hình CORS cho MinIO.

## Kiến trúc triển khai

```text
Frontend (5173)
       -> Backend (8000)
              -> PostgreSQL / MongoDB / Redis / MinIO / Qdrant
              -> AI Service (8001)
                             -> Qdrant / Mongo memory / LLM cache
```

### Dịch vụ chính

| Dịch vụ | Vai trò | Cổng mặc định |
|---|---|---|
| Frontend | Giao diện người dùng | 5173 hoặc 80 ở production |
| Backend | API nghiệp vụ chính | 8000 |
| AI Service | Embedding, RAG, agent | 8001 |
| PostgreSQL | Dữ liệu nghiệp vụ | 5432 |
| MongoDB | Lưu chat history và memory | 27017 |
| Redis | Cache, blacklist, session support | 6379 |
| MinIO | Lưu file/object storage | 9000/9001 |
| Qdrant | Vector database | 6333/6334 |

## Chạy local

1. Chuẩn bị biến môi trường trong `backend/.env`, `ai-service/.env` và `frontend/.env` nếu cần.
2. Chạy toàn bộ hệ thống:

```powershell
docker compose up -d
```

3. Kiểm tra trạng thái:

```powershell
docker compose ps
```

4. Mở các giao diện:

| Thành phần | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend docs | http://localhost:8000/docs |
| AI Service docs | http://localhost:8001/docs |
| MinIO console | http://localhost:9001 |
| Qdrant dashboard | http://localhost:6333/dashboard |

## Chạy production

Production dùng file `docker-compose.prod.yml`. Khi triển khai cần cung cấp các biến như `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ROOT_PASSWORD` và các file `.env.production` tương ứng cho backend và ai-service.

```powershell
docker compose -f docker-compose.prod.yml up -d
```

## Tài liệu con

- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)
- [AI Service README](ai-service/README.md)
- [AI Agents README](ai-service/agents/README.md)

## Ghi chú vận hành

- Backend cần JWT cho hầu hết API nghiệp vụ.
- AI Service là service nội bộ, thường được backend gọi trực tiếp.
- Dữ liệu hội thoại và memory được thiết kế để không phụ thuộc vào một phiên frontend duy nhất.
- Hệ thống hỗ trợ cả môi trường local lẫn production bằng Docker.
