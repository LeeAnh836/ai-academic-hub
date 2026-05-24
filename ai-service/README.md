# AI Service

AI Service là microservice xử lý toàn bộ phần AI của JVB Final. Thư mục này tập trung vào embedding, RAG, semantic search, multi-agent, prompt rewriting và các pipeline liên quan đến tài liệu.

## Vai trò

- Nhận request từ backend để xử lý AI.
- Tạo embedding và truy vấn vector database.
- Sinh câu trả lời theo ngữ cảnh tài liệu.
- Điều phối nhiều chiến lược truy xuất và suy luận.
- Hỗ trợ agent chuyên biệt cho document QA, data analysis, general QA và code execution.

## Cấu trúc thư mục

```text
ai-service/
├── agents/          # Các agent chuyên biệt
├── core/            # Cấu hình, Qdrant, memory, cache, model manager
├── models/          # Pydantic schemas
├── routers/         # FastAPI routers
├── services/        # RAG, embedding, orchestration, rerank, tool execution
├── test_data/       # Dữ liệu mẫu phục vụ thử nghiệm
├── main.py          # Entry point FastAPI
├── requirements.txt
├── Dockerfile
├── Dockerfile.prod
└── README.md
```

## Các khối chức năng chính

### `routers/`

- `embedding.py`: API tạo embedding.
- `rag.py`: API truy vấn RAG và chat theo ngữ cảnh.
- `document.py`: API xử lý tài liệu, tạo vectors và xóa vectors.
- `agent.py`: API cho multi-agent nếu feature được bật.

### `services/`

Đây là nơi chứa phần lớn logic của AI service:

- `embedding_service.py`: thao tác embedding.
- `rag_service.py`, `advanced_rag_service.py`, `corrective_rag.py`: các tầng RAG khác nhau.
- `document_service.py`: xử lý tài liệu đầu vào.
- `master_orchestrator.py`, `orchestrator.py`: điều phối luồng xử lý.
- `intent_classifier.py`, `query_rewriter.py`, `query_complexity_analyzer.py`: phân loại và chuẩn hóa truy vấn.
- `reranker.py`: xếp hạng lại kết quả.
- `tool_executor.py`, `computation_pipeline.py`: thực thi công cụ và pipeline tính toán.

### `core/`

- `config.py`: cấu hình service và feature flags.
- `qdrant.py`: client/vector connection.
- `memory.py`: conversation memory và state.
- `llm_cache.py`: cache cho các tác vụ LLM.
- `model_manager.py`: quản lý và xoay vòng model/provider.

### `agents/`

Thư mục chứa các agent chuyên môn hóa. Chi tiết từng agent được mô tả trong [agents/README.md](agents/README.md).

## Tech stack

- FastAPI
- Qdrant
- MongoDB cho memory/hội thoại khi bật multi-agent
- Redis cho cache
- Các model/LLM backend được quản lý qua `model_manager`

## Chạy local

```bash
pip install -r requirements.txt
python main.py
```

Service mặc định chạy ở `http://localhost:8001`.

## Chạy Docker

```bash
docker build -t jvb-ai-service .
docker run -p 8001:8001 --env-file .env jvb-ai-service
```

## API chính

### Embedding

- `POST /api/embed`
- `POST /api/embed/query`

### RAG

- `POST /api/rag/query`
- `POST /api/rag/chat`
- `POST /api/rag/search`

### Document

- `POST /api/documents/process`
- `DELETE /api/documents/vectors/{document_id}`

### Agent

- Các endpoint agent được bật khi `routers/agent.py` khả dụng và feature được mở trong config.

### Health

- `GET /`
- `GET /health`

## Luồng khởi động

Khi chạy `main.py`, service sẽ:

1. Kết nối Qdrant.
2. Kết nối memory Mongo nếu multi-agent được bật.
3. Kết nối LLM cache nếu feature cache bật.
4. Đăng ký các router embedding, rag, document và agent.

## Kết nối với backend

Backend gọi AI service bằng HTTP nội bộ để:

- hỏi đáp theo tài liệu.
- tạo embedding cho tài liệu mới.
- xử lý truy vấn ngắn cần làm rõ ý định.
- thực thi pipeline agent.

## Ghi chú phát triển

- Đây là service AI nội bộ, không phải frontend public.
- Khi sửa logic truy xuất, cần xem đồng thời `services/`, `routers/` và `agents/`.
- `test_data/` chỉ là dữ liệu kiểm thử, không phải dữ liệu chạy thật.
