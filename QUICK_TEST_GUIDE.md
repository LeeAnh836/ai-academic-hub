# 🚀 JVB Platform - Quick Test Guide

## ⚡ LUỒNG TEST NHANH (5 PHÚT)

### Bước 1: Login (Backend - Port 8000)

```
http://localhost:8000/docs
→ POST /api/auth/login
```

**Request:**
```json
{
  "email": "test@jvb.edu.vn",
  "password": "your_password"
}
```

**Lưu lại:**
- ✅ `access_token` 
- ✅ Click "Authorize" 🔒 → Nhập: `Bearer <access_token>`

---

### Bước 2: Upload File (Backend - Port 8000)

```
→ POST /api/documents/upload
```

**Upload:**
- File: PDF/DOCX/TXT
- Title, category, tags: để trống (tự động)

**Lưu lại:**
- ✅ `document.id` từ response
- ✅ **ĐỢI 30 giây - 1 phút** cho processing

---

### Bước 3: Check Processing Status (Backend - Port 8000)

```
→ GET /api/documents/{document_id}
```

**Kiểm tra:**
```json
{
  "id": "...",
  "is_processed": true,  // ← PHẢI LÀ true MỚI CHAT ĐƯỢC!
  "processing_status": "completed"
}
```

**Nếu `is_processed: false`:**
- Đợi thêm 20 giây
- Test lại
- Nếu vẫn false sau 2 phút → check logs

---

### Bước 4: Extract user_id từ Token

**Vào:** https://jwt.io

1. Paste `access_token` vào ô "Encoded"
2. Xem phần "Payload" → tìm `"sub"`
3. Copy giá trị `sub` = `user_id`

**Example Payload:**
```json
{
  "sub": "4d0b2b45-3688-42da-8d85-221e66590bcf",  // ← ĐÂY LÀ user_id
  "email": "test@jvb.edu.vn"
}
```

---

### Bước 5: Chat với AI (AI Service - Port 8001)

```
http://localhost:8001/docs
→ POST /api/rag/query
→ KHÔNG CẦN AUTHORIZE (no token needed)
```

**✅ HỖ TRỢ TIẾNG VIỆT 100%!** Model `command-r-plus` hiểu tốt tiếng Việt.

**Request (English):**
```json
{
  "question": "What is in this document?",
  "user_id": "4d0b2b45-3688-42da-8d85-221e66590bcf",
  "document_ids": ["8c414029-4ab6-4965-af07-3c872dc8a28c"],
  "top_k": 5,
  "score_threshold": 0.5
}
```

**Request (Tiếng Việt) - KHUYẾN NGHỊ:**
```json
{
  "question": "Tài liệu này nói về gì?",
  "user_id": "4d0b2b45-3688-42da-8d85-221e66590bcf",
  "document_ids": ["8c414029-4ab6-4965-af07-3c872dc8a28c"],
  "top_k": 5,
  "score_threshold": 0.5
}
```

**Các câu hỏi mẫu:**
- "Tài liệu này nói về gì?"
- "Tóm tắt nội dung chính"
- "Giải thích khái niệm X trong tài liệu"
- "So sánh A và B"
- "Cho ví dụ về Y"

**Response:**
```json
{
  "answer": "Tài liệu này nói về...",
  "contexts": [
    {
      "chunk_text": "...",
      "score": 0.91,
      "file_name": "lecture.pdf"
    }
  ],
  "model": "command-r-plus",
  "processing_time": 1.5
}
```

**🎉 XONG! Bạn đã chat được với AI!**

---

## ❓ FAQ

### Q1: Backend và AI Service có tự động liên kết không?

**A: ❌ KHÔNG!**

- Backend `/api/chat/messages` CHỈ lưu tin nhắn vào DB
- KHÔNG gọi AI để trả lời
- Phải gọi AI Service `/api/rag/query` riêng

**Sơ đồ:**
```
Backend (8000):
- Login ✅
- Upload file ✅
- Lưu chat history ✅

AI Service (8001):
- Chat với AI ✅ ← ĐÂY MỚI LÀ API CHAT!
- Search documents ✅
- Generate embeddings ✅
```

---

### Q2: Có Cohere API Key, có gọi được GPT-4 không?

**A: ❌ KHÔNG!**

- Code chỉ support **Cohere**
- `model_name: "gpt-4"` chỉ là **metadata** (tên thôi, không gọi OpenAI)

---

### Q3: Query trả về "Không tìm thấy tài liệu" dù đã upload?

**Nguyên nhân và giải pháp:**

**A. Document chưa được process:**
```bash
GET /api/documents/{id}
→ is_processed: false  ← ĐỢI THÊM!
```
✅ Giải pháp: Đợi 30-60 giây cho backend process xong

**B. Score threshold quá cao:**
```json
{
  "score_threshold": 0.7  ← Quá cao với câu hỏi chung chung
}
```
✅ Giải pháp: 
- Hạ xuống `0.5` hoặc `0.3` để test
- Hoặc hỏi cụ thể hơn (dùng keyword trong document)

**C. Document_id sai format:**
- Copy đúng UUID từ GET /api/documents
- Phải có dấu ngoặc kép: `["uuid-here"]`
- Không dùng document cũ đã xóa

**D. User_id không khớp:**
```json
{
  "user_id": "wrong-user-id"  ← Phải đúng với user upload
}
```
✅ Giải pháp: Extract `user_id` từ JWT token tại https://jwt.io

**E. Qdrant chưa có points:**
Check tại: http://localhost:6333/dashboard
- Collection `jvb_embeddings` phải có points > 0
- Nếu 0 points → Document processing failed

---

### Q4: AI có hiểu tiếng Việt không?

