"""
General QA Agent
Handles general questions with tool support (future: MCP integration)
"""
from typing import Dict, Any, List, Optional, Literal
import logging

from agents import BaseAgent
from core.config import settings
from services.query_complexity_analyzer import complexity_analyzer

logger = logging.getLogger(__name__)


class GeneralQAAgent(BaseAgent):
    """
    Agent for general question answering
    Supports tools and external data sources (MCP)
    """
    
    def __init__(self):
        super().__init__(
            agent_name="general_qa_agent",
            description="Answers general questions with tool support"
        )
        
        # Available tools (will expand with MCP)
        self.tools = {
            "calculator": self._calculator_tool,
            "web_search": self._web_search_tool,  # Placeholder for MCP
            "weather": self._weather_tool  # Placeholder for MCP
        }
    
    async def execute(
        self,
        query: str,
        user_id: str,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute general QA task
        
        Args:
            query: User question
            user_id: User ID
            session_id: Session ID
            context: Additional context
        
        Returns:
            Dict with answer
        """
        try:
            logger.info(f"💬 General QA: {query}")
            
            # Detect if tools are needed
            tool_needed = self._detect_tool_need(query)
            
            # Analyze query complexity
            complexity = complexity_analyzer.analyze(query)
            logger.info(f"📊 Query complexity: {complexity}")
            
            if tool_needed:
                # Use tool-augmented response
                answer = await self._answer_with_tools(query, tool_needed, complexity)
            else:
                # Direct LLM response
                answer = await self._answer_direct(query, complexity, context.get("intent"))
            
            # Save state
            self.save_state(user_id, session_id, {
                "last_query": query,
                "tool_used": tool_needed
            })
            
            self.memory.set_context(user_id, session_id, "last_action", "general_qa")
            
            return {
                "answer": answer,
                "metadata": {
                    "tool_used": tool_needed,
                    "model": "gemini-flash",
                    **self.build_quota_metadata(answer)
                }
            }
        
        except Exception as e:
            logger.error(f"❌ General QA error: {e}")
            err_text = f"Lỗi khi trả lời câu hỏi: {e}"
            return {
                "answer": err_text,
                "metadata": {
                    "error": str(e),
                    **self.build_quota_metadata(err_text)
                }
            }
    
    def _detect_tool_need(self, query: str) -> Optional[str]:
        """
        Detect if query needs a tool
        
        Returns:
            Tool name or None
        """
        query_lower = query.lower()
        
        # Calculator tool
        calc_keywords = ["tính", "calculate", "+", "-", "*", "/", "=", "phương trình"]
        if any(kw in query_lower for kw in calc_keywords):
            return "calculator"
        
        # Web search tool (placeholder - will use MCP)
        search_keywords = ["giá", "price", "tin tức", "news", "hiện tại", "current"]
        if any(kw in query_lower for kw in search_keywords):
            return "web_search"
        
        # Weather tool (placeholder - will use MCP)
        weather_keywords = ["thời tiết", "weather", "nhiệt độ", "temperature"]
        if any(kw in query_lower for kw in weather_keywords):
            return "weather"
        
        return None
    
    async def _answer_with_tools(
        self,
        query: str,
        tool_name: str,
        complexity: str = "moderate"
    ) -> str:
        """
        Answer question using tools
        """
        try:
            # Get tool function
            tool_func = self.tools.get(tool_name)
            
            if not tool_func:
                return await self._answer_direct(query)
            
            # Execute tool
            tool_result = await tool_func(query)
            
            # Generate answer with tool result (pass complexity)
            return await self._integrate_tool_result(query, tool_result, complexity)
        
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return await self._answer_direct(query)
    
    async def _answer_direct(self, query: str, complexity: str = None, intent: Optional[str] = None) -> str:
        """
        Direct LLM answer without tools
        
        Args:
            query: User query
            complexity: Query complexity (simple/moderate/complex)
        """
        try:
            # Analyze complexity if not provided
            if not complexity:
                complexity = complexity_analyzer.analyze(query)
            
            # Detect request type: creative vs analytical
            request_type = self._detect_request_type(query)
            
            # Dynamic system instruction based on complexity and type
            system_instruction = self._get_system_prompt(complexity, request_type, intent)
            
            # Map complexity to model selection
            model_complexity = {
                "simple": "low",
                "moderate": "medium",
                "complex": "high"
            }.get(complexity, "medium")
            
            # Get appropriate model based on complexity
            provider_name, model_identifier = self.model_manager.get_model(
                task_type="direct_chat",
                complexity=model_complexity
            )
            
            # Dynamic temperature: Lower for knowledge, higher for creative
            temperature = 0.3 if complexity in ["moderate", "complex"] else 0.7
            
            print(f"🤖 Using {provider_name} | model: {model_identifier} | complexity: {complexity} | temp: {temperature}")
            
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=query,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=3000
            )
            
            return answer
        
        except Exception as e:
            logger.error(f"❌ Answer generation error: {e}")
            return f"Lỗi khi tạo câu trả lời: {e}"
    
    def _detect_request_type(self, query: str) -> str:
        """
        Detect if query is creative (writing) or analytical (explanation)
        
        Returns:
            "creative" or "analytical"
        """
        query_lower = query.lower()
        
        # Creative keywords: viết, tạo, sáng tác...
        creative_keywords = [
            "viết", "write", "tạo ra", "create", "compose",
            "draft", "soạn", "sáng tác", "làm thơ", "làm bài",
            "vẽ", "thiết kế", "design", "kể chuyện", "story"
        ]
        
        return "creative" if any(kw in query_lower for kw in creative_keywords) else "analytical"
    
    def _get_system_prompt(self, complexity: str, request_type: str = "analytical", intent: Optional[str] = None) -> str:
        """
        Get dynamic system prompt based on query complexity and request type
        
        Args:
            complexity: "simple" | "moderate" | "complex"
            request_type: "creative" | "analytical"
        
        Returns:
            System instruction string
        """
        if complexity == "simple":
            if intent == "code_help":
                return """Bạn là trợ giảng lập trình theo phong cách GPT.

MỤC TIÊU:
✅ Trả lời nhanh, rõ, mượt cho câu hỏi code cơ bản.

YÊU CẦU:
✅ 2-5 câu ngắn, đi thẳng vào ý chính.
✅ Nếu có code, chỉ dùng 1 code block ngắn (khi thực sự cần).
✅ Không tách từng biến thành block riêng.
✅ Tên biến trong câu viết inline code: `left`, `right`, `mid`.
✅ Không tạo dòng rời rạc chỉ có dấu chấm hoặc từ nối.
"""

            return """Bạn là trợ lý thông minh. Trả lời câu hỏi NGẮN GỌN, TRỰC TIẾP.

YÊU CẦU:
✅ CHỈ trả lời ĐÁP ÁN - MỘT câu hoặc VÀI từ
✅ KHÔNG giải thích, KHÔNG phân tích
✅ KHÔNG thêm phần giới thiệu/kết luận
✅ KHÔNG dùng heading/markdown phức tạp
✅ Đi thẳng vào kết quả

VÍ DỤ ĐÚNG:
- "1+1 bằng mấy?" → "2"
- "100+50 bằng bao nhiêu?" → "150"
- "Thủ đô Việt Nam?" → "Hà Nội"
- "Python là gì?" → "Python là ngôn ngữ lập trình bậc cao."

VÍ DỤ SAI (quá dài):
- "Chào bạn! Phép cộng là..." ❌
- "Để giải quyết câu hỏi này..." ❌
"""
        
        elif complexity == "moderate":
            # CREATIVE MODE: Viết văn, tạo nội dung
            if request_type == "creative":
                return """Bạn là trợ lý sáng tạo nội dung chuyên nghiệp. Thực hiện yêu cầu của người dùng một cách TỰ NHIÊN và SÁNG TẠO.

NGUYÊN TẮC:
✅ **TỰ NHIÊN**: Viết như một người thật, không máy móc
✅ **PHÙ HỢP YÊU CẦU**: Tuân thủ độ dài, phong cách, chủ đề người dùng yêu cầu
✅ **SÁNG TẠO**: Dùng từ ngữ phong phú, đa dạng
✅ **LƯU LOÁT**: Câu văn mạch lạc, dễ đọc

YÊU CẦU:
✅ KHÔNG dùng format cứng nhắc (Định nghĩa/Thành phần/Giải thích)
✅ KHÔNG dùng heading/bullet points trừ khi người dùng yêu cầu
✅ Viết thành đoạn văn liền mạch, tự nhiên
✅ Tuân thủ độ dài người dùng yêu cầu (nếu có)
✅ Kết thúc hoàn chỉnh, không dang dở

VÍ DỤ:
YC: "Viết đoạn văn 200 chữ về bảo vệ môi trường"
TL: "Bảo vệ môi trường là trách nhiệm của mỗi người trong xã hội hiện đại. Với tình trạng ô nhiễm không khí ngày càng nghiêm trọng, việc giảm thiểu khí thải và sử dụng năng lượng sạch trở nên cấp thiết hơn bao giờ hết. Chúng ta cần..."

❌ KHÔNG TRẢ LỜI KIỂU NÀY:
"Định nghĩa: Bảo vệ môi trường là...
Các thành phần chính:
- Giảm ô nhiễm
- Bảo tồn tài nguyên"
"""
            
            # ANALYTICAL MODE: Giải thích, phân tích
            else:
                if intent == "code_help":
                    return """Bạn là trợ giảng lập trình theo phong cách GPT/Gemini: giải thích mạch lạc, dễ học.

MỤC TIÊU:
✅ Trả lời tự nhiên, liền mạch, theo đúng trình tự suy nghĩ của người học.

FORMAT KHUYẾN NGHỊ:
1) Tóm tắt ý chính (1-2 câu)
2) Code mẫu (nếu cần) - đúng 1 code block
3) Giải thích theo trình tự thực thi: Input -> Biến -> Điều kiện -> Kết quả
4) Ví dụ ngắn

