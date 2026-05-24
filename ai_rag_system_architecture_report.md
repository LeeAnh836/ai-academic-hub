# Báo Cáo Kiến Trúc Hệ Thống FE-BE-AI và Lõi Mô Hình RAG (Code-Verified)

Tài liệu này được viết lại dựa trên việc rà soát trực tiếp code trong toàn bộ dự án ở 3 lớp Frontend, Backend, AI Service và lớp hạ tầng Docker. Mục tiêu là mô tả hệ thống như một dòng chảy thống nhất, tập trung sâu vào lõi mô hình, luồng hoạt động của mô hình, cơ chế fallback và nơi dữ liệu thực sự được lưu trữ trong vận hành hiện tại.

## Tổng quan kiến trúc FE, BE, AI và hạ tầng

Frontend là lớp giao diện React + TypeScript, chịu trách nhiệm tương tác người dùng, quản lý phiên chat, upload tài liệu, hiển thị markdown kết quả AI và điều hướng tới trang preview tài liệu theo nguồn trích dẫn. Frontend không chạy AI trực tiếp, mà luôn gọi backend qua HTTP API.

Backend là lớp điều phối nghiệp vụ trung tâm bằng FastAPI. Backend xử lý xác thực, phiên chat, metadata tài liệu, vòng đời tài liệu, lưu lịch sử chat và gọi nội bộ sang AI Service để xử lý AI. Backend cũng là lớp gắn ngữ cảnh hội thoại, chuẩn hóa tài liệu theo canonical ID, và quản lý nguồn tri thức trong Mongo.

AI Service là microservice FastAPI độc lập cho toàn bộ tác vụ AI gồm đọc tài liệu nhiều định dạng, OCR ảnh/PDF scan, chunking, embedding, retrieval, rerank, corrective RAG, đa-agent orchestration và sinh câu trả lời.

Hạ tầng chạy qua docker-compose gồm:
- PostgreSQL cho dữ liệu quan hệ nghiệp vụ
- MongoDB cho chat history source-of-truth
- Redis cho token blacklist và cache helper LLM
- MinIO cho file gốc dạng object storage
- Qdrant cho vector retrieval

## Lõi mô hình trong AI Service

### 1) ModelManager: bộ não điều phối model và provider

ModelManager là điểm quyết định provider và model theo task_type và complexity.

Các nhóm route chính hiện tại:
- Nhóm helper/intermediate task như intent classification, query rewrite, corrective RAG, rerank, document map ưu tiên Groq trước để tối ưu chi phí/độ trễ.
- Nhóm trả lời nặng như rag_query, summarization ưu tiên Gemini Flash/Pro và Mistral theo độ phức tạp.
- Nhóm code_help, homework_solver, data_analysis đổi thứ tự theo độ khó.

Cơ chế fallback và chịu lỗi của ModelManager:
- Fallback chain đa provider khi lỗi sinh text.
- Theo dõi trạng thái rate-limit theo provider và thời điểm reset.
- Gemini hỗ trợ nhiều API key theo round-robin.
- Key Gemini invalid/expired bị loại vĩnh viễn khỏi rotation.
- Lỗi 503 Gemini sẽ cooldown ngắn theo key rồi xoay key khác.
- Trường hợp hard-limit theo model (ví dụ model chạm limit 0) sẽ cooldown theo model thay vì đốt hết key.
- OCR Vision cũng dùng chung tinh thần xoay key/fallback qua generate_text_from_image.

### 2) Intent Classifier: phân luồng ý định theo mô hình lai

Intent classifier dùng kết hợp:
- Rule-based cho tình huống rõ ràng, ưu tiên tốc độ.
- LLM-based cho tình huống mơ hồ, có cache helper để tiết kiệm token.

Các intent chính gồm direct_chat, rag_query, summarization, question_generation, data_analysis, homework_solver, code_help.

Tầng orchestrator còn có guard quan trọng:
- Nếu có tài liệu và câu hỏi dạng tham chiếu deictic như file này, hình này, this file thì ép route về nhánh document-grounded (rag_query hoặc summarization).
- Nếu không có tài liệu mà intent thuộc nhóm phụ thuộc tài liệu thì ép về direct_chat để tránh trả lời lạc sang lỗi thiếu file.

### 3) Prompt Preprocessor: chuẩn hóa các câu mơ hồ theo ngữ cảnh hội thoại

