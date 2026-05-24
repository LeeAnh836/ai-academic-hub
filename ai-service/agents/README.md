# AI Agents

Thư mục này chứa các agent chuyên biệt cho AI Service. Mỗi agent tập trung vào một loại tác vụ để việc điều phối rõ ràng hơn và dễ mở rộng hơn.

## Vai trò chung

- Chuẩn hóa cách xử lý từng kiểu truy vấn.
- Tận dụng memory và ngữ cảnh hội thoại.
- Tách logic xử lý tài liệu, phân tích dữ liệu và QA tổng quát.
- Cho phép mở rộng thêm agent mới mà không làm phình orchestration chính.

## Các agent hiện có

### `__init__.py`

Đóng vai trò nền tảng chung cho agent, bao gồm lớp cơ sở, state và các tiện ích chung.

### `prompt_preprocessor.py`

Tiền xử lý câu hỏi trước khi đưa vào classifier hoặc orchestrator.

Chức năng chính:

- làm rõ câu trả lời ngắn, mơ hồ hoặc phụ thuộc ngữ cảnh.
- tận dụng lịch sử hội thoại để bổ sung ý định.
- chuẩn hóa prompt cho các bước phía sau.

### `document_qa_agent.py`

Agent hỏi đáp theo tài liệu.

Nhiệm vụ:

- truy xuất context từ Qdrant.
- tổng hợp câu trả lời có dẫn nguồn.
- có cơ chế fallback khi semantic search không đủ dữ liệu.
- phù hợp với các truy vấn như tóm tắt, giải thích, trích dẫn tài liệu.

### `data_analysis_agent.py`

Agent phân tích dữ liệu CSV/Excel.

Luồng thường dùng:

1. đọc dữ liệu.
2. hiểu cấu trúc bảng.
3. tạo pandas code.
4. chạy code trong môi trường cô lập.
5. trả kết quả và code sinh ra.

### `general_qa_agent.py`

Agent trả lời câu hỏi tổng quát.

Nó phù hợp cho:

- giải thích khái niệm.
- trả lời kiến thức chung.
- kết hợp các tool phụ trợ khi cần.

### `code_executor.py`

Thành phần thực thi code Python an toàn trong container.

Đặc điểm:

- môi trường cô lập.
- giới hạn tài nguyên.
- có timeout.
- không cho phép network truy cập trực tiếp.

## Luồng xử lý điển hình

```text
User query
  -> Prompt preprocessor
  -> Intent/classification layer
  -> Master orchestrator
  -> Specialized agent
  -> Memory update
  -> Response
```

## Memory và state

Các agent đều có thể đọc/ghi memory để:

- lưu trạng thái phiên làm việc.
- nhớ file hoặc task gần nhất.
- phục hồi ngữ cảnh khi người dùng hỏi tiếp.

## Khi muốn thêm agent mới

1. Tạo file agent mới trong thư mục này.
2. Kế thừa lớp base hoặc pattern chung hiện có.
3. Đăng ký agent trong orchestrator chính.
4. Thêm logic intent/classification nếu cần.
5. Cập nhật router hoặc endpoint tương ứng trong AI Service.

## Tài liệu liên quan

- `services/master_orchestrator.py`
- `services/orchestrator.py`
- `services/intent_classifier.py`
- `routers/agent.py`