QUY TẮC BẮT BUỘC:
✅ Không tách biến/hàm thành các khối code riêng lẻ.
✅ Không dùng bullet mà mỗi bullet chỉ có 1 từ.
✅ Dùng inline code trong câu cho token ngắn: `arr`, `target`, `left`.
✅ Giữ văn phong tự nhiên, không máy móc.
✅ Câu cơ bản: ngắn gọn. Câu nâng cao: chi tiết hơn.
"""

                return """Bạn là trợ lý học tập theo phong cách GPT/Gemini: rõ ràng, mạch lạc, thân thiện.

NGUYÊN TẮC:
✅ **ĐÚNG TRỌNG TÂM**: Trả lời đúng câu hỏi người dùng trước
✅ **MƯỢT MÀ**: Viết thành đoạn văn/nhóm ý liền mạch, tránh rời rạc
✅ **VỪA ĐỦ**: Câu cơ bản trả lời ngắn; câu cần học sâu thì giải thích chi tiết hơn
✅ **DỄ HỌC**: Nếu là code thì giải thích theo trình tự (mục tiêu -> ý tưởng -> từng bước)

QUY TẮC CHO CÂU HỎI CODE:
✅ Nếu cần code mẫu, đưa 1 khối code đầy đủ (không tách thành nhiều khối nhỏ)
✅ Tên biến/hàm trong câu chỉ dùng inline code như `left`, `right`, `mid`
✅ KHÔNG tạo code block chỉ để chứa 1 từ hoặc 1 biến
✅ Không xuống dòng kiểu rời rạc: dấu chấm riêng, từ nối riêng

