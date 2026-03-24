"""
Reranker Service
Advanced RAG - Cross-Encoder Re-ranking

After initial retrieval (vector search), re-rank the top-K candidates
to select the most relevant passages before passing them to the LLM.

Strategy:
1. Cohere Rerank API (multilingual, best quality)
2. LLM-based relevance scoring (fallback if Cohere unavailable)
"""
from typing import List, Dict, Any, Optional
import logging

import cohere
from core.config import settings
from core.model_manager import model_manager

logger = logging.getLogger(__name__)


class Reranker:
    """
    Re-ranks retrieved contexts to select the most relevant ones.

    Uses Cohere Rerank as primary method (same API key as embeddings),
    falls back to LLM-based scoring.
    """

    def __init__(self):
        self.cohere_client = cohere.Client(settings.COHERE_API_KEY)
        self.rerank_model = settings.COHERE_RERANK_MODEL

    def rerank(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Re-rank contexts by relevance to the query.

        Args:
            query: The user query
            contexts: List of context dicts with at least "chunk_text"
            top_n: Number of top results to keep (defaults to settings.ADVANCED_RAG_FINAL_TOP_K)

        Returns:
            Re-ranked and filtered list of context dicts
        """
        if not contexts:
            return contexts

        top_n = top_n or settings.ADVANCED_RAG_FINAL_TOP_K

        # Try Cohere Rerank first
        if settings.ENABLE_COHERE_RERANK:
            try:
                return self._cohere_rerank(query, contexts, top_n)
            except Exception as e:
                logger.warning(f"⚠️ Cohere rerank failed: {e}, falling back to LLM rerank")

        # Fallback: LLM-based scoring
        return self._llm_rerank(query, contexts, top_n)

    def _cohere_rerank(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """
        Use Cohere Rerank API for cross-encoder scoring.
        """
        documents = [ctx.get("chunk_text", "") for ctx in contexts]

        # Filter empty documents
        valid_indices = [i for i, doc in enumerate(documents) if doc.strip()]
        valid_documents = [documents[i] for i in valid_indices]
        valid_contexts = [contexts[i] for i in valid_indices]

        if not valid_documents:
            return contexts[:top_n]

        response = self.cohere_client.rerank(
            model=self.rerank_model,
            query=query,
            documents=valid_documents,
            top_n=min(top_n, len(valid_documents))
        )

        # Build reranked list preserving original context dicts
        reranked = []
        for result in response.results:
            ctx = valid_contexts[result.index].copy()
            ctx["rerank_score"] = result.relevance_score
            ctx["original_score"] = ctx.get("score", 0.0)
            # Use rerank score as the primary score
            ctx["score"] = result.relevance_score
            reranked.append(ctx)

        top_score = f"{reranked[0]['rerank_score']:.3f}" if reranked else "N/A"
        logger.info(
            f"📊 Cohere rerank: {len(contexts)} → {len(reranked)} contexts "
            f"(top score: {top_score})"
        )
        return reranked

    def _llm_rerank(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback: use LLM to score and re-rank contexts.
        Scores each context 0-10 for relevance to query.
        """
        if len(contexts) <= top_n:
            return contexts

        # Build a combined prompt for batch scoring (more efficient)
        docs_text = ""
        for i, ctx in enumerate(contexts):
            text = ctx.get("chunk_text", "")[:500]  # Limit per chunk
            docs_text += f"\n[Đoạn {i+1}]: {text}\n"

        system_prompt = """Bạn là chuyên gia đánh giá độ liên quan.
Cho câu hỏi và các đoạn văn bản, hãy chấm điểm liên quan của TỪNG đoạn từ 0-10.

QUY TẮC:
- 10: Đoạn văn trả lời TRỰC TIẾP câu hỏi
- 7-9: Đoạn văn CÓ LIÊN QUAN, chứa thông tin hữu ích
- 4-6: Đoạn văn CÓ THỂ liên quan một phần
- 0-3: Đoạn văn KHÔNG liên quan

Định dạng: Chỉ trả lời các số điểm, mỗi điểm trên 1 dòng theo thứ tự đoạn văn.
Ví dụ:
8
3
9
5"""

        user_prompt = f"""Câu hỏi: "{query}"

Các đoạn văn bản:
{docs_text}

Điểm liên quan (0-10) cho từng đoạn:"""

        try:
            provider, model = model_manager.get_model("rerank", "low")
            response = model_manager.generate_text(
                provider_name=provider,
                model_identifier=model,
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.0,
                max_tokens=50
            )

            # Parse scores
            score_lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
            scores = []
            for line in score_lines:
                try:
                    score = float(line.split()[0]) / 10.0  # Normalize to 0-1
                    scores.append(score)
                except (ValueError, IndexError):
                    scores.append(0.5)  # Default

            # Pad scores if needed
            while len(scores) < len(contexts):
                scores.append(0.5)

            # Attach scores and sort
            scored_contexts = []
            for ctx, score in zip(contexts, scores):
                ctx_copy = ctx.copy()
                ctx_copy["rerank_score"] = score
                ctx_copy["original_score"] = ctx_copy.get("score", 0.0)
                ctx_copy["score"] = score
                scored_contexts.append(ctx_copy)

            scored_contexts.sort(key=lambda x: x["rerank_score"], reverse=True)
            reranked = scored_contexts[:top_n]

            logger.info(f"🤖 LLM rerank: {len(contexts)} → {len(reranked)} contexts")
            return reranked

        except Exception as e:
            logger.warning(f"⚠️ LLM rerank failed: {e}, returning original order")
            return contexts[:top_n]

    def filter_irrelevant(
        self,
        contexts: List[Dict[str, Any]],
        min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Filter out contexts below a minimum relevance score.
        Used after re-ranking to remove clearly irrelevant passages.
        """
        filtered = [ctx for ctx in contexts if ctx.get("score", 0) >= min_score]
        if len(filtered) < len(contexts):
            logger.info(f"🗑️ Filtered {len(contexts) - len(filtered)} low-score contexts")
        return filtered if filtered else contexts  # Don't return empty if all fail threshold


# Global singleton
reranker = Reranker()
