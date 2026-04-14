# Báo Cáo Kiến Trúc Hệ Thống FE-BE-AI và Cơ Chế Vận Hành RAG

Tài liệu này trình bày lại toàn bộ kiến trúc của hệ thống theo một mạch liền xuyên suốt, bắt đầu từ bức tranh tổng quan giữa Frontend, Backend và AI Service, sau đó đi sâu vào quy trình xử lý tài liệu của AI, nơi file được lưu trữ, cách file được đọc theo từng định dạng, cách chunk và embedding được tạo, cơ chế điều phối mô hình, và cấu trúc RAG đang vận hành thực tế trong dự án. Mục tiêu là để người đọc có thể hiểu hệ thống như một dòng chảy kỹ thuật thống nhất, thay vì nhìn từng mảnh rời rạc.

## Tổng quan kiến trúc FE, BE và AI trong hệ thống hiện tại

Ở lớp giao diện người dùng, Frontend được xây dựng bằng React kết hợp TypeScript và Vite, đóng vai trò là điểm chạm duy nhất giữa người dùng và nền tảng. Người dùng đăng nhập, quản lý tài liệu, mở phiên chat và gửi câu hỏi ngay trên giao diện này. Frontend không xử lý AI trực tiếp mà tập trung vào trải nghiệm, điều phối tương tác và gửi request HTTP có xác thực JWT về Backend.

Backend là lớp điều phối nghiệp vụ trung tâm, được xây dựng bằng FastAPI. Mọi thao tác mang tính nghiệp vụ như xác thực người dùng, phân quyền, quản lý phiên chat, quản lý metadata tài liệu, thống kê sử dụng và lưu lịch sử hội thoại đều nằm ở lớp này. Khi có thao tác liên quan tới AI, Backend không nhúng logic suy luận phức tạp ngay trong mình mà gọi sang AI Service qua internal HTTP. Thiết kế tách lớp này giúp backend giữ vai trò “hệ điều hành nghiệp vụ”, còn AI Service giữ vai trò “động cơ suy luận và truy xuất tri thức”.

AI Service là microservice chuyên xử lý các tác vụ AI: đọc và chuẩn hóa tài liệu, OCR ảnh/PDF scan, cắt chunk, tạo embedding, lưu vector vào Qdrant, phân loại intent, điều phối multi-agent và sinh câu trả lời theo cơ chế RAG. Vì được tách riêng thành service độc lập, AI có thể mở rộng hoặc tối ưu mà không làm xáo trộn lớp nghiệp vụ của backend.

Bên dưới ba lớp FE, BE, AI là các thành phần hạ tầng chuyên biệt. MinIO lưu file gốc theo kiểu object storage, PostgreSQL lưu metadata quan hệ và lịch sử nghiệp vụ, Qdrant lưu vector để tìm kiếm ngữ nghĩa, Redis giữ memory và cache cho các bước hỗ trợ như hội thoại và helper calls, còn Neo4j được dùng khi bật GraphRAG để lưu quan hệ thực thể. Cách chia lớp theo trách nhiệm này giúp hệ thống vừa rõ ràng vừa dễ kiểm soát chi phí vận hành.

## Luồng xử lý tài liệu từ lúc upload tới lúc sẵn sàng truy vấn

Khi người dùng upload tài liệu từ Frontend, request đi vào endpoint upload của Backend. Ở đây backend kiểm tra MIME type, extension và giới hạn dung lượng tối đa 20MB trước khi cho đi tiếp. Ngay sau đó backend đọc bytes của file để tạo mã băm SHA256, vì hash này là chìa khóa cho cơ chế chống xử lý trùng.

Nếu backend tìm thấy một tài liệu đã xử lý xong trước đó của cùng người dùng có cùng content hash, backend sẽ tái sử dụng tài nguyên đã có bằng cách tạo một Document mới nhưng trỏ canonical_document_id về bản gốc và tái sử dụng file_path. Cách làm này cho phép bỏ qua OCR, chunking và embedding, tức là cắt mạnh phần tiêu tốn quota. Một điểm quan trọng trong code hiện tại là ảnh được xử lý theo hướng bảo toàn danh tính nguồn trích dẫn nên không đi theo nhánh dedup giống tài liệu text thông thường.