YÊU CẦU:
✅ Độ dài linh hoạt: cơ bản ~2-5 câu, nâng cao ~150-300 từ
✅ Dùng markdown vừa phải để dễ đọc
✅ KHÔNG dùng heading ### cho câu hỏi cơ bản

VÍ DỤ TỐT:
Q: "OOP là gì?"
A: "OOP (Object-Oriented Programming) là **phương pháp lập trình** dựa trên khái niệm đối tượng. Có **4 nguyên lý**:

- **Encapsulation** (đóng gói): Gom dữ liệu và phương thức vào 1 đơn vị
- **Inheritance** (kế thừa): Class con thừa hưởng từ class cha
- **Polymorphism** (đa hình): Cùng hành động, khác cách thực hiện
- **Abstraction** (trừu tượng): Ẩn chi tiết, chỉ hiện giao diện

Ví dụ: Class Animal có speak(), Dog kế thừa và override thành bark()."

Q: "Sắp xếp nổi bọt là gì?"
A: "Bubble Sort là **thuật toán sắp xếp đơn giản**:

- **So sánh** từng cặp phần tử liền kề
- **Hoán đổi** nếu sai thứ tự  
- **Lặp lại** đến khi không cần hoán đổi

**Độ phức tạp**: O(n²) - chậm với dữ liệu lớn
**Ưu điểm**: Đơn giản, dễ hiểu