Prompt preprocessor xử lý các câu cực ngắn hoặc tham chiếu ngữ cảnh như có, được, những cái đó, cái này, above, those. Module này dùng memory context để phục hồi ý nghĩa trước khi intent classification và agent execution.

### 4) Hệ multi-agent

Master Orchestrator route request tới agent chuyên trách:
- DocumentQAAgent cho RAG, summarization, question_generation từ tài liệu.
- GeneralQAAgent cho câu hỏi kiến thức chung, code help, chat trực tiếp.
- DataAnalysisAgent cho phân tích CSV/XLSX qua sinh và thực thi code pandas.

Trong luồng chat chính từ backend, AI request gửi kèm persisted_by_backend=true, nên orchestrator sẽ không ghi đúp transcript vào memory nội bộ.

### 5) Memory và cache trong lõi mô hình

- Memory Mongo trong backend là nguồn hội thoại chính (conversations, messages, message_source_refs, conversation_summaries, conversation_state, knowledge_sources).
- AI memory manager vẫn tồn tại để fallback khi context request không mang đủ history.
- LLM cache dùng Redis + in-memory fallback cho helper calls như classify, rewrite, CRAG evaluate.

## Luồng ingest tài liệu từ upload đến index sẵn sàng truy vấn

### Bước 1: Upload từ Frontend

Frontend gọi endpoint upload của backend với file và metadata tùy chọn title/category/tags.

### Bước 2: Validate và hash ở Backend

Backend kiểm tra MIME/ext được hỗ trợ và giới hạn 20MB. Sau đó đọc bytes để tạo SHA-256 content_hash.

### Bước 3: Dedup theo người dùng và canonical hóa

Nếu là tài liệu không phải ảnh, backend tìm bản đã xử lý xong theo cùng user_id + content_hash + completed.

Nếu trùng:
- Tạo Document mới nhưng canonical_document_id trỏ về bản canonical.
- Reuse file_path MinIO của bản gốc.
- Đánh dấu is_processed=true và completed ngay, bỏ qua OCR/chunk/embedding.

Nếu là ảnh:
- Cố ý không dedup để giữ danh tính nguồn riêng cho trích dẫn.
- Tên ảnh generic sẽ được chuẩn hóa tên mới để tránh đụng độ.

### Bước 4: Lưu file gốc lên MinIO

Backend upload object theo cấu trúc user_id/uuid.ext. Trong PostgreSQL lưu file_path ở dạng bucket/object_name để truy vết object vật lý.

### Bước 5: Tạo bản ghi document pending

Backend tạo Document mới với status pending, sau đó set canonical_document_id = chính id mới.

### Bước 6: Chạy background task không chặn người dùng

Backend tạo background task process_document_background, mở session DB riêng, tải file từ MinIO rồi gọi AI Service endpoint xử lý tài liệu dạng multipart.

### Bước 7: AI Service đọc và chuẩn hóa tài liệu theo định dạng

Document service trong AI chọn chiến lược theo MIME/ext:
- PDF text: dùng PyPDFLoader.
- Nếu PDF text quá ít (ngưỡng nhỏ hơn khoảng 150 ký tự): coi như scan/image PDF, render mỗi trang bằng PyMuPDF 200 DPI rồi OCR bằng Gemini Vision.
- Ảnh JPG/PNG/WebP/HEIC: OCR trực tiếp bằng Gemini Vision.
- OCR có retry/backoff; nếu thất bại hoàn toàn vẫn tạo placeholder document để không vỡ pipeline.
- DOCX: Docx2txtLoader.
- Code file: đọc text và split theo ngôn ngữ lập trình tương ứng.
- CSV/XLSX: dùng pandas đọc bảng, chuyển markdown table theo cụm dòng.
- Text/định dạng còn lại: đọc UTF-8 có thay thế lỗi.
- File temp luôn được xóa sau xử lý.

### Bước 8: Chunking và chuẩn hóa chunk

Chunking dùng RecursiveCharacterTextSplitter với:
- chunk_size = 1000
- chunk_overlap = 200
- length_function dựa trên token encoder (fallback char length nếu thiếu tokenizer)

Chunk được chuẩn hóa thành nội dung có metadata header gồm filename, file_type, source. Chunk code được bọc fenced code block để giữ ngữ cảnh khi retrieval.

