# 🧪 HƯỚNG DẪN TEST THỦ CÔNG - JVB AI SYSTEM

## 📋 MỤC LỤC
1. [Tổng quan kiến trúc](#tổng-quan-kiến-trúc)
2. [Test AI Service (Port 8001)](#test-ai-service-port-8001)
3. [Test Backend API (Port 8000)](#test-backend-api-port-8000)
4. [Flow thực tế: Frontend → Backend → AI Service](#flow-thực-tế)
5. [Troubleshooting](#troubleshooting)

---

## 🏗️ TỔNG QUAN KIẾN TRÚC

### **Cổng dịch vụ:**
```
Frontend (React) 
    ↓ HTTP Request
Backend (Port 8000) ← Authentication, Database, Business Logic
    ↓ Internal Request
AI Service (Port 8001) ← LLM Processing, RAG, Embeddings
    ↓
Qdrant (Vector DB)
```

### **Khi nào test cổng nào?**

| Mục đích | Cổng | Swagger UI | Ghi chú |
|----------|------|------------|---------|
| **Test AI thuần** | 8001 | http://localhost:8001/docs | Test trực tiếp RAG, chat, embedding |
| **Test API thật** | 8000 | http://localhost:8000/docs | Có authentication, cần token |
| **Production** | 8000 | - | Frontend chỉ gọi backend, không gọi ai-service |

---

## 🤖 TEST AI SERVICE (Port 8001)

> ⚠️ **LƯU Ý**: AI Service không có authentication - chỉ dùng để test nội bộ!

### **1. Truy cập Swagger UI**
```
http://localhost:8001/docs
```

---

### **2. TEST CHAT THƯỜNG (Không có documents)**

#### **Endpoint:** `POST /api/rag/chat`

#### **Request Body:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Giải thích về thuật toán sắp xếp nhanh (Quick Sort)"
    }
  ],
  "user_id": "test-user-001"
}
```

#### **Dùng Swagger:**
1. Click vào endpoint `/api/rag/chat`
2. Click **"Try it out"**
3. Paste JSON trên vào body
4. Click **"Execute"**

#### **Response mẫu:**
```json
{
  "message": "Quick Sort là thuật toán sắp xếp chia để trị...",
  "model": "gemini-flash",
  "tokens_used": 245,
  "thinking_time": 1.2
}
```

#### **Test cases khác:**

**a) Chat đa lượt:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Code Python cho Quick Sort"
    },
    {
      "role": "assistant",
      "content": "Đây là code Quick Sort:\n```python\ndef quicksort(arr):..."
    },
    {
      "role": "user",
      "content": "Giải thích dòng partition(arr, low, high)"
    }
  ],
  "user_id": "test-user-002"
}
```

**b) Bài tập toán:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Giải phương trình: 2x^2 + 5x - 3 = 0"
    }
  ],
  "user_id": "test-homework"
}
```
→ Orchestrator sẽ tự động phân loại `homework_solver` và dùng Gemini Pro