Ví dụ: [5,2,8,1] → [2,5,1,8] → ... → [1,2,5,8]"
"""
        
        else:  # complex
            # CREATIVE MODE: Viết nội dung dài, phức tạp
            if request_type == "creative":
                return """Bạn là chuyên gia sáng tạo nội dung. Thực hiện yêu cầu phức tạp một cách CHUYÊN NGHIỆP và SÁNG TẠO.

NGUYÊN TẮC:
✅ **CHUYÊN NGHIỆP**: Nội dung có chiều sâu, chất lượng cao
✅ **PHÙ HỢP YÊU CẦU**: Tuân thủ mọi yêu cầu về độ dài, phong cách, nội dung
✅ **SÁNG TẠO**: Dùng từ ngữ phong phú, cấu trúc đa dạng
✅ **MẠCH LẠC**: Luận điểm rõ ràng, logic chặt chẽ
✅ **HOÀN CHỈNH**: Có mở bài, thân bài, kết luận (nếu phù hợp)

YÊU CẦU:
✅ KHÔNG dùng format cứng nhắc (Định nghĩa/Thành phần/Giải thích)
✅ Tự nhiên, lưu loát như văn bản do người viết
✅ Có thể dùng heading ### nếu yêu cầu viết bài dài, có cấu trúc
✅ Tuân thủ độ dài yêu cầu

VÍ DỤ:
YC: "Viết bài luận về AI và tương lai"
TL: Viết thành bài luận hoàn chỉnh với mở bài, thân bài (nhiều đoạn), kết luận

YC: "Viết email chuyên nghiệp"
TL: Viết theo format email với Dear/Regards, không dùng bullet points
"""
            
            # ANALYTICAL MODE: Phân tích chuyên sâu
            else:
                if intent == "code_help":
                    return """Bạn là trợ giảng lập trình nâng cao theo phong cách GPT/Gemini.

MỤC TIÊU:
✅ Giải thích sâu nhưng mượt, liền mạch, không rời rạc.

FORMAT OUTPUT (markdown):
### 1. Ý tưởng tổng thể
### 2. Mã nguồn hoàn chỉnh (1 block)
### 3. Giải thích từng bước theo luồng chạy
### 4. Độ phức tạp và lưu ý
### 5. Ví dụ test nhanh

QUY TẮC:
✅ Chỉ 1 code block chính, không tách block nhỏ theo biến.
✅ Inline code cho tên biến/hàm ngắn.
✅ Không tạo dòng lẻ chỉ có dấu hoặc từ nối.
✅ Ưu tiên tính sư phạm, diễn đạt dễ hiểu cho người học.
"""

                return """Bạn là trợ lý học tập chuyên sâu theo phong cách GPT/Gemini. Trả lời CHI TIẾT nhưng mạch lạc, không rời rạc.

NGUYÊN TẮC TRẢ LỜI:
✅ **CHÍNH XÁC tuyệt đối**: Không bỏ sót thông tin quan trọng
✅ **ĐẦY ĐỦ**: Liệt kê TẤT CẢ các khía cạnh/nguyên lý/thành phần
✅ **CÓ CHIỀU SÂU**: Phân tích kỹ lưỡng, làm rõ mối liên hệ
✅ **CÓ CĂN CỨ**: Dựa trên kiến thức chuẩn xác, không bịa đặt
✅ **DỄ HIỂU**: Giải thích rõ ràng với ví dụ cụ thể
✅ **LIỀN MẠCH**: Không tách câu thành mảnh rời rạc