### Bước 9: Embedding và upsert vector

Embedding dùng Cohere embed-multilingual-v3.0:
- input_type search_document cho index
- vector_dimension 1024

AI Service tạo chunk_id, upsert point vào Qdrant với payload gồm document_id, chunk_id, chunk_text, chunk_index, user_id, file_name, title, category, tags, is_image_ocr.

### Bước 10: Backend lưu metadata chunk/embedding và finalize

AI Service trả về danh sách chunk đã chuẩn hóa cho backend. Backend ghi:
- document_chunks
- document_embeddings (metadata trỏ qdrant_point_id)

Sau cùng backend cập nhật document thành completed và is_processed=true.

## Luồng hỏi đáp chat từ người dùng đến câu trả lời

### Bước 1: Frontend gửi câu hỏi

Frontend gọi endpoint ask theo session. Nếu có file đính kèm mới, frontend upload file trước, poll batch status, rồi mới gửi ask với document_ids.

### Bước 2: Backend xử lý ngữ cảnh phiên chat

Backend tại endpoint ask thực hiện:
1. Lưu user message.
2. Xác định document_ids sử dụng theo thứ tự ưu tiên:
- Nếu request có document_ids (kể cả mảng rỗng): dùng explicit selection.
- Nếu request không gửi document_ids: dùng context_documents đã lưu trong session.
3. Chuẩn hóa document_ids sang canonical_document_id để đảm bảo truy vấn vào cùng bộ vector chuẩn.
4. Nếu request không explicit doc_ids, backend đọc source catalog của conversation và parse filename mention hoặc id:prefix trong câu hỏi để override active source chính xác hơn.
5. Upsert knowledge_sources trong Mongo từ document_ids đang dùng.
6. Build context bundle từ Mongo gồm:
- chat_history gần nhất
- conversation_summary
- source_ids
- source_metadata
7. Nếu câu hỏi mơ hồ kiểu tham chiếu khi có nhiều source và user chưa chọn rõ, backend trả 422 yêu cầu làm rõ nguồn.

### Bước 3: Backend gọi AI Service multi-agent

Backend gọi endpoint /api/agent/query với payload chứa:
- query, user_id, session_id
- document_ids đã canonical hóa
- top_k, score_threshold, temperature, max_tokens
- chat_history, conversation_summary
- source_ids, source_metadata
- trace_id
- persisted_by_backend=true

Backend có bước JSON-safe serialization để tránh lỗi kiểu datetime/UUID không serialize được.

### Bước 4: AI Service orchestration

Master Orchestrator trong AI Service chạy chuỗi:
1. Nếu thiếu chat_history, tự nạp từ memory.
2. Prompt preprocessing cho truy vấn mơ hồ.
3. Intent classification theo hybrid rule + LLM.
4. Guard ép route document-grounded cho câu deictic có tài liệu.
5. Route tới agent phù hợp.

### Bước 5: Nhánh Document QA (trọng tâm RAG)

DocumentQAAgent thực thi theo 2 nhánh lớn:

A. Nhánh summarization
- Scroll toàn bộ chunk của các tài liệu được chọn, không dùng top-k semantic.
- Map phase: tóm tắt từng tài liệu riêng.
- Quality guard: nếu summary ngắn/cụt thì retry với prompt/provider khác.
- Reduce phase: tổng hợp kết quả đa tài liệu.

B. Nhánh QA thông thường
1. Phân tích độ phức tạp câu hỏi.
2. Nếu ENABLE_ADVANCED_RAG=true:
- Query rewriting tạo nhiều biến thể.
- Có step-back query cho câu hỏi vừa/phức tạp.
- Multi-query vector retrieval và hợp nhất kết quả.
- BM25 rescoring tăng trọng số từ khóa.
- Reranking bằng Cohere rerank hoặc fallback LLM.
- CRAG đánh giá đủ ngữ cảnh hay không.
- Nếu insufficient thì tạo corrective query và truy xuất lại theo ngưỡng linh hoạt.
- Nếu query đủ điều kiện multi-hop thì decomposition thành sub-queries rồi tổng hợp.
3. Nếu Advanced RAG không dùng thì vector-only retrieval trên Qdrant.
4. Nếu semantic retrieval rỗng mà query là dạng tham chiếu file này/hình này, bật reference fallback bằng scroll chunk đầu từ tài liệu đã chọn.
5. Sinh câu trả lời grounding chặt với context + history + summary + source metadata.
6. Tạo doc_map theo nhãn file_name | id:8 ký tự để frontend map citation chính xác khi trùng tên file.

