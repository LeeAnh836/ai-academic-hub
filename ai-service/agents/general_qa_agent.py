"""
General QA Agent
Handles general questions with tool support (future: MCP integration)
"""
from typing import Dict, Any, List, Optional
import logging
import re

from agents import BaseAgent
from core.config import settings
from services.query_complexity_analyzer import complexity_analyzer
from services.computation_pipeline import computation_pipeline

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
            
            # Get chat history for context continuity
            chat_history = context.get("chat_history", [])

            intent = context.get("intent")
            if intent in {"computation", "analysis"}:
                # Guardrail: not every query containing "tính/công thức" should go through
                # the computation pipeline. Only use tool+plan extraction when the user
                # actually requests a numeric result or a concrete calculation.
                if not self._should_use_computation_pipeline(query):
                    logger.info("↩️ Intent suggests computation/analysis, but query is informational → direct QA")
                    answer = await self._answer_direct(
                        query=query,
                        complexity=complexity_analyzer.analyze(query),
                        intent="qa",
                        chat_history=chat_history,
                    )
                    self.save_state(user_id, session_id, {"last_query": query, "tool_used": False})
                    self.memory.set_context(user_id, session_id, "last_action", "general_qa")
                    return {
                        "answer": answer,
                        "metadata": {
                            "tool_used": False,
                            "fallback_from": f"intent_{intent}",
                            **self.build_quota_metadata(answer),
                        },
                    }

                logger.info(f"🧮 Using computation pipeline for intent={intent}")
                comp_result = computation_pipeline.run(
                    query=query,
                    contexts=None,
                    intent=intent,
                    chat_history=chat_history,
                )
                # If the computation pipeline can't extract a plan (common for
                # general knowledge questions like "một năm có bao nhiêu ngày"),
                # fall back to direct chat instead of returning a misleading error.
                meta = comp_result.get("metadata") or {}
                if meta.get("error") == "plan_extraction_failed":
                    logger.info("↩️ Computation plan extraction failed → fallback to direct QA")
                    answer = await self._answer_direct(
                        query=query,
                        complexity=complexity_analyzer.analyze(query),
                        intent="qa",
                        chat_history=chat_history,
                    )
                    tool_used = False
                    tool_meta = {"tool_used": False, "fallback_from": "computation_pipeline"}
                else:
                    answer = comp_result.get("answer", "")
                    tool_used = True
                    tool_meta = {
                        "tool_used": True,
                        "model": "tool+llm",
                        **(meta or {}),
                    }
                self.save_state(user_id, session_id, {
                    "last_query": query,
                    "tool_used": tool_used
                })
                self.memory.set_context(user_id, session_id, "last_action", "computation" if tool_used else "general_qa")
                return {
                    "answer": answer,
                    "metadata": {
                        **tool_meta,
                        **self.build_quota_metadata(answer)
                    }
                }
            
            # Detect if tools are needed
            tool_needed = self._detect_tool_need(query)
            
            # Analyze query complexity
            complexity = complexity_analyzer.analyze(query)
            logger.info(f"📊 Query complexity: {complexity}")
            
            if tool_needed:
                # Use tool-augmented response
                answer = await self._answer_with_tools(query, tool_needed, complexity)
            else:
                # Direct LLM response with conversation history
                answer = await self._answer_direct(query, complexity, context.get("intent"), chat_history)
            
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
        query_lower = (query or "").lower()
        
        # Weather queries should use Google Search grounding
        if self._is_weather_query(query_lower):
            return "weather"

        # Time-sensitive info (price/news/market) should use Google Search grounding
        if self._needs_google_search(query_lower):
            return "web_search"

        # Calculator tool (only for real math expressions, not dates/codes)
        if self._looks_like_math_expression(query_lower):
            return "calculator"
        
        return None

    def _looks_like_math_expression(self, query_lower: str) -> bool:
        if not query_lower:
            return False
        if not any(ch.isdigit() for ch in query_lower):
            return False

        # Exclude dates and document codes
        if self._looks_like_date(query_lower) or self._looks_like_doc_code(query_lower):
            return False

        # Require at least two numbers with a math operator between them
        expr_pattern = r"\b\d+(?:[\.,]\d+)?\s*[+\-*/^]\s*\d+(?:[\.,]\d+)?\b"
        if re.search(expr_pattern, query_lower):
            return True

        calc_markers = ["tính", "calculate", "solve", "phương trình", "equation"]
        if any(m in query_lower for m in calc_markers):
            return True

        return False

    def _looks_like_date(self, query_lower: str) -> bool:
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
            r"\bng[aà]y\s+\d{1,2}\s+th[aá]ng\s+\d{1,2}\s+n[aă]m\s+\d{2,4}\b",
        ]
        return any(re.search(pat, query_lower) for pat in date_patterns)

    def _looks_like_doc_code(self, query_lower: str) -> bool:
        return bool(re.search(r"\b\d{1,4}/[a-zA-ZÀ-Ỹ0-9-]{2,}\b", query_lower))

    def _looks_like_official_doc_query(self, query_lower: str) -> bool:
        doc_keywords = [
            "công điện", "cong dien",
            "nghị định", "nghi dinh",
            "thông tư", "thong tu",
            "quyết định", "quyet dinh",
            "chỉ thị", "chi thi",
            "công văn", "cong van",
            "nghị quyết", "nghi quyet",
            "văn bản", "van ban",
            "luật", "luat",
        ]
        if any(k in query_lower for k in doc_keywords):
            return True
        return self._looks_like_doc_code(query_lower)

    def _looks_like_sports_query(self, query_lower: str) -> bool:
        sports_keywords = [
            "tỷ số", "ty so",
            "kết quả", "ket qua",
            "trận", "tran",
            "derby", "vs", "đối đầu", "doi dau",
            "giành chiến thắng", "chien thang",
            "thắng", "thang",
            "bóng đá", "bong da",
        ]
        return any(k in query_lower for k in sports_keywords)

    def _is_weather_query(self, query_lower: str) -> bool:
        weather_keywords = [
            "thời tiết", "thoi tiet", "weather",
            "nhiệt độ", "nhiet do", "temperature",
            "dự báo", "du bao", "forecast",
            "mưa", "mua", "nắng", "nang",
            "độ ẩm", "do am", "gió", "gio",
        ]
        return any(kw in query_lower for kw in weather_keywords)

    def _needs_google_search(self, query_lower: str) -> bool:
        if not query_lower:
            return False

        # Explicit dates often imply time-sensitive or event-specific lookup
        if self._looks_like_date(query_lower):
            return True

        # Official documents/news should be searched
        if self._looks_like_official_doc_query(query_lower):
            return True

        # Sports results and event outcomes
        if self._looks_like_sports_query(query_lower):
            return True

        price_targets = [
            "vàng", "vang", "tỷ giá", "ty gia", "usd", "đô", "do la",
            "dollar", "vnd", "bitcoin", "btc", "eth", "crypto",
            "chứng khoán", "chung khoan", "cổ phiếu", "co phieu",
            "xăng", "xang", "dầu", "dau", "lãi suất", "lai suat",
            "bất động sản", "bat dong san",
        ]
        news_markers = [
            "tin tức", "tin tuc", "news", "mới nhất", "moi nhat",
            "latest", "breaking", "trực tiếp", "truc tiep", "live",
            "vừa ký", "vua ky", "mới ký", "moi ky",
            "vừa ban hành", "vua ban hanh", "mới ban hành", "moi ban hanh",
        ]
        time_markers = [
            "hôm nay", "hom nay", "hiện nay", "hien nay",
            "hiện tại", "hien tai", "bây giờ", "bay gio",
            "current", "today", "now", "real-time", "real time",
        ]

        if "tỷ giá" in query_lower or "ty gia" in query_lower:
            return True

        if any(marker in query_lower for marker in news_markers):
            return True

        if "giá" in query_lower or "gia" in query_lower or "price" in query_lower:
            if any(target in query_lower for target in price_targets):
                return True
            if any(marker in query_lower for marker in time_markers):
                return True

        if any(marker in query_lower for marker in time_markers) and any(
            target in query_lower for target in price_targets
        ):
            return True

        return False

    def _should_use_computation_pipeline(self, query: str) -> bool:
        """
        Decide whether we should route to computation_pipeline for a general query.
        We only do this when the user likely wants a computed numeric result.
        """
        q = (query or "").lower()
        if not q.strip():
            return False

        # If the user explicitly asks for a formula/definition, do NOT run tool pipeline.
        formula_markers = [
            "công thức", "formula", "quy tắc", "định nghĩa",
            "là gì", "what is", "define", "definition",
        ]
        if any(m in q for m in formula_markers):
            # Unless they also provide concrete numbers / ask for a numeric result.
            pass

        numeric_markers = [
            "bao nhiêu", "bằng bao nhiêu", "kết quả", "result",
            "tính", "calculate", "solve",
        ]
        has_digits = any(ch.isdigit() for ch in q)
        has_operator = any(op in q for op in ["+", "-", "*", "/", "=", "%"])

        # Typical: "tính X khi a=.., b=.." or "bao nhiêu" + digits/operators.
        if has_digits and (has_operator or any(m in q for m in numeric_markers)):
            return True

        # Without numbers/operators, treat it as informational.
        return False
    
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
            if tool_name in {"web_search", "weather"}:
                return await self._answer_with_google_search(query, complexity)

            # Get tool function
            tool_func = self.tools.get(tool_name)
            
            if not tool_func:
                return await self._answer_direct(query)
            
            # Execute tool
            tool_result = await tool_func(query)

            if tool_name == "calculator" and not tool_result.get("success"):
                err = (tool_result.get("error") or "").lower()
                if any(token in err for token in ["leading zeros", "invalid syntax", "not_math_expression"]):
                    logger.info("↩️ Calculator parse error → fallback to direct QA")
                    return await self._answer_direct(query, complexity)
            
            # Generate answer with tool result (pass complexity)
            return await self._integrate_tool_result(query, tool_result, complexity)
        
        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return await self._answer_direct(query)

    async def _answer_with_google_search(self, query: str, complexity: str = "moderate") -> str:
        """
        Answer time-sensitive queries using Gemini Google Search grounding.
        """
        try:
            if not settings.ENABLE_GEMINI_GOOGLE_SEARCH:
                logger.info("Google Search grounding disabled by config → direct QA")
                return await self._answer_direct(query, complexity)

            # Analyze complexity if not provided
            if not complexity:
                complexity = complexity_analyzer.analyze(query)

            model_complexity = {
                "simple": "low",
                "moderate": "medium",
                "complex": "high"
            }.get(complexity, "medium")

            provider_name, model_identifier = self.model_manager.get_model(
                task_type="direct_chat",
                complexity=model_complexity,
                force_provider="gemini",
            )

            if "gemini" not in provider_name:
                return (
                    "Hiện không thể dùng Google Search vì Gemini chưa sẵn sàng "
                    "(thiếu API key hoặc hết quota). Vui lòng thử lại sau."
                )

            system_instruction = (
                "Bạn là trợ lý cung cấp thông tin cập nhật. "
                "Hãy dùng Google Search khi câu hỏi cần dữ liệu mới nhất "
                "(giá, thời tiết, tin tức). "
                "Trả lời ngắn gọn, nêu thời điểm nếu có. "
                "Nếu không tìm thấy kết quả đáng tin, hãy nói rõ."
            )

            return self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=query,
                system_instruction=system_instruction,
                temperature=0.2,
                max_tokens=2500,
                enable_fallback=False,
                enable_google_search=True,
            )

        except Exception as e:
            logger.error(f"❌ Google Search grounding error: {e}")
            return await self._answer_direct(query, complexity)
    
    async def _answer_direct(self, query: str, complexity: str = None, intent: Optional[str] = None, chat_history: Optional[List[Dict]] = None) -> str:
        """
        Direct LLM answer without tools
        
        Args:
            query: User query
            complexity: Query complexity (simple/moderate/complex)
            intent: Classified intent
            chat_history: Conversation history for context continuity
        """
        try:
            # Analyze complexity if not provided
            if not complexity:
                complexity = complexity_analyzer.analyze(query)
            
            # Detect request type: creative vs analytical
            request_type = self._detect_request_type(query)
            is_code_request = self._is_code_request(query)
            
            # Dynamic system instruction based on complexity and type
            system_instruction = self._get_system_prompt(complexity, request_type, intent, is_code_request)
            
            # Build conversation context from history
            history_prompt = self._build_history_prompt(chat_history)
            
            # Build final prompt with history context
            if history_prompt:
                full_prompt = history_prompt + query
            else:
                full_prompt = query
            
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
            
            print(f"🤖 Using {provider_name} | model: {model_identifier} | complexity: {complexity} | temp: {temperature} | history: {len(chat_history or [])} msgs")
            
            answer = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_identifier,
                prompt=full_prompt,
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

    def _is_code_request(self, query: str) -> bool:
        """
        Detect if query is asking for code generation or debugging.
        """
        query_lower = query.lower()
        code_keywords = [
            "code", "viết code", "lập trình", "program",
            "function", "class", "debug", "fix", "bug",
            "python", "java", "javascript", "c#", "c++",
            "typescript", "golang", "rust",
        ]
        return any(kw in query_lower for kw in code_keywords)
    
    def _build_history_prompt(self, chat_history: Optional[List[Dict]] = None) -> str:
        """
        Build conversation history section for LLM prompt.
        This enables context continuity within a chat session,
        similar to how GPT/Gemini remembers previous messages.
        
        Args:
            chat_history: List of {"role": "user"|"assistant", "content": "..."}
        
        Returns:
            Formatted history string to prepend to user prompt, or empty string
        """
        if not chat_history:
            return ""
        
        # Take last 12 messages (6 turns) for context
        recent = chat_history[-12:]
        
        if not recent:
            return ""
        
        lines = []
        for msg in recent:
            role = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
            content = msg.get("content", "")
            # Truncate very long messages to save tokens (decreased to 1000)
            if len(content) > 1000:
                content = content[:1000] + "\n...[truncated]"
            lines.append(f"{role}: {content}")
        
        return (
            "LỊCH SỬ TRÒ CHUYỆN (dùng để hiểu ngữ cảnh câu hỏi hiện tại):\n"
            + "\n".join(lines)
            + "\n\nCÂU HỎI HIỆN TẠI: "
        )
    
    def _get_system_prompt(
        self,
        complexity: str,
        request_type: str = "analytical",
        intent: Optional[str] = None,
        is_code_request: bool = False,
    ) -> str:
        """
        Get dynamic system prompt based on query complexity and request type
        
        Args:
            complexity: "simple" | "moderate" | "complex"
            request_type: "creative" | "analytical"
        
        Returns:
            System instruction string
        """
        if complexity == "simple":
            if intent == "code_help" or is_code_request:
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

            return """Bạn là trợ lý thông minh. Trả lời câu hỏi NGẮN GỌN, TỰ NHIÊN và ĐÚNG TRỌNG TÂM.

YÊU CẦU:
✅ Trả lời khoảng 1-3 câu (hoặc 1 dòng nếu là số/kết quả hiển nhiên)
✅ Không chào hỏi dài dòng, không rào trước đón sau
✅ Chỉ giải thích 1 câu rất ngắn nếu người dùng hỏi "là gì" / "vì sao"
✅ Không tự động thêm các mục như "Tổng quan / Ứng dụng" trừ khi được hỏi

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
                if intent == "code_help" or is_code_request:
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

                return """Bạn là trợ lý học tập: rõ ràng, mạch lạc, thân thiện và TỰ NHIÊN như chatbot.