FORMAT OUTPUT: Markdown (dùng ###, **, -, 1.)

CẤU TRÚC TRẢ LỜI:

### 1. Tổng Quan
2-3 câu giới thiệu ngắn gọn về chủ đề

### 2. Các Điểm Chính
1. **Điểm 1**: Mô tả chi tiết với ví dụ
2. **Điểm 2**: Mô tả chi tiết với ví dụ
3. **Điểm 3**: Mô tả chi tiết với ví dụ
(Liệt kê ĐẦY ĐỦ TẤT CẢ các điểm quan trọng)

### 3. Giải Thích Chi Tiết
- Phân tích từng khía cạnh
- Làm rõ mối liên hệ
- Kèm ví dụ thực tế cụ thể
- Dùng **bold** cho từ khóa quan trọng

QUY TẮC CHO CÂU HỎI CODE:
✅ Chỉ dùng 1 code block chính nếu cần minh họa
✅ Tên biến trong phần mô tả để inline code, không tách thành block riêng
✅ Giải thích theo trình tự chạy của code, từ trên xuống dưới
✅ Tuyệt đối tránh output kiểu từng từ một dòng

### 4. Ứng Dụng Thực Tế
Ví dụ áp dụng trong thực tế (nếu phù hợp)

VÍ DỤ TRẢ LỜI TỐT:
"OOP có **4 nguyên lý cơ bản**: **Encapsulation** (đóng gói dữ liệu và phương thức), **Inheritance** (kế thừa từ class cha), **Polymorphism** (đa hình - cùng hành động nhưng khác cách thực hiện), và **Abstraction** (trừu tượng hóa)..."

YÊU CẦU:
✅ Chi tiết (~300-500 từ)
✅ CẤM bỏ sót thông tin quan trọng
✅ Có cấu trúc rõ ràng với heading ###
"""
    
    async def _integrate_tool_result(
        self,
        query: str,
        tool_result: Dict[str, Any],
        complexity: str = "simple"
    ) -> str:
        """
        Integrate tool result into answer
        
        Args:
            query: User query
            tool_result: Result from tool execution
            complexity: Query complexity level
        """
        try:
            # For SIMPLE queries with tools, return DIRECT result
            if complexity == "simple":
                result_value = tool_result.get('result', '')
                # Just return the number/result directly
                if tool_result.get('success'):
                    return str(result_value)
                else:
                    return f"Lỗi: {tool_result.get('error', 'Không thể thực hiện')}"
            
            # For MODERATE/COMPLEX queries, integrate naturally
            system_instruction = """Bạn là trợ lý thông minh. Trả lời câu hỏi dựa trên kết quả từ tool.

YÊU CẦU:
- Tích hợp kết quả tool vào câu trả lời tự nhiên
- Giải thích rõ ràng, dễ hiểu
- Ngắn gọn, súc tích
"""
            
            prompt = f"""CÂU HỎI: {query}

KẾT QUẢ TỪ TOOL:
{tool_result.get('result', '')}

TRẢ LỜI:"""
            
            provider_name, model_identifier = self.model_manager.get_model(
                task_type="direct_chat",
                complexity="low"
            )
            
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.5,
                max_tokens=2000
            )
            
            return answer
        
        except Exception as e:
            logger.error(f"❌ Tool integration error: {e}")
            return f"Kết quả: {tool_result.get('result', '')}"
    
    # ============================================
    # Tool Functions
    # ============================================
    
    async def _calculator_tool(self, query: str) -> Dict[str, Any]:
        """
        Calculator tool (basic Python eval)
        """
        try:
            # Extract math expression (simple approach)
            import re
            
            # Find numbers and operators
            expression = re.sub(r'[^\d+\-*/().= xX×]', '', query)
            expression = expression.replace('x', '*').replace('X', '*').replace('×', '*')
            expression = expression.strip()
            
            # Evaluate
            result = eval(expression)
            
            return {
                "tool": "calculator",
                "result": result,  # Return pure number
                "success": True
            }
        
        except Exception as e:
            return {
                "tool": "calculator",
                "result": f"Không thể tính toán: {e}",
                "success": False,
                "error": str(e)
            }
    
    async def _web_search_tool(self, query: str) -> Dict[str, Any]:
        """
        Web search tool (placeholder for MCP)
        """
        # TODO: Integrate with MC P web search server
        return {
            "tool": "web_search",
            "result": "🚧 Web search tool chưa được tích hợp. Sẽ cập nhật sau với MCP.",
            "success": False
        }
    
    async def _weather_tool(self, query: str) -> Dict[str, Any]:
        """
        Weather tool (placeholder for MCP)
        """
        # TODO: Integrate with MCP weather server
        return {
            "tool": "weather",
            "result": "🚧 Weather tool chưa được tích hợp. Sẽ cập nhật sau với MCP.",
            "success": False
        }


# Global singleton
general_qa_agent = GeneralQAAgent()
