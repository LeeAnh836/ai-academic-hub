"""
Corrective RAG (CRAG) Service
Advanced RAG - Self-Correction and Quality Evaluation

Implements:
1. Retrieval Quality Evaluation: Is the retrieved context sufficient to answer?
2. Corrective Re-retrieval: If insufficient, refine query and re-retrieve
3. Multi-hop Reasoning: Track sub-query answers and synthesize
"""
from typing import List, Dict, Any, Optional, Tuple
import logging

from core.model_manager import model_manager
from core.config import settings

logger = logging.getLogger(__name__)


class CorrectiveRAG:
    """
    Corrective RAG (CRAG) with Self-RAG quality evaluation.

    After initial retrieval, evaluates whether the retrieved context
    is sufficient to answer the query. If not, triggers corrective actions:
    - Refine query and re-retrieve
    - Lower similarity threshold
    - Flag as "insufficient context"
    """

    # Quality levels
    QUALITY_SUFFICIENT = "sufficient"
    QUALITY_PARTIAL = "partial"
    QUALITY_INSUFFICIENT = "insufficient"

    def evaluate_retrieval_quality(
        self,
        query: str,
        contexts: List[Dict[str, Any]]
    ) -> Tuple[str, float, str]:
        """
        Evaluate whether retrieved contexts are sufficient to answer the query.

        Returns:
            Tuple of (quality_level, confidence_score, reasoning)
            quality_level: "sufficient" | "partial" | "insufficient"
            confidence_score: 0.0 - 1.0
            reasoning: Brief explanation
        """
        if not contexts:
            return self.QUALITY_INSUFFICIENT, 0.0, "No contexts retrieved"

        # Build context preview for evaluation
        context_preview = ""
        for i, ctx in enumerate(contexts[:5]):  # Evaluate top 5 only
            text = ctx.get("chunk_text", "")[:300]
            context_preview += f"\n[Đoạn {i+1}]: {text}\n"

        system_prompt = """Bạn là chuyên gia đánh giá chất lượng tìm kiếm tài liệu.
Nhiệm vụ: Đánh giá xem các đoạn văn được tìm kiếm có đủ thông tin để trả lời câu hỏi không.

Trả lời theo định dạng JSON:
{
  "quality": "sufficient|partial|insufficient",
  "confidence": 0.0-1.0,
  "reason": "Giải thích ngắn gọn (1 câu)"
}

Định nghĩa:
- sufficient: Đoạn văn chứa đủ thông tin để trả lời đầy đủ câu hỏi
- partial: Đoạn văn có một phần thông tin nhưng không đầy đủ
- insufficient: Đoạn văn không liên quan hoặc không đủ thông tin

CHỈ trả lời JSON, không thêm gì khác."""

        user_prompt = f"""Câu hỏi: "{query}"

Các đoạn văn tìm được:
{context_preview}

Đánh giá:"""

        try:
            provider, model = model_manager.get_model("direct_chat", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.0,
                max_tokens=100
            )

            import json
            # Try to extract JSON from response
            response_text = response.strip()
            # Remove markdown code blocks if present
            if "```" in response_text:
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            data = json.loads(response_text)
            quality = data.get("quality", self.QUALITY_PARTIAL)
            confidence = float(data.get("confidence", 0.5))
            reason = data.get("reason", "")

            if quality not in [self.QUALITY_SUFFICIENT, self.QUALITY_PARTIAL, self.QUALITY_INSUFFICIENT]:
                quality = self.QUALITY_PARTIAL

            logger.info(f"🔍 CRAG eval: {quality} (confidence: {confidence:.2f}) - {reason}")
            return quality, confidence, reason

        except Exception as e:
            logger.warning(f"⚠️ CRAG evaluation failed: {e}")
            # Default to partial if evaluation fails
            avg_score = sum(ctx.get("score", 0) for ctx in contexts) / len(contexts)
            if avg_score >= 0.7:
                return self.QUALITY_SUFFICIENT, avg_score, "Score-based evaluation"
            elif avg_score >= 0.4:
                return self.QUALITY_PARTIAL, avg_score, "Score-based evaluation"
            else:
                return self.QUALITY_INSUFFICIENT, avg_score, "Score-based evaluation"

    def generate_corrective_query(
        self,
        original_query: str,
        failed_contexts: List[Dict[str, Any]],
        attempt: int = 1
    ) -> Optional[str]:
        """
        Generate a corrected/refined query when initial retrieval was insufficient.
        Uses the retrieved (but insufficient) contexts as hints for refinement.
        """
        try:
            # Build hint from what we DID find
            found_topics = ""
            if failed_contexts:
                topics = [ctx.get("title", ctx.get("file_name", "")) for ctx in failed_contexts[:3]]
                found_topics = f"\nTài liệu liên quan tìm được: {', '.join(t for t in topics if t)}"

            system_prompt = """Bạn là chuyên gia tối ưu hóa tìm kiếm.
Câu hỏi gốc không tìm được đủ thông tin. Hãy tạo câu hỏi mới, TỐT HƠN để tìm kiếm.

QUY TẮC:
- Câu hỏi mới phải đơn giản hơn, trực tiếp hơn
- Thử dùng từ khóa chuyên môn khác
- Thử rút gọn câu hỏi về khái niệm cốt lõi
- CHỈ trả lời câu hỏi mới, không giải thích"""

            user_prompt = f"""Câu hỏi gốc: "{original_query}"
Lần thử: {attempt}{found_topics}

Câu hỏi cải thiện:"""

            provider, model = model_manager.get_model("direct_chat", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.5,
                max_tokens=100
            )

            corrected = response.strip()
            if corrected and corrected != original_query:
                logger.info(f"🔧 Corrective query (attempt {attempt}): '{corrected}'")
                return corrected
            return None

        except Exception as e:
            logger.warning(f"⚠️ Corrective query generation failed: {e}")
            return None

    def synthesize_multi_hop(
        self,
        original_query: str,
        sub_answers: List[Dict[str, Any]]
    ) -> str:
        """
        Synthesize answers from multiple sub-queries into a final answer.

        Args:
            original_query: The original complex query
            sub_answers: List of {"sub_query": ..., "contexts": [...], "answer": ...}

        Returns:
            Synthesized final answer
        """
        if not sub_answers:
            return ""

        if len(sub_answers) == 1:
            return sub_answers[0].get("answer", "")

        # Build synthesis prompt
        sub_answers_text = ""
        for i, sa in enumerate(sub_answers):
            sub_q = sa.get("sub_query", "")
            answer = sa.get("answer", "")[:500]  # Limit each answer
            sub_answers_text += f"\n**Câu hỏi con {i+1}**: {sub_q}\n**Câu trả lời**: {answer}\n"

        system_prompt = """Bạn là chuyên gia tổng hợp thông tin học thuật.
Nhiệm vụ: Tổng hợp các câu trả lời riêng lẻ thành 1 câu trả lời hoàn chỉnh, mạch lạc cho câu hỏi gốc.

YÊU CẦU:
- Câu trả lời phải liền mạch, không phải danh sách rời rạc
- Kết nối thông tin từ các phần lại với nhau
- Tập trung vào câu hỏi GỐC
- Dùng markdown để cấu trúc nếu cần"""

        user_prompt = f"""Câu hỏi gốc: "{original_query}"

Các câu trả lời thành phần:
{sub_answers_text}

Câu trả lời tổng hợp:"""

        try:
            provider, model = model_manager.get_model("rag_query", "medium")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.3,
                max_tokens=1500
            )
            logger.info("🔗 Multi-hop synthesis complete")
            return response.strip()

        except Exception as e:
            logger.error(f"❌ Multi-hop synthesis failed: {e}")
            # Fallback: concatenate answers
            return "\n\n".join(
                f"**{sa.get('sub_query', '')}**\n{sa.get('answer', '')}"
                for sa in sub_answers
            )

    def should_use_multi_hop(self, query: str, complexity: str) -> bool:
        """
        Determine if a query should use multi-hop reasoning.
        """
        if not settings.ENABLE_MULTI_HOP:
            return False

        if complexity != "complex":
            return False

        # Additional heuristics for multi-hop
        multi_hop_indicators = [
            "so sánh", "compare", "khác nhau", "difference",
            "và", " and ", "cả hai", "both",
            "trước và sau", "before and after",
            "ưu và nhược", "pros and cons"
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in multi_hop_indicators)


# Global singleton
corrective_rag = CorrectiveRAG()
