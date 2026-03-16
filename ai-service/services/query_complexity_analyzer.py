"""
Query Complexity Analyzer
Phân tích độ phức tạp của câu hỏi để điều chỉnh format response
"""
import re
from typing import Literal, Dict, Any
import logging

logger = logging.getLogger(__name__)


class QueryComplexityAnalyzer:
    """
    Phân tích độ phức tạp của câu hỏi
    - simple: Câu hỏi đơn giản, cần trả lời ngắn gọn
    - moderate: Câu hỏi trung bình, cần giải thích vừa phải
    - complex: Câu hỏi phức tạp, cần phân tích sâu
    """
    
    def __init__(self):
        # Patterns cho câu hỏi simple
        self.simple_patterns = [
            # Math Direct Calculation (đạo hàm/tích phân của biểu thức cụ thể)
            r'(đạo hàm|derivative|tính đạo hàm)\s+(của\s+)?[\w\d\+\-\*\/\^\(\)]+\s*(bằng|là)',
            r'(tích phân|integral|tính tích phân)\s+(của\s+)?[\w\d\+\-\*\/\^\(\)]+',
            r'(giới hạn|limit)\s+(của\s+)?[\w\d\+\-\*\/\^\(\)]+',
            
            # Phép tính đơn giản
            r'\d+\s*[\+\-\*\/xX×]\s*\d+',  # "1+1", "100+50", "5 x 3"
            r'\d+\s*(cộng|trừ|nhân|chia|tổng|hiệu|tích)\s*\d+',
            
            # Yes/No questions
            r'^(có|không|có phải|đúng không|sai không)',
            r'(phải không|đúng không|có không)\s*\??\s*$',
            
            # Hỏi thông tin cực ngắn (1 từ)
            r'^(tên|viết tắt|ký hiệu)\s+\w+',
            r'^(thủ đô|đất nước|quốc gia|tỉnh|thành phố)\s+của\s+\w+',
            
            # Chỉ 1 từ
            r'^\w{1,15}\s*\??\s*$',  # "Python?", "AI?"
        ]
        
        # Patterns cho definition questions (luôn cần giải thích đầy đủ)
        self.definition_patterns = [
            r'(là gì|là ai|nghĩa là gì)',  # Tiếng Việt
            r'(what is|what are|who is|define|definition of)',  # English
            r'(giải thích|explain|clarify)\s+\w+\s+(là|là gì)',
            r'^(khái niệm|concept)\s+',
        ]
        
        # Keywords cho câu hỏi complex
        self.complex_keywords = [
            # So sánh, phân tích
            'so sánh', 'khác biệt', 'giống nhau', 'compare', 'difference',
            'ưu điểm', 'nhược điểm', 'advantages', 'disadvantages',
            
            # Giải thích sâu
            'giải thích chi tiết', 'phân tích', 'tại sao', 'vì sao', 'why', 'how',
            'nguyên nhân', 'explain', 'analyze',
            
            # Đa chiều
            'các loại', 'các bước', 'quy trình', 'process', 'workflow',
            'ứng dụng', 'áp dụng', 'thực tế', 'applications',
            
            # Tổng hợp
            'tổng hợp', 'tổng kết', 'summarize', 'overview',
            'toàn bộ', 'tất cả', 'đầy đủ', 'comprehensive',

            # Multi-document / Multi-file
            'các file', 'các tài liệu', 'nhiều file', 'nhiều tài liệu',
            'từng file', 'từng tài liệu', 'mỗi file', 'mỗi tài liệu',
            'tất cả file', 'tất cả tài liệu',
        ]
        
        # Keywords cho câu hỏi moderate (trung bình)
        self.moderate_keywords = [
            'cách thức', 'phương pháp', 'method',
            'ví dụ', 'example',
            'hoạt động', 'work', 'function',
            'khái niệm', 'concept'
        ]
    
    def analyze(self, query: str) -> Literal["simple", "moderate", "complex"]:
        """
        Phân tích độ phức tạp của câu hỏi
        
        Args:
            query: Câu hỏi của user
        
        Returns:
            "simple" | "moderate" | "complex"
        """
        try:
            print(f"\n🔍 ========== ANALYZING QUERY COMPLEXITY ==========")
            print(f"   Query: '{query}'")
            query_lower = query.lower().strip()
            query_clean = re.sub(r'[^\w\s\+\-\*\/]', '', query_lower)
            print(f"   Cleaned: '{query_clean}'")
            
            # PRIORITY 1: Check SIMPLE patterns (math calc, basic calc)
            for pattern in self.simple_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    print(f"✅ Result: SIMPLE (pattern '{pattern}' matched: '{match.group()}')")
                    print(f"================================================\n")
                    return "simple"
            
            # PRIORITY 2: Check DEFINITION patterns (always need explanation)
            # Câu hỏi "X là gì?", "what is X?" → MODERATE (cần giải thích đầy đủ)
            for pattern in self.definition_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    # Trừ câu rất ngắn (≤3 words) như "AI?"
                    words = query_clean.split()
                    if len(words) > 2:
                        print(f"✅ Result: MODERATE (definition pattern: '{pattern}', matched: '{match.group()}')")
                        print(f"================================================\n")
                        return "moderate"
            
            # PRIORITY 3: Check length (câu quá ngắn thường simple)
            words = query_clean.split()
            word_count = len(words)
            print(f"   Word count: {word_count}")
            
            if word_count <= 2:
                print(f"✅ Result: SIMPLE (≤2 words)")
                print(f"================================================\n")
                return "simple"
            
            # PRIORITY 4: Check COMPLEX keywords
            complex_score = sum(
                1 for keyword in self.complex_keywords 
                if keyword in query_lower
            )
            print(f"   Complex score: {complex_score}")
            
            if complex_score >= 2:
                print(f"✅ Result: COMPLEX (keywords: {complex_score})")
                print(f"================================================\n")
                return "complex"
            
            # PRIORITY 5: Check MODERATE keywords
            moderate_score = sum(
                1 for keyword in self.moderate_keywords
                if keyword in query_lower
            )
            print(f"   Moderate score: {moderate_score}")
            
            # PRIORITY 6: Length-based classification
            if word_count >= 15:
                print(f"✅ Result: COMPLEX (≥15 words)")
                print(f"================================================\n")
                return "complex"
            elif word_count >= 6:
                print(f"✅ Result: MODERATE (6-14 words)")
                print(f"================================================\n")
                return "moderate"
            
            # PRIORITY 7: Moderate keywords detected
            if moderate_score >= 1:
                print(f"✅ Result: MODERATE (keywords)")
                print(f"================================================\n")
                return "moderate"
            
            # PRIORITY 8: Complex keywords detected (even 1)
            if complex_score >= 1:
                print(f"✅ Result: COMPLEX (keyword)")
                print(f"================================================\n")
                return "complex"
            
            # PRIORITY 9: Default: moderate for safety
            print(f"✅ Result: MODERATE (default)")
            print(f"================================================\n")
            return "moderate"
        
        except Exception as e:
            print(f"❌ Complexity analysis error: {e}")
            return "moderate"  # Safe default
    
    def get_response_guidance(self, complexity: str) -> Dict[str, Any]:
        """
        Lấy hướng dẫn format response theo complexity
        
        Args:
            complexity: "simple" | "moderate" | "complex"
        
        Returns:
            Dict với max_length, format_type, level_of_detail
        """
        guidance = {
            "simple": {
                "max_length": 100,  # words
                "format_type": "direct",
                "level_of_detail": "minimal",
                "description": "Trả lời trực tiếp, ngắn gọn 1-2 câu"
            },
            "moderate": {
                "max_length": 300,
                "format_type": "structured_short",
                "level_of_detail": "moderate",
                "description": "Giải thích vừa phải với 2-3 điểm chính"
            },
            "complex": {
                "max_length": 800,
                "format_type": "structured_full",
                "level_of_detail": "comprehensive",
                "description": "Phân tích đầy đủ với cấu trúc hoàn chỉnh"
            }
        }
        
        return guidance.get(complexity, guidance["moderate"])


# Global instance
complexity_analyzer = QueryComplexityAnalyzer()