**c) Câu hỏi tiếng Việt:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Tại sao trời xanh?"
    }
  ],
  "user_id": "test-vietnamese"
}
```

---

### **3. TEST RAG QUERY (Có documents từ Qdrant)**

#### **Endpoint:** `POST /api/rag/query`

> ⚠️ **YÊU CẦU**: Phải có documents đã được upload và embedded trong Qdrant!

#### **Request Body:**
```json
{
  "question": "Các nguyên tắc thiết kế SOLID là gì?",
  "document_ids": ["doc-001", "doc-002"],
  "user_id": "test-user-003",
  "top_k": 5
}
```

#### **Giải thích fields:**
- `question`: Câu hỏi của user
- `document_ids`: Array các document IDs đã upload (lấy từ backend)
- `user_id`: ID của user (để filter contexts)
- `top_k`: Số lượng context chunks lấy từ Qdrant (default: 3)

#### **Response mẫu:**
```json
{
  "answer": "Các nguyên tắc SOLID bao gồm:\n1. Single Responsibility Principle...",
  "contexts": [
    {
      "text": "SOLID là viết tắt của 5 nguyên tắc thiết kế...",
      "document_id": "doc-001",
      "score": 0.89
    }
  ],
  "model": "gemini-pro",
  "tokens_used": 1250
}
```

#### **Test case: Document dài (test 1M tokens context):**
```json
{
  "question": "Tóm tắt toàn bộ tài liệu về Design Patterns",
  "document_ids": ["doc-design-patterns-full"],
  "user_id": "test-long-context",
  "top_k": 20
}
```
→ Gemini 2.5 có thể xử lý 20-50 chunks cùng lúc (Groq chỉ 3-5)

---

### **4. TEST EMBEDDING SERVICE**

#### **Endpoint:** `POST /api/embeddings/embed`

#### **Request Body:**
```json
{
  "texts": [
    "Python là ngôn ngữ lập trình phổ biến",
    "Machine Learning is a subset of AI"
  ]
}
```

#### **Response:**
```json
{
  "embeddings": [
    [0.123, -0.456, 0.789, ...],  // Vector 1024 dimensions
    [0.234, -0.567, 0.890, ...]
  ],
  "model": "cohere-embed-multilingual-v3.0",
  "dimensions": 1024
}
```

---

### **5. TEST DOCUMENT UPLOAD**

#### **Endpoint:** `POST /api/documents/upload`

> 📝 **Dùng Swagger** vì cần upload file!

#### **Trong Swagger:**
1. Click endpoint `/api/documents/upload`
2. Click **"Try it out"**
3. Click **"Choose File"** → Chọn file PDF/DOCX
4. Nhập `user_id`: "test-user-004"
5. Nhập `document_id`: "doc-test-001"
6. Click **"Execute"**

#### **Response:**
```json
{
  "document_id": "doc-test-001",
  "chunks_created": 15,
  "total_tokens": 2450,
  "status": "success"
}
```

#### **Test files nên thử:**
- PDF nhỏ (~5 pages) - Test chunking cơ bản
- DOCX có hình ảnh - Test document parsing
- TXT dài (>10k words) - Test large context

---

## 🔐 TEST BACKEND API (Port 8000)

> ✅ **Production-ready**: Có authentication, database, business logic

### **1. Truy cập Swagger UI**
```
http://localhost:8000/docs
```

---

### **2. ĐĂNG KÝ & ĐĂNG NHẬP (Bắt buộc trước khi test)**

#### **a) Đăng ký tài khoản:**

**Endpoint:** `POST /api/auth/register`

```json
{
  "email": "test@example.com",
  "password": "Test123456!",
  "full_name": "Nguyen Van Test",
  "role": "student"
}
```

**Response:**
```json
{
  "id": "user-uuid-123",
  "email": "test@example.com",
  "full_name": "Nguyen Van Test",
  "role": "student"
}
```

#### **b) Đăng nhập lấy token:**

**Endpoint:** `POST /api/auth/login`

```json
{
  "email": "test@example.com",
  "password": "Test123456!"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid-123",
    "email": "test@example.com"
  }
}
```

#### **c) Authorize trong Swagger:**
1. Copy `access_token` từ response
2. Click nút **"Authorize"** (góc trên bên phải Swagger UI)
3. Paste token vào: `Bearer eyJhbGci...`
4. Click **"Authorize"** → **"Close"**

---

### **3. UPLOAD TÀI LIỆU**

#### **Endpoint:** `POST /api/documents/upload`

> ⚠️ **Cần token!** Phải authorize trước.

#### **Trong Swagger:**
1. Authorize với token
2. Click endpoint `/api/documents/upload`
3. **"Try it out"**
4. Click **"Choose File"** → Chọn file PDF/DOCX/TXT
5. Click **"Execute"**

#### **Response:**
```json
{
  "id": "doc-abc-xyz-123",
  "user_id": "user-uuid-456",
  "title": "oop-java.pdf",
  "description": null,
  "filename": "oop-java.pdf",
  "file_path": "documents/user-uuid-456/oop-java.pdf",
  "file_size": 2048576,
  "file_type": "pdf",
  "status": "processed",
  "chunks_count": 25,
  "created_at": "2026-02-11T10:30:00Z"
}
```

> 🎯 **QUAN TRỌNG**: 
> - **Copy field `id`** từ response này
> - Dùng `id` này cho `context_documents` ở bước 4 (tạo session)
> - `status` phải là `"processed"` mới query được
> - Nếu `status: "pending"`, đợi vài giây rồi GET lại document

---

### **4. TEST CHAT VỚI TÀI LIỆU (RAG)**

> 🎯 **QUAN TRỌNG**: Endpoint chính để chat + RAG!

#### **Flow hoàn chỉnh:**
1. Tạo chat session
2. Dùng `/ask` endpoint để hỏi AI (tự động query RAG + save messages)

---

#### **Bước 1: Tạo Chat Session**

**Endpoint:** `POST /api/chat/sessions`

> 📝 **Trong Swagger UI:**
> 1. Click **"Try it out"**
> 2. Body mẫu sẽ hiện ra, bạn **CÓ THỂ SỬA TRỰC TIẾP**
> 3. Thay `context_documents` bằng ID tài liệu bạn vừa upload (bước 3)

**Request Body (ví dụ):**
```json
{
  "title": "Học OOP Java",
  "session_type": "document_qa",
  "context_documents": [
    "PASTE_DOCUMENT_ID_TỪ_BƯỚC_3_VÀO_ĐÂY"
  ],
  "model_name": "gemini-2.5-flash"
}
```

> 💡 **Giải thích fields:**
> - `title`: Tên session (tùy chọn, có thể null)
> - `session_type`: 
>   - `"document_qa"` = Chat với tài liệu (có RAG)
>   - `"general"` = Chat thường (không RAG)
> - `context_documents`: Array các UUID của documents đã upload
>   - Lấy từ response của `/api/documents/upload` (field `id`)
>   - Để `[]` nếu chat thường
> - `model_name`: Tên model (default: "gemini-2.5-flash")

**Response:**
```json
{
  "id": "session-abc-123",
  "user_id": "user-xyz-456",
  "title": "Học OOP Java",
  "session_type": "document_qa",
  "context_documents": ["doc-id-bạn-vừa-paste"],
  "model_name": "gemini-2.5-flash",
  "message_count": 0,
  "total_tokens_used": 0,
  "created_at": "2026-02-11T10:35:00Z"
}
```

> ⚠️ **LƯU Ý**: Copy `id` từ response này để dùng cho bước 2!

--🔧 **Trong Swagger UI:**
> 1. Thay `{session_id}` = ID từ bước 1
> 2. Click **"Try it out"**
> 3. Sửa body (giải thích bên dưới)
> 4. Click **"Execute"**

> ✨ **Endpoint này TỰ ĐỘNG:**
> - Query RAG từ documents trong `context_documents`
> - Save user message vào DB
> - Gọi AI Service internally
> - Save AI response vào DB
> - Return đầy đủ conversation + contexts

**Request Body (có thể sửa trực tiếp):**
```json
{
  "question": "4 nguyên tắc của OOP là gì?",
  "document_ids": null,
  "top_k": 5,
  "score_threshold": 0.5,
  "temperature": 0.7,
  "max_tokens": 2000
}
```

> 📝 **Giải thích fields (CÓ THỂ SỬA trong Swagger):**
> 
> **Required:**
> - `question`: Câu hỏi của bạn (bắt buộc)
> 
> **Optional (để mặc định cũng OK):**
> - `document_ids`: 
>   - `null` = Dùng tất cả documents từ `context_documents` của session
>   - `["doc-id-1", "doc-id-2"]` = Chỉ query 2 documents này
> - `top_k`: Số context chunks lấy từ Qdrant
>   - Default: 5
>   - Nên set: 3-10
>   - Càng lớn = nhiều context hơn nhưng chậm hơn
> - `score_threshold`: Điểm tối thiểu của context
>   - Default: 0.5
>   - Range: 0.0-1.0
>   - Càng cao = context chất lượng cao hơn nhưng ít hơn
> - `temperature`: Độ sáng tạo của AI
>   - Default: 0.7
>   - Thấp (0.1-0.3): Chính xác, ít sáng tạo
>   - Cao (0.8-1.0): Sáng tạo, đa dạng
> - `max_tokens`: Độ dài response tối đa
>   - Default: 2000
>   - Range: 100-8000
> - `question`: Câu hỏi của user (required)
> - `document_ids`: Filter documents cụ thể. Nếu `null`, dùng `context_documents` từ session
> - `top_k`: Số chunks retrieve từ Qdrant (default: 5)
> - `score_threshold`: Điểm tối thiểu của context (default: 0.5)
> - `temperature`: LLM temperature (default: 0.7)
> - `max_tokens`: Max response length (default: 2000)

**Response:**
```json
{
  "session_id": "session-uuid-789",
  "user_message": {
    "id": "msg-user-uuid",
    "role": "user",
    "content": "4 nguyên tắc của OOP là gì?",
    "created_at": "2026-02-11T10:36:00Z"
  },
  "ai_message": {
    "id": "msg-ai-uuid",
    "role": "assistant",
    "content": "4 nguyên tắc cơ bản của OOP bao gồm:\n\n1. **Encapsulation (Đóng gói)**...",
    "total_tokens": 450,
    "created_at": "2026-02-11T10:36:02Z"
  },
  "contexts": [
    {
      "chunk_id": "chunk-uuid-1",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "chunk_text": "OOP có 4 nguyên tắc cơ bản: Encapsulation...",
      "chunk_index": 5,
      "score": 0.89,
      "file_name": "oop-java.pdf",
      "title": "Giáo trình OOP"
    }
  ],
  "processing_time": 2.5,
  "model_used": "gemini-2.5-flash"
}
```

---

#### **Bước 3: Xem lịch sử chat**

**Endpoint:** `GET /api/chat/sessions/{session_id}/messages`

**Response:**
```json
[
  {
    "id": "msg-user-uuid",
    "role": "user",
    "content": "4 nguyên tắc của OOP là gì?",
    "created_at": "2026-02-11T10:36:00Z"
  },
  {
    "id": "msg-ai-uuid",
    "role": "assistant",
    "content": "4 nguyên tắc cơ bản của OOP bao gồm...",
    "total_tokens": 450,
    "created_at": "2026-02-11T10:36:02Z"
  }
]
```

---

### **5. TEST CHAT THƯỜNG (KHÔNG CÓ DOCUMENTS)**

#### **Tạo session chat thường:**

```json
{
  "title": "Trò chuyện thường",
  "session_type": "general",
  "model_name": "gemini-2.5-flash"
}
```

#### **Hỏi AI:**

```json
{
  "question": "2 + 2 bằng mấy?",
  "top_k": 0
}
```
→ Backend gọi `/api/rag/chat` (không query RAG, chỉ chat)

---

## 🔄 FLOW THỰC TẾ: Frontend → Backend → AI Service

### **Kiến trúc:**

```
┌─────────────┐
│  Frontend   │
│  (React)    │
└──────┬──────┘
       │ 1. HTTP + JWT Token
       ↓