### Bước 6: Persist kết quả và trả về UI

Backend nhận response từ AI Service, lưu assistant message, cập nhật usage stats, ghi source refs theo retrieved chunk vào Mongo, cập nhật summary hội thoại khi cần, rồi trả về frontend kèm contexts, doc_map, quota_info.

Frontend render markdown, tự động biến citation dạng [file] thành link nội bộ preview tài liệu tương ứng qua doc_map.

## Cấu trúc dữ liệu và nơi lưu trữ thực tế

### MinIO

Lưu file nhị phân gốc của tài liệu theo object storage. Đây là source-of-file chính.

### PostgreSQL

Lưu dữ liệu quan hệ nghiệp vụ:
- documents (metadata, hash, canonical, trạng thái)
- document_chunks
- document_embeddings (metadata qdrant_point_id, không chứa vector nặng)
- chat_sessions, chat_messages (fallback/compat)
- ai_usage_history

### Qdrant

Lưu vector 1024 chiều và payload retrieval. Query luôn filter theo user_id và document_id để giữ isolation dữ liệu người dùng.

### MongoDB

Lưu source-of-truth cho hội thoại và nguồn tri thức:
- conversations
- messages
- message_source_refs
- conversation_summaries
- conversation_state
- knowledge_sources

Mongo cũng giữ active_source_ids, source catalog, và quan hệ giữa message và nguồn trích dẫn.

### Redis

- Token blacklist cho auth backend.
- LLM helper cache (intent/query rewrite/CRAG...) ở AI Service.

## Cơ chế fallback và chống gián đoạn vận hành

Hệ thống có nhiều lớp fallback nối tiếp:
- Provider/model fallback trong ModelManager theo task profile.
- Gemini key rotation đa key và loại bỏ key invalid.
- Cooldown theo key cho rate-limit, cooldown ngắn cho 503.
- Cooldown theo model khi chạm hard-limit theo model.
- OCR retry với backoff trong Vision pipeline.
- Retrieval fallback hạ threshold khi thiếu kết quả.
- CRAG corrective retrieval khi quality insufficient.
- Reference fallback bằng scroll khi query deictic không match semantic.
- Ambiguity guard ở backend để chặn trả lời nhầm nguồn khi nhiều nguồn đang active.

## Các cấu hình quan trọng chi phối hành vi

Ở AI Service:
- ENABLE_ADVANCED_RAG (mặc định bật)
- ENABLE_QUERY_REWRITING, ENABLE_BM25_RESCORING, ENABLE_RERANKING, ENABLE_CORRECTIVE_RAG
- ENABLE_MULTI_HOP
- CHUNK_SIZE=1000, CHUNK_OVERLAP=200
- RAG_TOP_K, RAG_SCORE_THRESHOLD, RAG_MIN_SCORE_THRESHOLD
- ENABLE_MULTI_AGENT, ENABLE_PROMPT_PREPROCESSING

Ở Backend:
- ENABLE_MONGO_CHAT_HISTORY (mặc định bật)
- AI_SERVICE_URL cho internal call
- MINIO_BUCKET_NAME, QDRANT_COLLECTION_NAME

Ở deployment:
- docker-compose hiện có PostgreSQL, MongoDB, Redis, MinIO, Qdrant, Backend, AI Service, Frontend.

## Kết luận vận hành

Kiến trúc hiện tại là mô hình phân lớp rõ ràng và thực dụng cho hệ RAG production:
- Frontend tập trung UX và điều phối tương tác.
- Backend quản trị nghiệp vụ, vòng đời tài liệu, ngữ cảnh hội thoại và điều phối gọi AI.
- AI Service tập trung lõi mô hình: intent routing, multi-agent orchestration, advanced retrieval, model fallback và sinh câu trả lời grounded.

Điểm mạnh kỹ thuật nổi bật của hệ thống là canonical dedup để tối ưu chi phí xử lý lặp, advanced RAG nhiều tầng (rewrite -> retrieve -> rerank -> CRAG), và quản trị nguồn trích dẫn xuyên suốt từ Qdrant/Mongo tới UI bằng doc_map để giữ tính truy vết minh bạch trong câu trả lời.