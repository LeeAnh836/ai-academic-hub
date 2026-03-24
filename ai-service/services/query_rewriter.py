"""
Query Rewriter Service
Advanced RAG - Query Expansion/Rewriting

Techniques:
1. Multi-Query: Generate multiple alternative phrasings of the query
2. Step-Back: Generate a broader/more general version to capture context
3. HyDE: Generate a hypothetical answer to improve semantic similarity

These expanded queries improve retrieval recall by capturing more semantically
related chunks that a single query might miss.
"""
from typing import List, Optional
import logging

from core.model_manager import model_manager
from core.llm_cache import llm_cache

logger = logging.getLogger(__name__)


class QueryRewriter:
    """
    LLM-based query expansion and rewriting for Advanced RAG.

    Workflow:
    - Multi-Query: generate N alternative phrasings → search each → merge unique results
    - Step-Back: create a broader generalization → retrieve background context
    - HyDE: imagine an ideal answer passage → embed that for retrieval
    """

    def generate_multi_queries(
        self,
        query: str,
        num_variants: int = 3
    ) -> List[str]:
        """
        Generate multiple alternative phrasings of the original query.
        Returns the original query plus N variants.
        """
        try:
            cache_key = llm_cache.build_key(
                "query_rewrite_multi_v1",
                {"query": query.strip().lower(), "num_variants": num_variants},
            )
            cached = llm_cache.get(cache_key)
            if isinstance(cached, list) and cached:
                return cached

            system_prompt = """Bạn là chuyên gia tối ưu hóa truy vấn tìm kiếm.
Nhiệm vụ: Tạo ra các phiên bản khác nhau của câu hỏi người dùng để cải thiện tìm kiếm tài liệu.

QUY TẮC:
- Giữ nguyên ý nghĩa gốc nhưng dùng từ ngữ/cấu trúc khác
- Thử cả tiếng Việt và tiếng Anh nếu phù hợp
- Mỗi variant trên 1 dòng riêng
- KHÔNG thêm số thứ tự hay giải thích
- KHÔNG thay đổi chủ đề hay thêm thông tin mới

VÍ DỤ:
Query gốc: "RAG là gì?"
Output:
Retrieval Augmented Generation là gì?
RAG hoạt động như thế nào?
Phương pháp RAG trong AI là gì?"""

            user_prompt = f"""Tạo {num_variants} phiên bản khác nhau của câu hỏi sau:
"{query}"

Chỉ trả lời các phiên bản, mỗi phiên bản trên 1 dòng:"""

            provider, model = model_manager.get_model("query_rewrite", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.7,
                max_tokens=200
            )

            # Parse variants from response
            variants = [
                line.strip()
                for line in response.strip().splitlines()
                if line.strip() and line.strip() != query
            ][:num_variants]

            # Always include the original query first
            all_queries = [query] + variants
            llm_cache.set(cache_key, all_queries)
            logger.info(f"🔄 Query expansion: {len(all_queries)} variants generated")
            return all_queries

        except Exception as e:
            logger.warning(f"⚠️ Query rewrite failed: {e}, using original only")
            return [query]

    def generate_step_back_query(self, query: str) -> Optional[str]:
        """
        Generate a broader/more general version of the query (Step-Back Prompting).
        This helps retrieve foundational/background context.
        """
        try:
            cache_key = llm_cache.build_key(
                "query_rewrite_step_back_v1",
                {"query": query.strip().lower()},
            )
            cached = llm_cache.get(cache_key)
            if isinstance(cached, str) and cached:
                return cached

            system_prompt = """Bạn là chuyên gia tóm tắt câu hỏi.
Nhiệm vụ: Tạo một câu hỏi TỔNG QUÁT HƠN từ câu hỏi cụ thể, để tìm kiếm nền tảng kiến thức liên quan.

QUY TẮC:
- Câu hỏi mới nên rộng hơn, bao quát hơn chủ đề gốc
- Vẫn giữ chủ đề chính, nhưng bỏ chi tiết cụ thể
- Chỉ trả lời 1 câu hỏi duy nhất

VÍ DỤ:
"RAG sử dụng Qdrant như thế nào?" → "RAG (Retrieval Augmented Generation) là gì và hoạt động như thế nào?"
"Hàm sigmoid trong neural network" → "Các hàm kích hoạt trong neural network là gì?"

QUAN TRỌNG: Chỉ trả lời câu hỏi tổng quát, không giải thích."""

            user_prompt = f"""Câu hỏi gốc: "{query}"
Câu hỏi tổng quát hơn:"""

            provider, model = model_manager.get_model("query_rewrite", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.3,
                max_tokens=100
            )

            step_back = response.strip()
            if step_back and step_back != query:
                llm_cache.set(cache_key, step_back)
                logger.info(f"⬆️ Step-back query: '{step_back}'")
                return step_back
            return None

        except Exception as e:
            logger.warning(f"⚠️ Step-back generation failed: {e}")
            return None

    def generate_hyde_passage(self, query: str) -> Optional[str]:
        """
        HyDE (Hypothetical Document Embeddings):
        Generate a hypothetical answer passage to improve semantic matching.
        """
        try:
            cache_key = llm_cache.build_key(
                "query_rewrite_hyde_v1",
                {"query": query.strip().lower()},
            )
            cached = llm_cache.get(cache_key)
            if isinstance(cached, str) and cached:
                return cached

            system_prompt = """Bạn là chuyên gia học thuật. Viết một đoạn văn ngắn như thể nó xuất hiện trong một tài liệu học thuật trả lời câu hỏi dưới đây.
Đoạn văn nên:
- Khoảng 80-120 từ
- Ngôn ngữ học thuật, chính xác
- Trực tiếp trả lời câu hỏi
- KHÔNG đề cập "theo tài liệu" hay "câu hỏi hỏi về"
- Viết như nội dung tài liệu thực"""

            user_prompt = f"""Câu hỏi: {query}

Đoạn văn tài liệu:"""

            provider, model = model_manager.get_model("query_rewrite", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.5,
                max_tokens=200
            )

            hyde_passage = response.strip()
            if hyde_passage:
                llm_cache.set(cache_key, hyde_passage)
                logger.info(f"📄 HyDE passage generated ({len(hyde_passage)} chars)")
                return hyde_passage
            return None

        except Exception as e:
            logger.warning(f"⚠️ HyDE generation failed: {e}")
            return None

    def decompose_complex_query(self, query: str) -> List[str]:
        """
        Multi-hop Reasoning: Decompose a complex question into simpler sub-questions.
        Each sub-question can be answered independently, then synthesized.
        """
        try:
            cache_key = llm_cache.build_key(
                "query_rewrite_decompose_v1",
                {"query": query.strip().lower()},
            )
            cached = llm_cache.get(cache_key)
            if isinstance(cached, list) and cached:
                return cached

            system_prompt = """Bạn là chuyên gia phân tích câu hỏi.
Nhiệm vụ: Phân tích câu hỏi PHỨC TẠP thành 2-4 câu hỏi CON đơn giản hơn.

QUY TẮC:
- Chỉ phân tách nếu câu hỏi thực sự phức tạp (so sánh nhiều thứ, hỏi nhiều khía cạnh)
- Nếu câu hỏi đã đơn giản, chỉ trả lời: "SIMPLE"
- Mỗi câu con trên 1 dòng
- Các câu con phải có thể trả lời độc lập

VÍ DỤ:
"So sánh RAG và Fine-tuning về hiệu suất và chi phí" →
RAG là gì và hoạt động thế nào?
Fine-tuning là gì và hoạt động thế nào?
Ưu nhược điểm của RAG so với Fine-tuning về hiệu suất?
Ưu nhược điểm của RAG so với Fine-tuning về chi phí?

QUAN TRỌNG: Chỉ trả lời các câu hỏi con, không giải thích."""

            user_prompt = f"""Câu hỏi: "{query}"
Phân tích:"""

            provider, model = model_manager.get_model("query_rewrite", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.2,
                max_tokens=200
            )

            response_clean = response.strip()

            # If LLM says it's simple, return original as-is
            if "SIMPLE" in response_clean.upper():
                llm_cache.set(cache_key, [query])
                return [query]

            sub_queries = [
                line.strip()
                for line in response_clean.splitlines()
                if line.strip() and len(line.strip()) > 10
            ]

            if len(sub_queries) >= 2:
                llm_cache.set(cache_key, sub_queries)
                logger.info(f"🔀 Decomposed into {len(sub_queries)} sub-queries")
                return sub_queries

            llm_cache.set(cache_key, [query])
            return [query]

        except Exception as e:
            logger.warning(f"⚠️ Query decomposition failed: {e}")
            return [query]


# Global singleton
query_rewriter = QueryRewriter()