**A: ✅ CÓ! 100% hỗ trợ tiếng Việt!**

Model `command-r-plus` là multilingual:
- ✅ Hỏi bằng tiếng Việt
- ✅ Document tiếng Việt
- ✅ Trả lời bằng tiếng Việt
- ✅ Tìm kiếm semantic tiếng Việt

**Khuyến nghị:**
- Upload tài liệu tiếng Việt → Hỏi tiếng Việt
- Upload tài liệu English → Hỏi English hoặc Việt đều được
- Thực tế dùng: **Cohere Command R+** (LLM) + **embed-multilingual-v3.0** (embedding)

**Cohere Command R+:**
- Tương đương GPT-3.5
- Support Vietnamese tốt
- Miễn phí tier: 100 requests/month

---

### Q3: Tại sao MinIO có nhiều files nhưng Qdrant chỉ có 1 point?

**A: Các files khác PROCESSING FAILED!**

**Check logs:**
```powershell
docker-compose logs -f ai-service | Select-String "error|failed"
```

**Nguyên nhân thường gặp:**
1. ❌ Cohere API key invalid
2. ❌ File format không support
3. ❌ File quá lớn
4. ❌ Rate limit exceeded

**Fix:**
```powershell
# 1. Check .env
cat .env | Select-String "COHERE"

# 2. Restart services
docker-compose restart ai-service backend

# 3. Upload lại file
```

---

### Q4: `/api/chat/messages` dùng để làm gì?

**A: CHỈ để lưu conversation history**

Không để chat với AI!

**Use cases:**
- Lưu lịch sử chat
- Hiển thị chat history cũ
- Analytics & tracking

**Workflow đúng:**
```
1. POST /api/chat/messages (Backend) - Lưu user message
2. POST /api/rag/query (AI Service) - Chat với AI ← API THẬT!
3. POST /api/chat/messages (Backend) - Lưu AI response (optional)
```

---

### Q5: Check Qdrant có bao nhiêu documents?

**Option 1: Dashboard**
```
http://localhost:6333/dashboard
→ Collections → jvb_embeddings
→ Xem "Points count"
```

**Option 2: API**
```powershell
$result = curl http://localhost:6333/collections/jvb_embeddings | ConvertFrom-Json
Write-Host "Documents processed: $($result.result.points_count)"
```

**Option 3: Search by user_id**
```powershell
curl -Method POST `
  -Uri "http://localhost:6333/collections/jvb_embeddings/points/scroll" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{
    "limit": 100,
    "with_payload": true,
    "filter": {
      "must": [
        {
          "key": "user_id",
          "match": {"value": "4d0b2b45-3688-42da-8d85-221e66590bcf"}
        }
      ]
    }
  }'
```

---

## 🔍 Debug Checklist

### ❌ Document processing failed

**Triệu chứng:**
- Upload file thành công
- Sau 30s-1 phút vẫn `is_processed: false`
- `processing_status: "failed"`
- MinIO có file nhưng Qdrant không có point mới

**Bước 1: Upload file TEST và xem error**
```powershell
# Watch AI Service logs trong terminal riêng
docker-compose logs -f ai-service

# Trong terminal khác, hoặc trong browser upload 1 file nhỏ
# Xem error message chi tiết trong logs
```

**Bước 2: Check common issues**
```powershell
# 1. AI Service logs
docker-compose logs --tail=50 ai-service

# 2. Document status
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/documents

# 3. Cohere API key
cat .env | Select-String "COHERE"
```

**Common errors:**
- `401 Unauthorized` → Cohere API key invalid
- `500 Internal Server Error` → Check AI Service logs
- `Timeout` → File quá lớn

---

### ❌ RAG query không trả về contexts

**Check:**
1. Document đã processed? (`is_processed: true`)
2. `user_id` đúng với user upload?
3. `document_ids` đúng?
4. Qdrant có points? (`http://localhost:6333/dashboard`)

**Test:**
```powershell
# Lower threshold
curl -Method POST `
  -Uri "http://localhost:8001/api/rag/query" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{
    "question": "test",
    "user_id": "your-user-id",
    "document_ids": ["your-doc-id"],
    "score_threshold": 0.3
  }'
```

---

### ❌ 422 Validation Error

**Common causes:**
```json
// ❌ SAI
{
  "retrieved_chunks": [""]  // Empty string không phải UUID
}

// ✅ ĐÚNG
{
  "retrieved_chunks": []  // Empty array
}
```

---

## 📊 Services Status

```powershell
# Check all services
docker-compose ps

# Check specific service
docker-compose logs -f backend
docker-compose logs -f ai-service

# Restart service
docker-compose restart backend
docker-compose restart ai-service
```

**Services:**
- Backend: http://localhost:8000/docs
- AI Service: http://localhost:8001/docs
- Qdrant: http://localhost:6333/dashboard
- MinIO: http://localhost:9001 (admin/minioadmin)

---

## 🎯 Quick Commands

```powershell
# Start all
docker-compose up -d

# Check logs
docker-compose logs -f ai-service | Select-String "Document|error"

# Restart after code changes
docker-compose restart backend ai-service

# Check Qdrant
curl http://localhost:6333/collections/jvb_embeddings

# Check MinIO files
# Browser: http://localhost:9001

# Stop all
docker-compose down
```

---

## ✅ Success Indicators

**Document Processing:**
- ✅ MinIO có file
- ✅ Qdrant points count tăng
- ✅ `is_processed: true`
- ✅ `processing_status: "completed"`

**Chat với AI:**
- ✅ Response có `answer`
- ✅ `contexts` array có data
- ✅ `processing_time` < 3 giây
- ✅ Contexts có `score` > 0.7

---

**🎉 Happy Testing!**
