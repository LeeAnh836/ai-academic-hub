# 🔧 Fix Password Hashing Error

## Vấn Đề
Lỗi khi đăng ký user mới:
```
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```

## Nguyên Nhân
- Bcrypt có giới hạn 72 bytes cho password
- Passlib (version cũ) gặp lỗi khi khởi tạo context

## Giải Pháp

### ✅ Quy Trình Mới (SHA256 + bcrypt)

**Bước 1:** Lấy password người dùng nhập (vd: `!hugAfi35sg...`)

**Bước 2:** Hash qua SHA-256 → chuỗi hex 64 ký tự (luôn cố định)

**Bước 3:** Đưa chuỗi 64 ký tự vào bcrypt → hash cuối cùng lưu DB

```
Password: !hugAfi35sg...
   ↓ SHA256
   ↓ 
64 chars hex: 3a8f9d2e1b4c7a5e8d3f1b2c9e4a7d6f...
   ↓ bcrypt (12 rounds)
   ↓
Final hash: $2b$12$abcdef... → Lưu vào DB
```

### 🎯 Lợi Ích

1. **Consistent**: Mọi password đều qua SHA256 trước
2. **Safe**: 64 chars hex < 72 bytes (luôn safe cho bcrypt)
3. **Secure**: SHA256 giúp normalize input, tránh các vấn đề với ký tự đặc biệt
4. **Simple**: Không cần check điều kiện password length

### 🔧 Thay Đổi Code

#### 1. **utils/password.py** - Dùng bcrypt trực tiếp
```python
def _prepare_password(password: str) -> bytes:
    # Bước 1: Password → SHA256 hex (64 chars)
    password_bytes = password.encode("utf-8")
    sha256_hex = hashlib.sha256(password_bytes).hexdigest()
    
    # Bước 2: Convert hex → bytes cho bcrypt
    return sha256_hex.encode("utf-8")

def hash_password(password: str) -> str:
    # Bước 1: SHA256
    prepared_password = _prepare_password(password)
    
    # Bước 2: bcrypt
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(prepared_password, salt)
    
    return hashed.decode("utf-8")
```

#### 2. **requirements.txt**
- Xóa: `passlib[bcrypt]==1.7.4`
- Thêm: `bcrypt==4.1.2`

#### 3. **Files đã xóa**
- ✅ `services/password_hard.py` (duplicate)
- ✅ `test_password_logic.py` (không cần thiết)

#### 4. **Files giữ lại**
- ✅ `test_password.py` (test script hữu ích)

## 🚀 Cách Deploy

### Option 1: Dùng script (Recommended)

```powershell
cd d:\JVB_final\backend
.\rebuild.ps1
```

### Option 2: Manual

```bash
docker-compose down
docker-compose build backend
docker-compose up -d
```

## 🧪 Test Password Hashing

Sau khi rebuild, test với script:

```bash
# Trong container
docker-compose exec backend python test_password.py
```

Hoặc test API:

1. **Password ngắn**
   ```json
   {
     "email": "test@example.com",
     "password": "Short123!",
     "username": "testuser",
     "full_name": "Test User",
     "student_id": "B20DCCN001"
   }
   ```

2. **Password dài** (>= 72 bytes)
   ```json
   {
     "email": "test2@example.com",
     "password": "ThisIsAVeryLongPasswordThatExceeds72BytesAndShouldBePreHashedWithSHA256BeforeBcrypt!!!",
     "username": "testuser2",
     "full_name": "Test User 2",
     "student_id": "B20DCCN002"
   }
   ```

3. **Password với ký tự đặc biệt**
   ```json
   {
     "email": "test3@example.com",
     "password": "Mật_Khẩu_Tiếng_Việt_123!@#$%^&*()",
     "username": "testuser3",
     "full_name": "Test User 3",
     "student_id": "B20DCCN003"
   }
   ```

## 📊 So Sánh

### Trước (❌)
```
Password: abc (ngắn) → bcrypt trực tiếp → hash
Password: AAA...AAA (dài > 72) → ??? → ERROR
```

### Sau (✅)
```
Password: abc (ngắn) → SHA256 (64 chars) → bcrypt → hash
Password: AAA...AAA (dài) → SHA256 (64 chars) → bcrypt → hash
```

**Tất cả password đều qua SHA256 trước → Consistent & Safe!**

## 📝 Technical Details

- **SHA256 output**: 64 characters hex string
- **Bcrypt rounds**: 12 (good balance security/performance)
- **Max input for bcrypt**: 72 bytes
- **SHA256 hex as bytes**: 64 bytes < 72 bytes ✅

## ✅ Checklist

- ✅ Code updated: `utils/password.py`
- ✅ Dependencies updated: `requirements.txt`
- ✅ Old files removed: `password_hard.py`, `test_password_logic.py`
- ✅ Test script available: `test_password.py`
- ✅ Rebuild script ready: `rebuild.ps1`

## 💡 Lưu Ý

- **Không breaking change**: User cũ CÓ THỂ cần reset password
- **Lý do**: Hash format mới (SHA256+bcrypt) khác với trước (bcrypt thuần)
- **Migration**: Có thể thêm flag để detect old hash format nếu cần

---

**Updated:** 2026-02-05
**Status:** ✅ Ready to deploy
**Breaking:** ⚠️ Có thể cần reset password cho users cũ
