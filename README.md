# 🎓 JVB Learning Platform

AI-powered learning platform with RAG (Retrieval Augmented Generation) using FastAPI, Cohere, and Qdrant.

---

## ⚡ Quick Start (3 Steps)

### 1️⃣ Setup Environment

```powershell
# Copy .env.example files (nếu có) hoặc tạo .env files trong backend/ và ai-service/
notepad backend/.env
notepad ai-service/.env
```

**Yêu cầu:**
- Cohere API Key (Free): https://dashboard.cohere.com/api-keys

---

### 2️⃣ Start All Services

```powershell
docker compose up -d
```

Chờ 30-60 giây để tất cả services khởi động.

**Check status:**
```powershell
docker compose ps
# All services should show "Up" status
```

---

### 3️⃣ Access the Application

🌐 **Web Interface:** http://localhost:5173

**First time:**
1. Register a new account
2. Upload documents
3. Chat with AI based on your documents

---

### 3️⃣ Access Applications

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5173 | React Web Application |
| **Backend API** | http://localhost:8000/docs | REST API + Swagger UI |
| **AI Service** | http://localhost:8001/docs | AI/RAG endpoints |
| **MinIO Console** | http://localhost:9001 | Object storage (admin/minioadmin) |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Vector database |

---

### 4️⃣ Use the Application

**Option 1: Web Interface (Recommended)**
1. Open http://localhost:5173 in your browser
2. Register a new account or login
3. Upload documents in the "Documents" page
4. Chat with AI in the "AI Chat" page

**Option 2: API Testing (Advanced)**
- Backend API Docs: http://localhost:8000/docs
- AI Service Docs: http://localhost:8001/docs
- Full guide: [MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md)

---

## 🏗️ Architecture

```
┌─────────────────────────┐
│  Frontend (Port 5173)   │
│  React + Vite + TS      │
│  - Authentication UI    │
│  - Document Management  │
│  - AI Chat Interface    │
└──────────┬──────────────┘
           │ HTTP REST + JWT
           ▼
┌─────────────────────────┐
│  Backend (Port 8000)    │
│  - Authentication       │
│  - Document Management  │
│  - Chat History         │
└──────┬──────────────────┘
       │ Internal HTTP
       ▼
┌─────────────────────────┐
│  AI Service (Port 8001) │
│  - Cohere Embeddings    │
│  - RAG Pipeline         │
│  - Qdrant Search        │
└─────────────────────────┘
```

**Stack:**
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Backend:** FastAPI + PostgreSQL + Redis + MinIO
- **AI:** Cohere (LLM + Embeddings) + Qdrant (Vector DB)
- **Auth:** JWT tokens (15min access, 7 day refresh)

---

## 📚 Documentation

- [📖 API Testing Guide](API_TESTING_GUIDE.md) - Chi tiết từng API
- [⚡ Quick Test Guide](QUICK_TEST_GUIDE.md) - Test nhanh 5 phút
- [🛠️ Setup Guide](SETUP.md) - Hướng dẫn setup chi tiết

---

## 🔧 Common Issues

### ❌ `invalid api token`

**Fix:**
1. Get Cohere API key: https://dashboard.cohere.com/api-keys
2. Edit `.env`: `COHERE_API_KEY=your_key`
3. Restart: `docker-compose restart ai-service`

---

### ❌ Document processing failed (`is_processed: false`)

**Check logs:**
```powershell
docker-compose logs -f ai-service
```

**Common causes:**
- Invalid Cohere API key
- File format not supported (only PDF, DOCX, TXT)
- File too large
- Rate limit exceeded

**Fix:**
```powershell
docker-compose restart ai-service backend
```

---

### ❌ Port already in use

**Check what's using the port:**
```powershell
netstat -ano | findstr :8000
```

**Kill process:**
```powershell
taskkill /PID <PID> /F
```

---

## 🧪 Development

### View Logs
```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f ai-service
```

### Restart Services
```powershell
# All
docker-compose restart

# Specific
docker-compose restart backend ai-service
```

### Rebuild After Code Changes
```powershell
docker-compose up -d --build
```

### Stop Everything
```powershell
docker-compose down
```

### Clean Everything (including volumes)
```powershell
docker-compose down -v
```

---

## 📊 Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| Backend | `jvb_backend` | 8000 | FastAPI REST API |
| AI Service | `jvb_ai_service` | 8001 | AI/RAG processing |
| PostgreSQL | `jvb_db` | 5432 | Main database |
| Redis | `jvb_redis` | 6379 | Cache & sessions |
| MinIO | `jvb_minio` | 9000/9001 | Object storage |
| Qdrant | `jvb_qdrant` | 6333/6334 | Vector database |

---

## 🔐 Authentication

**Backend (8000):** ✅ Requires JWT token
**AI Service (8001):** ❌ No authentication (internal service)

**Flow:**
1. Frontend → Backend (with JWT token)
2. Backend → Verify token → Extract user_id
3. Backend → AI Service (with user_id, no token)
4. AI Service → Process & return results

---

## 🎯 Features

- ✅ User authentication (JWT)
- ✅ Document upload (PDF, DOCX, TXT)
- ✅ Automatic document processing (chunking + embedding)
- ✅ Vector search with Qdrant
- ✅ RAG chat with Cohere
- ✅ Chat history management
- ✅ Multi-language support (Vietnamese optimized)

---

## 🚀 Production Deployment

**TODO:**
- [ ] Add HTTPS/TLS
- [ ] Use production-grade secrets
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline
- [ ] Add rate limiting
- [ ] Configure CDN for static assets

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

---

**Made with ❤️ using FastAPI + Cohere + Qdrant**
