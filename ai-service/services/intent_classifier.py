"""
Intent Classifier - Route queries to appropriate handlers
Classifies user intent to determine processing strategy
"""
from typing import Dict, List, Optional


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
                "theo tài liệu", "trong file", "trong tài liệu",
                "dựa vào", "dựa theo", "file nói gì",
                "tài liệu có", "trong bài", "theo bài"
            ],
            "requires_documents": True,
            "description": "Fact-finding from uploaded documents",
            "examples": [
                "CICD là gì theo tài liệu?",
                "Trong file vừa upload có nói gì về Docker?",
                "Dựa vào tài liệu, RAG hoạt động như thế nào?"
            ]
        },
        
        "summarization": {
            "keywords": [
                "tóm tắt", "summarize", "tổng hợp", "tổng kết",
                "summary", "overview", "nội dung chính",
                "điểm chính", "key points"
            ],
            "requires_full_document": True,
            "description": "Summarize entire document",
            "examples": [
                "Tóm tắt tài liệu này",
                "Nội dung chính của file là gì?",
                "Tổng hợp các điểm quan trọng"
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
        Classify user intent based on question and context
        
        Args:
            question: User's question
            has_documents: Whether user has uploaded documents
            document_count: Number of documents in context
        
        Returns:
            Intent name (str)
        """
        question_lower = question.lower()
        
        # 1. Check for EXPLICIT intent keywords (high priority)
        
        # Summarization (very specific)
        if self._has_keywords(question_lower, self.INTENTS["summarization"]["keywords"]):
            if has_documents:
                return "summarization"
        
        # Question Generation (very specific)
        if self._has_keywords(question_lower, self.INTENTS["question_generation"]["keywords"]):
            if has_documents:
                return "question_generation"
            else:
                # Without documents, generate general questions
                return "direct_chat"
        
        # RAG Query (explicit document reference)
        if self._has_keywords(question_lower, self.INTENTS["rag_query"]["keywords"]):
            return "rag_query"
        
        # Homework Solver
        if self._has_keywords(question_lower, self.INTENTS["homework_solver"]["keywords"]):
            return "homework_solver"
        
        # Code Help
        if self._has_keywords(question_lower, self.INTENTS["code_help"]["keywords"]):
            return "code_help"
        
        # 2. Context-based classification
        
        # If user has documents and question is factual -> RAG
        if has_documents and self._is_factual_question(question_lower):
            return "rag_query"
        
        # 3. Default intent
        
        # If has documents but no explicit RAG keywords -> still try RAG
        if has_documents and document_count > 0:
            return "rag_query"
        
        # Default: direct chat (no RAG needed)
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