┌─────────────────────┐
│  Backend (8000)     │
│  ├─ Auth            │ ← Verify token, check permissions
│  ├─ Database        │ ← Save messages, documents
│  └─ ai_service.py   │ ← Calls AI Service internally
└──────┬──────────────┘
       │ 2. Internal HTTP (no auth)
       ↓
┌─────────────────────┐
│  AI Service (8001)  │
│  ├─ Orchestrator    │ ← Intent classification
│  ├─ Model Manager   │ ← Gemini/Groq
│  └─ Qdrant Client   │ ← Vector search
└─────────────────────┘
```

### **Code trong Backend (đã có sẵn):**

File: `backend/services/ai_service.py`

```python
class AIService:
    def __init__(self):
        self.ai_service_url = settings.AI_SERVICE_URL  # http://ai-service:8001
    
    async def chat(self, messages: List[dict], user_id: str):
        """Gọi AI Service để chat"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ai_service_url}/api/rag/chat",
                json={
                    "messages": messages,
                    "user_id": user_id
                }
            )
            return response.json()
    
    async def query_documents(self, question: str, document_ids: List[str], user_id: str):
        """Gọi AI Service để query RAG"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ai_service_url}/api/rag/query",
                json={
                    "question": question,
                    "document_ids": document_ids,
                    "user_id": user_id
                }
            )
            return response.json()