NGUYÊN TẮC:
✅ **ĐÚNG TRỌNG TÂM**: Trả lời đúng câu hỏi người dùng trước
✅ **MƯỢT MÀ**: Viết thành đoạn văn/nhóm ý liền mạch, tránh rời rạc
✅ **VỪA ĐỦ**: Câu cơ bản trả lời ngắn; câu cần học sâu thì giải thích chi tiết hơn
✅ **LINH HOẠT FORMAT**:
   - Nếu chỉ có 1 ý: trả lời dạng đoạn văn ngắn
   - Nếu có nhiều ý: mới dùng bullet points
   - Không mặc định "Tổng quan / Ứng dụng thực tế" nếu người dùng không yêu cầu

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
                if intent == "code_help" or is_code_request:
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

                return """Bạn là trợ lý học tập chuyên sâu. Trả lời CHI TIẾT nhưng mạch lạc và LINH HOẠT theo câu hỏi.

NGUYÊN TẮC TRẢ LỜI:
✅ **CHÍNH XÁC tuyệt đối**: Không bỏ sót thông tin quan trọng
✅ **ĐẦY ĐỦ**: Liệt kê TẤT CẢ các khía cạnh/nguyên lý/thành phần
✅ **CÓ CHIỀU SÂU**: Phân tích kỹ lưỡng, làm rõ mối liên hệ
✅ **CÓ CĂN CỨ**: Dựa trên kiến thức chuẩn xác, không bịa đặt
✅ **DỄ HIỂU**: Giải thích rõ ràng với ví dụ cụ thể
✅ **LIỀN MẠCH**: Không tách câu thành mảnh rời rạc
✅ **KHÔNG ĐÓNG KHUNG**: Không bắt buộc phải có "Tổng quan/Ứng dụng" hay các heading cố định. Chỉ dùng khi phù hợp.

FORMAT OUTPUT:
- Ưu tiên 1 câu trả lời liền mạch có cấu trúc tự nhiên.
- Nếu cần chia phần, dùng markdown nhẹ (###) tối đa 2-4 mục.
- Nếu người dùng chỉ hỏi 1 điểm cụ thể, trả lời thẳng vào điểm đó trước.

QUY TẮC CHO CÂU HỎI CODE:
✅ Chỉ dùng 1 code block chính nếu cần minh họa
✅ Tên biến trong phần mô tả để inline code, không tách thành block riêng
✅ Giải thích theo trình tự chạy của code, từ trên xuống dưới
✅ Tuyệt đối tránh output kiểu từng từ một dòng

VÍ DỤ TRẢ LỜI TỐT:
"OOP có **4 nguyên lý cơ bản**: **Encapsulation** (đóng gói dữ liệu và phương thức), **Inheritance** (kế thừa từ class cha), **Polymorphism** (đa hình - cùng hành động nhưng khác cách thực hiện), và **Abstraction** (trừu tượng hóa)..."

YÊU CẦU:
✅ Chi tiết (~300-500 từ)
✅ CẤM bỏ sót thông tin quan trọng
✅ Cấu trúc rõ ràng nhưng linh hoạt (không rập khuôn)
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
            if not self._looks_like_math_expression((query or "").lower()):
                return {
                    "tool": "calculator",
                    "result": "",
                    "success": False,
                    "error": "not_math_expression",
                }
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
