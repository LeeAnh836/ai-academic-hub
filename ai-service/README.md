# AI Service

AI Processing Microservice cho JVB Platform

## 🎯 Tính năng

- **Embeddings**: Generate embeddings từ texts bằng Cohere
- **RAG (Retrieval Augmented Generation)**: Tìm kiếm context và generate câu trả lời
- **Document Processing**: Load, split, embed documents và lưu vào Qdrant
- **Vector Search**: Semantic search trong documents
- **Chat with Context**: Chat sử dụng documents làm context

## 🏗️ Tech Stack

- **Framework**: FastAPI
- **Vector Database**: Qdrant
- **Embedding Model**: Cohere embed-multilingual-v3.0 (1024 dims)
- **LLM**: Cohere Command R+
- **Document Processing**: LangChain

## 📦 Cài đặt

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env và thêm COHERE_API_KEY
```

## 🚀 Chạy Local

```bash
python main.py
```

Service sẽ chạy tại: `http://localhost:8001`

## 🐳 Chạy với Docker

```bash
docker build -t jvb-ai-service .
docker run -p 8001:8001 --env-file .env jvb-ai-service
```

## 📚 API Endpoints

### Embeddings
- `POST /api/embed` - Generate embeddings cho texts
- `POST /api/embed/query` - Generate embedding cho single query

### RAG
- `POST /api/rag/query` - Query RAG system (search + generate)
- `POST /api/rag/chat` - Chat với AI có document context
- `POST /api/rag/search` - Vector search (không generate answer)

### Document Processing
- `POST /api/documents/process` - Process document (upload -> embed -> Qdrant)
- `DELETE /api/documents/vectors/{document_id}` - Delete document vectors

### Health
- `GET /` - Service info
- `GET /health` - Health check

## 🔗 Kết nối với Backend

Backend gọi AI Service qua HTTP:

```python
# In backend
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://ai-service:8001/api/rag/query",
        json={
            "question": "Giải thích OOP là gì?",
            "user_id": "uuid",
            "document_ids": ["doc1", "doc2"]
        }
    )
```

## 📖 Documentation

API docs tự động: `http://localhost:8001/docs`
