"""
Intent Classifier - Route queries to appropriate handlers
Classifies user intent to determine processing strategy using HYBRID approach:
- Rule-based for obvious cases (fast)
- LLM-based for ambiguous cases (accurate)
"""
from typing import Dict, List, Optional
from core.model_manager import model_manager


class IntentClassifier:
    """
    Classify user intent to route to appropriate handler
    """
    
    # Intent definitions with keywords and characteristics
    INTENTS = {
        "direct_chat": {
            "keywords": [
                "giải", "tính", "viết code", "debug", "lỗi", "sửa",
                "giải thích", "là gì", "tại sao", "làm thế nào",
                "ví dụ", "so với", "chương trình"
            ],
            "requires_documents": False,
            "description": "General questions, homework, coding - no documents needed",
            "examples": [
                "Giải phương trình: x^2 + 2x + 1 = 0",
                "Viết code Python để sắp xếp mảng",
                "Giải thích khái niệm recursion",
                "Tại sao Python lại phổ biến?"
            ]
        },
        
        "rag_query": {
            "keywords": [
                # Explicit keywords
                "theo tài liệu", "trong file", "trong tài liệu",
                "dựa vào", "dựa theo", "file nói gì",
                "tài liệu có", "trong bài", "theo bài",
                # Implicit document references (MORE INTELLIGENT)
                "file này", "tài liệu này", "file đó", "tài liệu đó",
                "file vừa", "tài liệu vừa", "file mới", "tài liệu mới",
                "file upload", "file tải", "file đã upload", "file đã tải",
                "tóm tắt file", "file nói về", "nội dung file",
                "tóm tắt tài liệu", "tài liệu nói về", "nội dung tài liệu",
                # Data/document keywords
                "file dữ liệu", "tài liệu dữ liệu", "dữ liệu trong file",
                "document", "uploaded file", "my file", "my document"
            ],
            "requires_documents": True,
            "description": "Fact-finding from uploaded documents",
            "examples": [
                "CICD là gì theo tài liệu?",
                "Trong file vừa upload có nói gì về Docker?",
                "Dựa vào tài liệu, RAG hoạt động như thế nào?",
                "Tóm tắt file dữ liệu này",  # NEW
                "File này nói về gì?",  # NEW
                "File dữ liệu có thông tin về gì?"  # NEW
            ]
        },
        
        "data_analysis": {
            "keywords": [
                "phân tích", "analyze", "analysis", "thống kê", "statistics",
                "tính toán", "compute", "doanh thu", "revenue",
                "theo tháng", "monthly", "theo năm", "yearly",
                "trung bình", "average", "tổng", "sum",
                "biểu đồ", "chart", "graph", "plot",
                "csv", "excel", "dữ liệu", "data"
            ],
            "requires_documents": False,  # Uses data files, not text documents
            "requires_file": True,
            "description": "Data analysis with CSV/Excel using pandas",
            "examples": [
                "Phân tích doanh thu theo tháng",
                "Tính trung bình của cột revenue",
                "Tạo biểu đồ từ dữ liệu sales",
                "Thống kê số lượng theo danh mục"
            ]
        },
        
        "summarization": {
            "keywords": [
                "tóm tắt", "summarize", "tổng hợp", "tổng kết",
                "summary", "overview", "nội dung chính",
                "điểm chính", "key points",
                # More variations for summarization
                "tóm lại", "tóm gọn", "nói về gì", "bài này về",
                "chủ đề", "topic", "subject", "about what"
            ],
            "requires_full_document": True,
            "description": "Summarize entire document",
            "examples": [
                "Tóm tắt tài liệu này",
                "Nội dung chính của file là gì?",
                "Tổng hợp các điểm quan trọng",
                "File nói về gì?",  # NEW
                "Tóm tắt file dữ liệu"  # NEW
            ]
        },
        
        "question_generation": {
            "keywords": [
                "tạo câu hỏi", "đưa ra câu hỏi", "gợi ý câu hỏi",
                "câu hỏi khác", "câu hỏi thêm", "câu hỏi tương tự",
                "generate questions", "suggest questions",
                "questions about", "quiz", "practice questions"
            ],
            "creative_mode": True,
            "requires_documents": True,
            "description": "Generate new questions from document content",
            "examples": [
                "Tạo 10 câu hỏi từ tài liệu này",
                "Đưa ra câu hỏi để ôn tập",
                "Gợi ý câu hỏi về chủ đề Docker"
            ]
        },
        
        "homework_solver": {
            "keywords": [
                "giải bài", "giải bài tập", "homework",
                "bài tập", "exercise", "problem",
                "làm giúp", "hướng dẫn giải"
            ],
            "reasoning_required": True,
            "requires_documents": False,
            "description": "Step-by-step homework/problem solving",
            "examples": [
                "Giúp tôi giải bài toán này",
                "Hướng dẫn làm bài tập Python",
                "Giải bài tập về linked list"
            ]
        },
        
        "code_help": {
            "keywords": [
                "code", "viết code", "lập trình", "program",
                "implement", "function", "class", "debug"
            ],
            "reasoning_required": True,
            "requires_documents": False,
            "description": "Code writing, debugging, implementation",
            "examples": [
                "Viết hàm tìm số nguyên tố",
                "Code này bị lỗi gì?",
                "Implement binary search"
            ]
        }
    }
    
    def classify(
        self,
        question: str,
        has_documents: bool = False,
        document_count: int = 0
    ) -> str:
        """
        Classify user intent using HYBRID approach:
        1. Rule-based for obvious cases (fast)
        2. LLM-based for ambiguous cases (accurate)
        
        Args:
            question: User's question
            has_documents: Whether user has uploaded documents
            document_count: Number of documents in context
        
        Returns:
            Intent name (str)
        """
        question_lower = question.lower()
        
        print(f"\n🎯 ========== INTENT CLASSIFICATION ==========")
        print(f"   Question: '{question}'")
        print(f"   Has documents: {has_documents}, Count: {document_count}")
        
        # ========================================
        # PHASE 1: RULE-BASED (Obvious Cases)
        # ========================================
        
        # 1. Code Help (very obvious - contains code keywords)
        code_indicators = ["code", "python", "java", "javascript", "function", "class", "def ", "import ", "debug", "lỗi code"]
        if any(indicator in question_lower for indicator in code_indicators):
            print(f"✅ Intent: CODE_HELP (rule-based: code keywords)")
            print(f"================================================\n")
            return "code_help"
        
        # 2. Data Analysis (very obvious - data/analysis keywords)
        data_indicators = ["phân tích dữ liệu", "analyze data", "csv", "excel", "doanh thu", "biểu đồ", "thống kê"]
        if any(indicator in question_lower for indicator in data_indicators):
            print(f"✅ Intent: DATA_ANALYSIS (rule-based: data keywords)")
            print(f"================================================\n")
            return "data_analysis"
        
        # 3. Explicit Document Reference WITH documents (obvious RAG)
        explicit_doc_refs = ["theo tài liệu", "trong file", "file vừa upload", "file này nói", "trong tài liệu"]
        if any(ref in question_lower for ref in explicit_doc_refs):
            if has_documents and document_count > 0:
                print(f"✅ Intent: RAG_QUERY (rule-based: explicit doc ref + has docs)")
                print(f"================================================\n")
                return "rag_query"
        
        # 4. Math Calculation (obvious - contains calculation)
        if any(op in question for op in ["+", "-", "*", "/", "×"]) and any(c.isdigit() for c in question):
            print(f"✅ Intent: HOMEWORK_SOLVER (rule-based: math operators)")
            print(f"================================================\n")
            return "homework_solver"
        
        # ========================================
        # PHASE 2: LLM-BASED (Ambiguous Cases)
        # ========================================
        
        print(f"⚡ Not obvious - using LLM classification...")
        llm_intent = self._classify_with_llm(question, has_documents, document_count)
        print(f"✅ Intent: {llm_intent.upper()} (LLM-based)")
        print(f"================================================\n")
        return llm_intent
    
    def _classify_with_llm(
        self,
        question: str,
        has_documents: bool,
        document_count: int
    ) -> str:
        """
        Use LLM (Gemini Flash) to classify intent for ambiguous cases
        
        Returns:
            Intent name
        """
        # Build prompt with context
        doc_context = ""
        if has_documents and document_count > 0:
            doc_context = f"\n**QUAN TRỌNG**: Người dùng ĐÃ UPLOAD {document_count} tài liệu."
        else:
            doc_context = "\n**QUAN TRỌNG**: Người dùng CHƯA UPLOAD tài liệu nào."
        
        system_prompt = f"""Bạn là Intent Classifier thông minh. Phân loại câu hỏi vào ĐÚNG 1 intent.

{doc_context}

📋 CÁC INTENT:

1. **homework_solver** - Giải toán, bài tập, phương trình
   - Ví dụ: "Giải phương trình x² + 2x = 0", "đạo hàm của 3x", "tích phân của x²"
   - Dấu hiệu: Có công thức toán, biến số (x, y), phép tính, đạo hàm, tích phân
   - ✅ Luôn dùng cho câu hỏi TOÁN, KHÔNG dùng RAG kể cả khi có tài liệu

2. **code_help** - Lập trình, viết code, debug
   - Ví dụ: "Viết code Python sắp xếp", "Debug lỗi này", "Tạo function tính tổng"
   - Dấu hiệu: Có từ "code", "function", "class", "debug", tên ngôn ngữ
   - ✅ Luôn dùng cho câu hỏi LẬP TRÌNH

3. **direct_chat** - Kiến thức chung, giải thích khái niệm, trò chuyện
   - Ví dụ: "OOP là gì?", "Sắp xếp nổi bọt hoạt động thế nào?", "Giải thích AI"
   - Dấu hiệu: Hỏi "là gì", "làm thế nào", kiến thức tổng quát
   - ✅ Dùng pre-trained knowledge, KHÔNG dùng RAG

4. **rag_query** - Hỏi VỀ tài liệu đã upload (CHỈ KHI có tài liệu)
   - Ví dụ: "Theo tài liệu, CICD là gì?", "File nói gì về Docker?", "Trong tài liệu có thông tin về RAG?"
   - Dấu hiệu: 
     * Có cụm "theo tài liệu", "trong file", "file này", "tài liệu nói"
     * HOẶC hỏi thông tin CỤ THỂ có trong tài liệu đã upload
   - ⚠️ CHỈ dùng nếu người dùng ĐÃ UPLOAD tài liệu

5. **summarization** - Tóm tắt tài liệu
   - Ví dụ: "Tóm tắt file này", "File nói về gì?", "Tổng hợp nội dung chính"
   - Dấu hiệu: Có "tóm tắt", "nói về gì", "nội dung chính"
   - ⚠️ CHỈ dùng nếu người dùng ĐÃ UPLOAD tài liệu

6. **data_analysis** - Phân tích dữ liệu CSV/Excel
   - Ví dụ: "Phân tích doanh thu", "Tính trung bình cột A", "Tạo biểu đồ"
   - Dấu hiệu: "phân tích", "thống kê", "biểu đồ", "csv", "excel"

🎯 LOGIC QUYẾT ĐỊNH:

**Bước 1**: Kiểm tra LOẠI câu hỏi
- Toán học? → homework_solver
- Lập trình? → code_help  
- Kiến thức chung? → direct_chat

**Bước 2**: Nếu CÓ tài liệu, kiểm tra có MUỐN dùng tài liệu?
- "tài liệu này", "file này", "theo file" → rag_query hoặc summarization
- Câu hỏi chung (OOP là gì, đạo hàm?) → direct_chat (KHÔNG dùng RAG)

**Bước 3**: Nếu KHÔNG có tài liệu
- "tài liệu này nói về gì?" → direct_chat (vì không có tài liệu để hỏi)

YÊU CẦU:
- Trả lời CHỈ TÊN INTENT (homework_solver/code_help/direct_chat/rag_query/summarization/data_analysis)
- KHÔNG giải thích, KHÔNG thêm text khác
- Ưu tiên: homework_solver > code_help > direct_chat > rag_query"""

        user_prompt = f"""Câu hỏi: "{question}"

Intent:"""

        try:
            # Use Gemini Flash for fast classification
            provider, model = model_manager.get_model("direct_chat", "low")
            
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
            valid_intents = ["homework_solver", "code_help", "direct_chat", "rag_query", "summarization", "data_analysis", "question_generation"]
            
            if intent in valid_intents:
                return intent
            else:
                # Fallback: extract intent if LLM returns with explanation
                for valid_intent in valid_intents:
                    if valid_intent in intent:
                        return valid_intent
                
                # Last resort: default to direct_chat
                print(f"⚠️ LLM returned invalid intent '{intent}', defaulting to direct_chat")
                return "direct_chat"
        
        except Exception as e:
            print(f"❌ LLM classification error: {e}")
            # Fallback to rule-based
            return self._classify_fallback(question, has_documents, document_count)
    
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
        
        # Check for obvious patterns
        if any(kw in question_lower for kw in ["giải", "tính", "phương trình", "x =", "đạo hàm", "tích phân"]):
            return "homework_solver"
        
        if any(kw in question_lower for kw in ["code", "function", "class", "debug"]):
            return "code_help"
        
        if has_documents and any(kw in question_lower for kw in ["theo tài liệu", "trong file", "file này"]):
            if any(kw in question_lower for kw in ["tóm tắt", "nói về gì"]):
                return "summarization"
            return "rag_query"
        
        # Default
        return "direct_chat"
    
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
