# 🚀 Hướng dẫn Setup JVB Final - AI Document Processing

## 📋 Tổng quan

Dự án JVB Final là một hệ thống xử lý tài liệu AI với các tính năng:
- **Upload tài liệu** (PDF, DOCX, TXT)
- **Xử lý tự động**: Split → Embedding → Lưu vào Vector DB
- **Vector Search** với Qdrant
- **Object Storage** với MinIO
- **RAG (Retrieval-Augmented Generation)** - Sẽ implement sau

## 🏗️ Kiến trúc hệ thống

```
Frontend (React) 
    ↓
Backend (FastAPI)
    ├── PostgreSQL (Metadata: documents, users, chunks)
    ├── Redis (Cache, blacklist tokens)
    ├── MinIO (Object storage cho files)
    ├── Qdrant (Vector database cho embeddings)
    └── Cohere API (Generate embeddings)
```

## 📦 Yêu cầu

- Docker & Docker Compose
- Python 3.11+ (nếu chạy local)
- Cohere API Key (miễn phí tại: https://dashboard.cohere.com/)

## ⚙️ Setup

### Bước 1: Clone và cấu hình

```bash
cd d:/JVB_final

# Copy file .env.example
cp .env.example .env
cp backend/.env.example backend/.env
```

### Bước 2: Cấu hình Cohere API Key

1. Đăng ký Cohere tại: https://dashboard.cohere.com/
2. Lấy API key
3. Mở file `.env` ở root directory:

```env
COHERE_API_KEY=your-cohere-api-key-here
```

4. Mở `backend/.env` và điền đầy đủ thông tin (xem backend/.env.example)

### Bước 3: Khởi động services

```bash
docker-compose up -d
```

Services sẽ chạy trên:
- **Backend API**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **Qdrant Dashboard**: http://localhost:6333/dashboard

### Bước 4: Kiểm tra logs

```bash
# Xem logs của backend
docker-compose logs -f backend

# Kiểm tra tất cả services đã chạy
docker-compose ps
```

Nếu thành công, bạn sẽ thấy:
```
✅ Database initialized
✅ Redis blacklist connected
✅ User presence tracker connected
✅ MinIO connected
✅ Qdrant connected
```

## 📡 API Endpoints

### 1. Upload tài liệu

**POST** `/api/documents/upload`

```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@document.pdf" \
  -F "title=My Document" \
  -F "category=programming" \
  -F 'tags=["python", "tutorial"]'
```

**Response:**
```json
{
  "id": "uuid",
  "title": "My Document",
  "file_name": "document.pdf",
  "file_size": 1024000,
  "is_processed": false,
  "processing_status": "pending",
  ...
}
```

### 2. Xem danh sách documents

**GET** `/api/documents`

```bash
curl http://localhost:8000/api/documents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Xem chi tiết document

**GET** `/api/documents/{document_id}`

```bash
curl http://localhost:8000/api/documents/{uuid} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🔄 Luồng xử lý tài liệu

1. **User upload file** → Backend nhận file
2. **Upload to MinIO** → Lưu file vào object storage
3. **Lưu metadata vào PostgreSQL** → Tạo record trong bảng `documents`
4. **Background task xử lý AI**:
   - Download file từ MinIO
   - Load document (PDF/DOCX/TXT)
   - Split thành chunks (1000 chars, overlap 200)
   - Generate embeddings với Cohere (embed-multilingual-v3.0)
   - Lưu chunks vào PostgreSQL
   - Lưu vectors vào Qdrant với payload đầy đủ
5. **Update status** → `is_processed=True`, `processing_status="completed"`

## 🗄️ Cấu trúc Database

### PostgreSQL

**documents**: Metadata của file
- id, user_id, title, file_name, file_path (MinIO path)
- is_processed, processing_status
- category, tags

**document_chunks**: Text chunks
- id, document_id, chunk_index, chunk_text, token_count

**document_embeddings**: Metadata của embeddings (KHÔNG lưu vector)
- id, chunk_id, document_id
- qdrant_point_id (link to Qdrant)
- embedding_model, vector_dimension

### Qdrant

Collection: `jvb_embeddings`

**Point structure:**
```json
{
  "id": "chunk_uuid",
  "vector": [0.123, 0.456, ...],  // 1024 dimensions
  "payload": {
    "document_id": "uuid",
    "chunk_id": "uuid",
    "chunk_text": "...",
    "chunk_index": 0,
    "user_id": "uuid",
    "file_name": "document.pdf",
    "title": "...",
    "category": "...",
    "tags": [...]
  }
}
```

## 🐛 Troubleshooting

### Backend không start được

```bash
# Xem logs chi tiết
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

### Lỗi "Cohere API key not found"

Kiểm tra file `.env` ở root có COHERE_API_KEY chưa.

### MinIO không kết nối được

```bash
# Restart MinIO
docker-compose restart minio

# Kiểm tra bucket
docker-compose exec backend python -c "from core.minio import minio_client; print(minio_client.client.list_buckets())"
```

### Qdrant không kết nối được

```bash
# Restart Qdrant
docker-compose restart qdrant

# Kiểm tra collection
curl http://localhost:6333/collections
```

## 📚 Tài liệu tham khảo

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Cohere API](https://docs.cohere.com/)
- [MinIO Python SDK](https://min.io/docs/minio/linux/developers/python/API.html)
- [LangChain](https://python.langchain.com/docs/get_started/introduction)

## 🎯 Roadmap

- [x] Upload tài liệu
- [x] Xử lý AI: Split, Embedding, Qdrant
- [ ] RAG Chat: Query → Search Qdrant → LLM
- [ ] Streaming response
- [ ] WebSocket cho real-time processing status
- [ ] Multi-language support
- [ ] OCR cho scan documents

## 📞 Hỗ trợ

Nếu gặp vấn đề, vui lòng:
1. Kiểm tra logs: `docker-compose logs -f backend`
2. Kiểm tra tất cả services đang chạy: `docker-compose ps`
3. Restart: `docker-compose restart`