Nếu không có bản trùng, backend upload file lên MinIO. Object name được tổ chức theo cấu trúc user_id/uuid.ext, còn file_path lưu trong database theo dạng bucket/object_name để luôn truy vết lại được file vật lý. Sau khi upload xong, backend tạo bản ghi Document ở PostgreSQL với trạng thái pending, rồi gắn canonical_document_id bằng chính id của document mới.

Từ thời điểm đó, backend không bắt người dùng chờ toàn bộ pipeline AI hoàn tất. Thay vào đó, backend tạo background task để xử lý bất đồng bộ. Task này mở DB session riêng, kéo file gốc từ MinIO, rồi gửi multipart request sang AI Service tại endpoint xử lý tài liệu. Request này chứa file bytes, document_id, user_id và metadata nghiệp vụ như title, category, tags.

Khi AI Service xử lý xong, kết quả trả về gồm danh sách chunk đã chuẩn hóa cùng token_count và metadata từng chunk. Backend nhận danh sách này rồi ghi vào bảng document_chunks, đồng thời ghi bảng document_embeddings dưới dạng metadata trỏ tới qdrant_point_id. Cuối cùng backend cập nhật document thành completed và đánh dấu is_processed là true.

## File được lưu ở đâu và mỗi nơi giữ vai trò gì

Trong kiến trúc này, file gốc luôn nằm ở MinIO, vì đây là lớp lưu trữ object bền vững cho dữ liệu nhị phân. PostgreSQL không giữ file gốc mà chỉ giữ “hồ sơ quản trị” của tài liệu, bao gồm tên file, đường dẫn MinIO, hash nội dung, trạng thái xử lý, metadata nghiệp vụ, thông tin canonical và các bản ghi chunk liên quan.

Qdrant là nơi lưu vector thật sự để phục vụ truy vấn semantic search tốc độ cao. Trong mỗi point của Qdrant, hệ thống lưu vector cùng payload giàu ngữ cảnh như document_id, chunk_id, chunk_text, chunk_index, user_id, file_name, title, category, tags và cờ nhận diện OCR ảnh. Điều này giúp retrieval vừa tìm đúng theo ngữ nghĩa vừa giữ đủ thông tin để truy vết nguồn.

Khi bật GraphRAG, Neo4j giữ lớp tri thức dạng đồ thị, gồm Document, Chunk, Entity và các quan hệ liên kết. Redis giữ ngữ cảnh hội thoại đa phiên và cache cho các bước helper để giảm số lần gọi model ở những tác vụ lặp.

## AI Service đọc file và trích xuất nội dung theo từng định dạng

Điểm quan trọng của pipeline AI là không đọc file theo một cách duy nhất. Service sẽ nhận bytes từ backend, ghi tạm ra file temp để các loader làm việc, sau đó chọn chiến lược đọc dựa theo MIME type và extension.

Với PDF có text, hệ thống dùng PyPDFLoader để trích xuất nội dung. Nhưng nếu tổng text lấy được quá ít, nhỏ hơn ngưỡng khoảng 150 ký tự, pipeline coi đó là PDF scan hoặc PDF ảnh. Khi đó mỗi trang được render thành ảnh JPEG bằng PyMuPDF ở độ phân giải 200 DPI rồi gửi sang Gemini Vision để OCR theo từng trang. Kết quả OCR của mỗi trang được đóng thành document đầu vào cho các bước sau.

Với ảnh độc lập như JPG, PNG, WebP hoặc HEIC, hệ thống gửi trực tiếp bytes ảnh vào luồng Vision OCR. Prompt OCR được thiết kế theo hướng số hóa tài liệu đầy đủ, bao gồm text, bảng, ký hiệu và mô tả hình minh họa nếu có. Trong trường hợp OCR thất bại hoàn toàn, pipeline vẫn tạo một placeholder document để tránh vỡ luồng xử lý.

Với DOCX, hệ thống dùng Docx2txtLoader để lấy nội dung text. Với file mã nguồn, hệ thống đọc raw text rồi chọn text splitter theo ngôn ngữ lập trình tương ứng để hạn chế cắt ngang cấu trúc hàm hoặc class. Với CSV và XLSX, pipeline dùng pandas để đọc bảng rồi chuyển sang markdown table theo cụm dòng nhằm giữ ngữ nghĩa bảng dữ liệu. Với plain text hoặc định dạng còn lại, hệ thống đọc theo UTF-8 có cơ chế thay thế lỗi ký tự để không dừng pipeline.

