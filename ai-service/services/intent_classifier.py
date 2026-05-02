"""
Intent Classifier - Route queries to appropriate handlers
Classifies user intent to determine processing strategy using LLM-first approach.
"""
from typing import Dict, List, Optional, Any
from core.model_manager import model_manager
from core.llm_cache import llm_cache


class IntentClassifier:
    """
    Classify user intent to route to appropriate handler
    """
    
    # Intent definitions with keywords and characteristics
    INTENTS = {
        "qa": {
            "description": "Hỏi kiến thức, giải thích khái niệm, tóm tắt, hỏi nội dung tài liệu/ảnh, sinh code",
            "examples": [
                "OOP là gì?",
                "Tóm tắt tài liệu này",
                "Theo file, CICD là gì?",
                "Viết code Python sắp xếp mảng"
            ]
        },
        "computation": {
            "description": "Bài toán tính toán ra kết quả số, giải bài tập, công thức",
            "examples": [
                "Tính trung bình mẫu cần thiết với sai số 1 giây",
                "Giải bài 5.12 trong hình",
                "Tính xác suất và đưa kết quả số"
            ]
        },
        "analysis": {
            "description": "Phân tích, thống kê, so sánh số liệu; phân tích dữ liệu CSV/Excel",
            "examples": [
                "Phân tích doanh thu theo tháng",
                "Thống kê tỷ lệ theo nhóm",
                "So sánh xu hướng giữa 2 tập dữ liệu"
            ]
        }
    }
    
    def classify(
        self,
        question: str,
        has_documents: bool = False,
        document_count: int = 0,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        source_metadata: Optional[List[Dict[str, Any]]] = None,
        has_tabular_data: bool = False,
    ) -> str:
        """
        Classify user intent using LLM-first approach with context.
        Rule-based fallback is used only when LLM fails.
        """
        question_text = (question or "").strip()

        print(f"\n🎯 ========== INTENT CLASSIFICATION ==========")
        print(f"   Question: '{question_text}'")
        print(f"   Has documents: {has_documents}, Count: {document_count}")

        if not question_text:
            print("⚠️ Empty question - defaulting to direct_chat")
            print(f"================================================\n")
            return "direct_chat"

        print("⚡ Using LLM classification with context...")
        llm_intent = self._classify_with_llm(
            question=question_text,
            has_documents=has_documents,
            document_count=document_count,
            chat_history=chat_history,
            source_metadata=source_metadata,
            has_tabular_data=has_tabular_data,
        )
        print(f"✅ Intent: {llm_intent.upper()} (LLM-first)")
        print(f"================================================\n")
        return llm_intent
    
    def _classify_with_llm(
        self,
        question: str,
        has_documents: bool,
        document_count: int,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        source_metadata: Optional[List[Dict[str, Any]]] = None,
        has_tabular_data: bool = False,
    ) -> str:
        """
        Use LLM (Gemini Flash) to classify intent for ambiguous cases
        
        Returns:
            Intent name
        """
        # Build prompt with context
        if has_documents and document_count > 0:
            doc_context = f"Người dùng ĐÃ upload {document_count} tài liệu."
        else:
            doc_context = "Người dùng CHƯA upload tài liệu nào."

        has_image_source = self._has_image_source_metadata(source_metadata)
        history_hint = self._build_history_hint(chat_history)
        source_hint = self._build_source_hint(source_metadata, has_image_source)

        system_prompt = f"""Bạn là Intent Classifier thông minh. Phân loại câu hỏi vào ĐÚNG 1 intent.

NGỮ CẢNH HIỆN TẠI:
- {doc_context}
- {source_hint}
- Có file dữ liệu dạng bảng (CSV/XLSX): {has_tabular_data}
- Lịch sử gần đây (tóm tắt ngắn): {history_hint}

YÊU CẦU:
- Ưu tiên hiểu ý nghĩa câu hỏi dựa trên ngữ cảnh, KHÔNG dựa vào từ khóa đơn lẻ.
- Nếu có tham chiếu như "này", "đó", "trong hình", hãy dùng lịch sử/ngữ cảnh để hiểu đúng đối tượng.
- Chỉ được chọn 1 trong: qa / computation / analysis.

⚠️ QUY TẮC CHỐNG NHẦM (RẤT QUAN TRỌNG):
- Nếu có nguồn là HÌNH ẢNH hoặc câu hỏi nói "trong hình/ảnh", hầu hết trường hợp là hỏi mô tả/nhận diện nội dung → ưu tiên **qa**.
- Không được chọn **analysis** chỉ vì xuất hiện từ như "hàng", "cột", "bảng" nếu KHÔNG có file dữ liệu bảng.
- **analysis KHÔNG chỉ dành cho CSV/XLSX**. Có 2 nhóm use-case hợp lệ:
  (A) **Data analysis (tabular)**: Có file CSV/XLSX và yêu cầu thống kê/nhóm/pivot/biểu đồ, kết quả định lượng.
  (B) **Document analysis (report/code/pdf/docx)**: Có tài liệu/ảnh OCR và yêu cầu phân tích/tổng hợp/so sánh/kết luận từ nội dung tài liệu (không nhất thiết có bảng).
- Chỉ chọn **analysis** khi yêu cầu thật sự là “phân tích/tổng hợp/so sánh/kết luận” (không phải hỏi định nghĩa đơn giản hay nhận diện vật thể).
- Nếu người dùng chỉ xin **công thức/định nghĩa/quy tắc** (vd: "công thức tính tỉ số phần trăm", "công thức đạo hàm", "quy tắc Bayes là gì")
  mà KHÔNG đưa số liệu cụ thể và KHÔNG yêu cầu ra kết quả số → ưu tiên **qa** (không phải computation).
- Nếu câu hỏi vừa có tài liệu/ảnh đính kèm vừa có từ khóa "hàng/cột", nhưng mục tiêu là nhận diện/mô tả nội dung trong tài liệu/ảnh → vẫn là **qa**.

📋 CÁC INTENT:

1. **qa** - Hỏi kiến thức, giải thích, tóm tắt, hỏi nội dung tài liệu/ảnh, sinh code
    - Ví dụ: "OOP là gì?", "Tóm tắt file này", "Theo tài liệu, CICD là gì?", "Viết code Python"
    - Dấu hiệu: hỏi khái niệm, giải thích, tóm tắt, hoặc hỏi nội dung trong tài liệu/ảnh

2. **computation** - Yêu cầu tính toán ra kết quả số, giải bài tập có công thức
    - Ví dụ: "Tính sai số mẫu", "Giải bài 5.12", "Tính xác suất/diện tích"
    - Dấu hiệu: cần ra con số cuối cùng, có biến số/công thức/phép tính

3. **analysis** - Phân tích/tổng hợp/so sánh/kết luận từ tài liệu hoặc dữ liệu (CSV/Excel hoặc report/pdf/docx/code)
    - Ví dụ: "Phân tích doanh thu theo tháng", "Thống kê tỷ lệ", "So sánh xu hướng"
    - Dấu hiệu: cần phân tích dữ liệu/đồ thị, thống kê mô tả, xu hướng

🎯 LOGIC QUYẾT ĐỊNH:

**Bước 1**: Nếu câu hỏi yêu cầu ra kết quả số cụ thể → computation
**Bước 2**: Nếu câu hỏi là phân tích/tổng hợp/so sánh/kết luận từ (a) file CSV/XLSX hoặc (b) nội dung tài liệu/report/code/pdf/docx → analysis
**Bước 3**: Còn lại → qa

YÊU CẦU:
- Trả lời CHỈ TÊN INTENT (qa/computation/analysis)
- KHÔNG giải thích, KHÔNG thêm text khác"""

        user_prompt = f"""Câu hỏi: "{question}"

Intent:"""

        cache_key = llm_cache.build_key(
            "intent_classifier_v2",
            {
                "question": question.strip().lower(),
                "has_documents": has_documents,
                "document_count": int(document_count),
                "history_tail": self._build_history_cache_key(chat_history),
                "has_image_source": has_image_source,
                "has_tabular_data": bool(has_tabular_data),
            },
        )
        cached_intent = llm_cache.get(cache_key)
        if isinstance(cached_intent, str) and cached_intent:
            return cached_intent

        try:
            # Use Gemini Flash for fast classification
            provider, model = model_manager.get_model("intent_classification", "low")
            
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.0,  # Deterministic
                max_tokens=20
            )
            
            intent = response.strip().lower()
            
            # Validate intent
            valid_intents = ["qa", "computation", "analysis"]
            
            if intent in valid_intents:
                llm_cache.set(cache_key, intent)
                return intent
            else:
                # Fallback: extract intent if LLM returns with explanation
                for valid_intent in valid_intents:
                    if valid_intent in intent:
                        llm_cache.set(cache_key, valid_intent)
                        return valid_intent
                
                # Last resort: default to qa
                print(f"⚠️ LLM returned invalid intent '{intent}', defaulting to qa")
                return "qa"
        
        except Exception as e:
            print(f"❌ LLM classification error: {e}")
            # Fallback to minimal rule-based
            return self._classify_fallback(question, has_documents, document_count)

    def _build_history_hint(
        self,
        chat_history: Optional[List[Dict[str, Any]]],
        max_messages: int = 6,
        max_chars: int = 800
    ) -> str:
        if not chat_history:
            return "Không có"

        recent = chat_history[-max_messages:]
        parts = []
        for msg in recent:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = (msg.get("content") or "").strip()
            if len(content) > 240:
                content = content[:240] + "..."
            parts.append(f"{role}: {content}")

        text = " | ".join(parts)
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        return text

    def _build_history_cache_key(
        self,
        chat_history: Optional[List[Dict[str, Any]]]
    ) -> str:
        if not chat_history:
            return ""
        recent = chat_history[-4:]
        parts = []
        for msg in recent:
            role = msg.get("role") or ""
            content = (msg.get("content") or "").strip()
            if len(content) > 120:
                content = content[:120]
            parts.append(f"{role}:{content}")
        return " | ".join(parts)

    def _has_image_source_metadata(
        self,
        source_metadata: Optional[List[Dict[str, Any]]]
    ) -> bool:
        if not source_metadata:
            return False
        image_exts = (".png", ".jpg", ".jpeg", ".webp", ".heic")
        for source in source_metadata:
            mime_type = (source.get("mime_type") or "").lower()
            file_name = (source.get("file_name") or "").lower()
            if mime_type.startswith("image/") or file_name.endswith(image_exts):
                return True
        return False

    def _build_source_hint(
        self,
        source_metadata: Optional[List[Dict[str, Any]]],
        has_image_source: bool
    ) -> str:
        if not source_metadata:
            return "Không có nguồn đính kèm"
        file_names = []
        for source in source_metadata[:3]:
            name = source.get("file_name") or source.get("source_id") or "unknown"
            file_names.append(name)
        file_list = ", ".join(file_names) if file_names else "không rõ"
        return f"Có {len(source_metadata)} nguồn | hình ảnh={has_image_source} | ví dụ: {file_list}"
    
    def _classify_fallback(
        self,
        question: str,
        has_documents: bool,
        document_count: int
    ) -> str:
        """
        Fallback classification when LLM fails
        Simple rule-based logic
        """
        question_lower = question.lower()
        
        # Minimal fallback: avoid heavy keyword routing
        if any(token in question_lower for token in ["phân tích", "thống kê", "analysis", "statistics"]):
            return "analysis"
        if any(token in question_lower for token in ["tính", "calculate", "giải", "phương trình"]):
            return "computation"
        return "qa"
    
    def _has_keywords(self, text: str, keywords: List[str]) -> bool:
        """Check if text contains any of the keywords"""
        return any(keyword in text for keyword in keywords)
    
    def _is_factual_question(self, text: str) -> bool:
        """Check if question is asking for facts"""
        factual_patterns = [
            "là gì", "what is", "define",
            "nghĩa là", "meaning",
            "khác nhau", "difference", "so sánh", "compare",
            "là", "means", "refers to"
        ]
        return self._has_keywords(text, factual_patterns)
    
    def _is_math_or_homework(self, text: str) -> bool:
        """
        Check if question is math or homework related
        Returns True for questions that should NOT use RAG even if docs exist
        """
        math_homework_keywords = [
            # Math keywords
            "giải", "tính", "phương trình", "solve", "calculate",
            "đạo hàm", "tích phân", "derivative", "integral",
            "x =", "y =", "f(x)", "=" , "bằng bao nhiêu",
            "cộng", "trừ", "nhân", "chia", "+", "-", "*", "/",
            
            # Homework/exercise keywords
            "bài toán", "bài tập", "problem", "exercise",
            "homework", "giúp tôi", "hướng dẫn",
            
            # General knowledge
            "thế giới", "lịch sử", "địa lý", "world", "history",
            "who is", "when did", "where is", "how many",
            
            # Code
            "code", "viết code", "function", "class", "debug",
            "python", "java", "javascript", "program"
        ]
        return self._has_keywords(text, math_homework_keywords)
    
    def _is_likely_document_query(self, text: str) -> bool:
        """
        Check if question is likely related to uploaded documents
        Returns False for math, code, general knowledge questions
        """
        # Exclude math/homework indicators
        math_keywords = [
            "giải", "tính", "phương trình", "solve", "calculate",
            "x =", "y =", "f(x)", "=", "+", "-", "*", "/",
            "bài toán", "bài tập", "problem", "exercise"
        ]
        if self._has_keywords(text, math_keywords):
            return False
        
        # Exclude code indicators (already handled by code_help intent)
        code_keywords = [
            "code", "viết code", "function", "class", "debug",
            "python", "java", "javascript", "program"
        ]
        if self._has_keywords(text, code_keywords):
            return False
        
        # Exclude pure general knowledge questions
        general_keywords = [
            "thế giới", "lịch sử", "địa lý", "world", "history",
            "who is", "when did", "where is"
        ]
        if self._has_keywords(text, general_keywords):
            return False
        
        # If none of above exclusions, likely document-related
        return True
    
    def is_complex_query(self, question: str) -> bool:
        """
        Determine if query is complex (needs Pro model vs Flash)
        
        Complex indicators:
        - Long questions (>100 chars)
        - Multiple sub-questions
        - Requires analysis/comparison/synthesis
        - Creative tasks
        """
        question_lower = question.lower()
        
        # Length check
        if len(question) > 100:
            return True
        
        # Complexity keywords
        complex_keywords = [
            "phân tích", "analyze", "analysis",
            "so sánh", "compare", "comparison",
            "tổng hợp", "synthesize", "synthesis",
            "đánh giá", "evaluate", "evaluation",
            "giải thích chi tiết", "explain in detail",
            "tại sao", "why", "how does",
            "mối quan hệ", "relationship between"
        ]
        
        if self._has_keywords(question_lower, complex_keywords):
            return True
        
        # Multiple questions indicator
        if question.count("?") > 1:
            return True
        
        # Default: simple
        return False
    
    def get_intent_info(self, intent: str) -> Dict:
        """Get information about an intent"""
        return self.INTENTS.get(intent, {
            "description": "Unknown intent",
            "requires_documents": False
        })


# Global singleton instance
intent_classifier = IntentClassifier()