```

### **Khi có Frontend:**

1. **Frontend gọi Backend (8000):**
   ```javascript
   // Tạo chat session
   fetch('http://localhost:8000/api/chat/sessions', {
     method: 'POST',
     headers: {
       'Authorization': 'Bearer ' + token,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       title: "Học OOP",
       session_type: "document_qa",
       context_documents: ["doc-456"]
     })
   })
   
   // Hỏi AI
   fetch('http://localhost:8000/api/chat/sessions/session-123/ask', {
     method: 'POST',
     headers: {
       'Authorization': 'Bearer ' + token,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       question: "Giải thích OOP",
       top_k: 5
     })
#### **Option A: Test trực tiếp AI Service (Port 8001 - Nhanh, không cần auth)**

```bash
POST http://localhost:8001/api/rag/chat
{
  "messages": [{"role": "user", "content": "Xin chào"}],
  "user_id": "test-001"
}
```

#### **Option B: Test qua Backend (Port 8000 - Production flow)**

**Trong Swagger UI (http://localhost:8000/docs):**

```json
// Bước 1: Tạo session (POST /api/chat/sessions)
{
  "title": "Chat thường",       // Có thể sửa thành gì cũng được
  "session_type": "general",    // Để "general" cho chat thường
  "context_documents": [],      // [] = không có tài liệu
  "model_name": "gemini-2.5-flash"
}
→ Copy "id" từ response

// Bước 2: Hỏi AI (POST /api/chat/sessions/{session-id-vừa-copy}/ask)
{
**Trong Swagger UI (http://localhost:8000/docs):**

```bash
# ========================================
# BƯỚC 1: Upload file
# ========================================
POST /api/documents/upload
Authorization: Bearer {your-token}

[Click "Choose File" → Chọn PDF/DOCX]
[Click "Execute"]

→ Response: 
{
  "id": "doc-abc-123",  ← COPY ID NÀY!
  "filename": "your-file.pdf",
  "status": "processed",
  "chunks_count": 25
}

# ========================================
# BƯỚC 2: Tạo chat session
# ========================================
POST /api/chat/sessions
Authorization: Bearer {your-token}

Request body (SỬA trực tiếp trong Swagger):
{
  "title": "Hỏi về tài liệu",
  "session_type": "document_qa",
  "context_documents": [
    "doc-abc-123"  ← PASTE ID TỪ BƯỚC 1
  ]
}

→ Response:
{
  "id": "session-xyz-456",  ← COPY ID NÀY!
  ...
}

# ========================================
# BƯỚC 3: Hỏi AI với RAG
# ========================================
POST /api/chat/sessions/session-xyz-456/ask  ← PASTE SESSION ID
Authorization: Bearer {your-token}

Request body (SỬA câu hỏi tùy ý):
{
  "question": "Nội dung chính của tài liệu là gì?",
  "top_k": 5
}

→ Response:
{
  "ai_message": {
    "content": "Tài liệu nói về...",
    "total_tokens": 450
  },
  "contexts": [
    {
      "chunk_text": "Context từ tài liệu...",
      "score": 0.89
    }
  ]
}
```

---

#### **Option B: Test nhanh trên AI Service (Port 8001 - No auth)**

```bash
POST http://localhost:8001/api/rag/query

{
  "question": "Nội dung chính là gì?",
  "document_ids": ["doc-abc-123"],  ← ID từ backend upload
```bash
# Bước 1: Upload file (Backend)
POST http://localhost:8000/api/documents/upload
Authorization: Bearer {token}
[File upload]
→ Response: {"id": "doc-123", "chunks_count": 10}

# Bước 2: Tạo chat session (Backend)
POST http://localhost:8000/api/chat/sessions
Authorization: Bearer {token}
{
  "title": "Hỏi về tài liệu",
  "session_type": "document_qa",
  "context_documents": ["doc-123"]
}
→ Response: {"id": "session-456"}

# Bước 3: Hỏi AI với RAG (Backend - RECOMMENDED)
POST http://localhost:8000/api/chat/sessions/session-456/ask
Authorization: Bearer {token}
{
  "question": "Nội dung chính là gì?",
  "top_k": 5
}

# Hoặc test trực tiếp AI Service (no auth, development only)
POST http://localhost:8001/api/rag/query
{
  "question": "Nội dung chính là gì?",
  "document_ids": ["doc-123"],
  "user_id": "test-001"
}
```

### **Test 3: Multi-turn conversation**

```bash
# Bước 1: Tạo chat session
POST http://localhost:8000/api/chat/sessions
Authorization: Bearer {token}
{
  "title": "Học Python Basic",
  "session_type": "general"
}
→ Response: {"id": "session-456"}

# Câu hỏi 1
POST http://localhost:8000/api/chat/sessions/session-456/ask
Authorization: Bearer {token}
{"question": "Python là gì?"}

# Câu hỏi 2
POST http://localhost:8000/api/chat/sessions/session-456/ask
{"question": "So sánh Python và Java"}

# Câu hỏi 3
POST http://localhost:8000/api/chat/sessions/session-456/ask
{"question": "Cho ví dụ code Python đơn giản"}

# Xem lịch sử chat
GET http://localhost:8000/api/chat/sessions/session-456/messages
Authorization: Bearer {token}
```

---

## 🐛 TROUBLESHOOTING

### **1. Error: "401 Unauthorized" trên port 8000**

**Nguyên nhân:** Chưa login hoặc token hết hạn

**Giải pháp:**
```bash
# 1. Login lại
POST http://localhost:8000/api/auth/login
{"email": "test@example.com", "password": "Test123456!"}

# 2. Copy token mới
# 3. Authorize lại trong Swagger
```

### **2. Error: "404 Not Found" cho chat session/document**

**Nguyên nhân:** Session/Document không tồn tại hoặc không có quyền truy cập

**Giải pháp:**
```bash
# Kiểm tra document status
GET http://localhost:8000/api/documents/{document_id}
Authorization: Bearer {token}

# Status phải là "processed", không phải "pending" hoặc "failed"

# Kiểm tra session tồn tại
GET http://localhost:8000/api/chat/sessions/{session_id}
Authorization: Bearer {token}

# Đảm bảo user_id của session khớp với current user
```

### **3. Error: "Connection refused" khi gọi AI Service**

**Nguyên nhân:** Container ai-service chưa chạy

**Giải pháp:**
```powershell
# Check containers
docker ps

# Restart ai-service
docker-compose restart ai-service
```

### **4. Response từ AI Service trống hoặc lỗi**

**Nguyên nhân:** 
- Gemini API key hết quota
- Qdrant không có data

**Giải pháp:**
```bash
# Check logs
docker logs jvb_ai_service --tail 50

# Kiểm tra Gemini key
curl "https://generativelanguage.googleapis.com/v1/models?key=YOUR_KEY"

# Kiểm tra Qdrant
curl http://localhost:6333/collections/jvb_embeddings
```

### **5. UTF-8 encoding lỗi trong PowerShell**

**Triệu chứng:** Tiếng Việt hiển thị: `ChÃ o báº¡n`

**Giải pháp:**
```powershell
# Set UTF-8 cho PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Hoặc dùng curl/Postman thay vì Invoke-RestMethod
```

---

## 📊 CHECKLIST TEST HOÀN CHỈNH

### **AI Service (8001):**
- [ ] `/api/rag/chat` - Chat thường
- [ ] `/api/rag/chat` - Chat nhiều lượt
- [ ] `/api/rag/query` - Query với document
- [ ] `/api/documents` - List documents
- [ ] `/api/documents/{id}` - Xem document detail
- [ ] `/api/chat/sessions` - Tạo session (POST) / List sessions (GET)
- [ ] `/api/chat/sessions/{id}` - Xem session detail
- [ ] `/api/chat/sessions/{id}/ask` - **Hỏi AI với RAG** ⭐
- [ ] `/api/chat/sessions/{id}/messages` - Xem lịch sử c
- [ ] `/api/auth/register` - Đăng ký
- [ ] `/api/auth/login` - Đăng nhập
- [ ] `/api/documents/upload` - Upload file (Backend)
- [ ] `/api/documents/{id}` - Xem document info
- [ ] `/api/documents/{id}/query` - Query RAG
- [ ] `/api/chat/conversations` - Tạo conversation
- [ ] `/api/chat/conversations/{id}/messages` - Chat
- [ ] `/api/users/me` - Xem profile

### **Integration:**
- [ ] Frontend → Backend → AI Service flow
- [ ] Authentication hoạt động đúng
- [ ] Document upload + embedding + query
- [ ] Multi-turn conversation
- [ ] Error handling

---

## 🎯 KẾT LUẬN

### **Hiện tại (Development):**
- ✅ Test trực tiếp trên **port 8001** - Nhanh, không cần auth
- ✅ Test flow thật trên **port 8000** - Có auth, giống production

### **Khi có Frontend:**
- ✅ **Backend/services/ai_service.py đã sẵn sàng** - Không cần config thêm
- ✅ Frontend chỉ gọi Backend (8000)
- ✅ Backend tự động gọi AI Service (8001) internally
- ✅ Không expose AI Service ra ngoài internet

### **Bước tiếp theo:**
1. Test đầy đủ các endpoint theo checklist
2. Upload vài tài liệu mẫu
3. Test RAG với documents
4. Sẵn sàng integrate Frontend

---

**Tài liệu version:** 1.0 - Feb 11, 2026
**Gemini Model:** 2.5 Flash (1M tokens context)
**Groq Model:** Llama 3.3 70B (8k tokens context)