Sau khi hoàn tất, file temp luôn được xóa để không tích lũy dữ liệu tạm trong container AI.

## Cơ chế chunking và chuẩn hóa nội dung trước khi embedding

Chunking được cấu hình bằng RecursiveCharacterTextSplitter với chunk_size là 1000 ký tự và chunk_overlap là 200 ký tự. Các document đã được cắt sẵn từ trước, như một số nhánh code hoặc bảng, sẽ được đánh dấu pre_chunked để không bị tách lại. Các document cần tách mới sẽ được split theo thứ tự separator ưu tiên ngắt đoạn và ngắt dòng trước khi rơi xuống mức ký tự.

Trước khi đưa đi embedding, từng chunk được chuẩn hóa lại thành định dạng có metadata header ngay trong nội dung, bao gồm filename, file_type và source. Nếu chunk đến từ OCR ảnh thì source được ghi theo hướng OCR/Vision, còn chunk đến từ file gốc thì source phản ánh luồng MinIO. Với chunk mã nguồn, phần body được đặt trong fenced code block đúng ngôn ngữ để bảo toàn ngữ cảnh khi retrieval và khi model đọc lại prompt.

Mỗi chunk khi đóng gói đều có chunk_index, chunk_text, chunk_metadata, document_id, user_id, file_name và token_count ước lượng theo quy tắc ký tự chia bốn. Cách lưu này làm cho luồng truy vết từ câu trả lời quay ngược về đoạn văn bản gốc luôn minh bạch.

## Embedding được tạo như thế nào và lưu vào đâu

Embedding service của AI dùng Cohere với model embed-multilingual-v3.0. Với dữ liệu tài liệu, hệ thống gọi input_type là search_document để sinh vector phù hợp ngữ cảnh index. Với câu hỏi người dùng, hệ thống dùng input_type là search_query để vector truy vấn đồng nhất với vector tài liệu trong không gian tìm kiếm. Kích thước vector được cấu hình 1024 chiều và được dùng thống nhất trong collection Qdrant.

Sau khi embedding được tạo, AI Service upsert toàn bộ points vào Qdrant. Mỗi point có id riêng, vector và payload chứa metadata retrieval. Backend đồng thời lưu metadata embedding vào PostgreSQL để phục vụ quản trị vòng đời dữ liệu, trong khi vector thật chỉ nằm ở Qdrant. Thiết kế này giữ cho lớp nghiệp vụ có thể audit được dữ liệu mà không phải lưu vector nặng trong database quan hệ.

## Phân luồng mô hình và cơ chế fallback trong AI Service

ModelManager là thành phần điều phối provider và model theo task_type và độ phức tạp. Với helper tasks như intent classification, query rewrite, rerank fallback hay corrective RAG, thứ tự ưu tiên thiên về tốc độ và chi phí thấp. Với các tác vụ trả lời RAG hoặc tóm tắt phức tạp, hệ thống ưu tiên model mạnh hơn trước rồi mới rơi về model rẻ hơn nếu cần. Với code_help hoặc data_analysis, route cũng thay đổi theo mức độ khó của câu hỏi.

Cơ chế chống gián đoạn được thiết kế hai lớp. Ở lớp thứ nhất, hệ thống theo dõi trạng thái rate-limit theo provider, nhận diện lỗi quota rồi tạm thời gắn cờ provider đó để tránh chọn lại ngay lập tức. Ở lớp thứ hai, nếu lần gọi hiện tại thất bại, hệ thống đi qua fallback chain sang provider kế tiếp. Riêng Gemini hỗ trợ nhiều API key theo cơ chế round-robin, đồng thời có theo dõi trạng thái giới hạn theo từng key để xoay vòng thông minh hơn. Riêng Groq có giới hạn max_tokens ở mức an toàn để giảm rủi ro chạm trần miễn phí.

Trong OCR đa phương thức, luồng Vision cũng thừa hưởng tinh thần fallback tương tự. Hệ thống thử lại nhiều lần với backoff và xoay key Gemini khi gặp tín hiệu quota, nhờ đó giảm xác suất thất bại cứng ở các tác vụ scan tài liệu nhiều trang.

## Cấu trúc RAG thực tế đang chạy trong luồng chat

Luồng hỏi đáp chính hiện tại đi theo endpoint chat của backend. Frontend gửi câu hỏi vào phiên chat, backend lưu message người dùng, gom chat_history gần nhất, chuẩn hóa document_ids về canonical_document_id rồi gọi AI Service tại endpoint multi-agent. Đây là điểm rất quan trọng vì nó đảm bảo một tài liệu trùng nội dung vẫn truy vấn đúng bộ vector chuẩn đã index từ trước.

Trong AI Service, Master Orchestrator điều phối chuỗi xử lý. Nếu request chưa mang đủ lịch sử hội thoại, orchestrator tự nạp thêm từ Redis memory để không mất ngữ cảnh. Sau đó Prompt Preprocessor xử lý những câu mơ hồ kiểu xác nhận ngắn hoặc tham chiếu ngữ cảnh. Intent classifier chạy theo mô hình lai rule trước, LLM sau, có cache để giảm helper token. Nếu người dùng có tài liệu đính kèm và câu hỏi mang tính chỉ định như “file này” hoặc “hình này”, orchestrator có logic ép route sang nhánh tài liệu để tránh trả lời trôi sang kiến thức chung.

Khi intent đi vào Document QA Agent, nhánh summarization và nhánh QA thường được tách rõ. Ở nhánh summarization, hệ thống không chỉ lấy top-k mà scroll toàn bộ chunk của các document được chọn, rồi chạy map-reduce. Map phase tóm tắt riêng từng tài liệu, reduce phase tổng hợp toàn cảnh. Nếu chất lượng summary có dấu hiệu quá ngắn hoặc cụt ý, quality guard sẽ kích hoạt retry với prompt chặt hơn hoặc provider khác.

Ở nhánh QA thông thường, hệ thống phân tích độ phức tạp câu hỏi trước khi retrieval. Nếu Advanced RAG đang bật, pipeline sẽ đi qua query rewriting để tạo biến thể, có thể thêm step-back query và thậm chí decomposition cho multi-hop. Sau đó hệ thống chạy multi-query vector retrieval, hợp nhất kết quả, áp dụng BM25 rescoring để tăng trọng số từ khóa, rồi rerank lại bằng Cohere rerank hoặc fallback bằng LLM. Tiếp theo CRAG đánh giá độ đủ của context. Nếu chất lượng bị đánh giá là insufficient, pipeline sinh corrective query và thử truy xuất lại với ngưỡng linh hoạt hơn.

Nếu Advanced RAG không khả dụng nhưng GraphRAG được bật, hệ thống dùng Hybrid RAG để phối hợp context vector từ Qdrant và context quan hệ từ Neo4j. Nếu cả hai lớp nâng cao không dùng được, pipeline rơi xuống vector-only retrieval trong Qdrant với filter user_id và document_ids. Khi semantic search không tìm thấy gì mà câu hỏi mang tính tham chiếu file đính kèm, hệ thống còn có reference fallback bằng cơ chế scroll để kéo các chunk đầu theo tài liệu, tránh trường hợp query ngắn chung chung nhưng người dùng thực sự đang hỏi nội dung trong file vừa chọn.

Sau khi có context, agent xây prompt theo hướng grounding chặt, gắn thêm phần lịch sử hội thoại gần và chọn model theo độ phức tạp. Câu trả lời trả về kèm metadata như retrieval_mode, pipeline stages, số context đã dùng và doc_map để frontend liên kết nguồn trích dẫn đúng tài liệu.

## Kết luận vận hành

Nhìn tổng thể, hệ thống này không phải mô hình “một API gọi một model rồi trả lời”, mà là chuỗi phối hợp nhiều lớp có kiểm soát trách nhiệm rõ ràng. Frontend tập trung trải nghiệm và luồng tương tác, Backend tập trung quản trị nghiệp vụ và vòng đời dữ liệu, còn AI Service tập trung trí tuệ xử lý tài liệu và suy luận. Ở chiều ingest, file gốc nằm ở MinIO, metadata nằm ở PostgreSQL, vector nằm ở Qdrant và quan hệ tri thức có thể mở rộng bằng Neo4j. Ở chiều truy vấn, multi-agent orchestration, model routing, advanced retrieval và fallback giúp hệ thống giữ được cân bằng giữa độ đúng tài liệu, độ ổn định và chi phí. Chính sự phân lớp này làm cho nền tảng vừa đủ linh hoạt để mở rộng, vừa đủ minh bạch để theo dõi và tối ưu vận hành theo thời gian.
