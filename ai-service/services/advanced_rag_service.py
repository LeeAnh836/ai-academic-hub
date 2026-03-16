"""
Advanced RAG Service
Full Advanced RAG pipeline integrating:

1. Query Routing (via Intent Classifier - existing)
2. Query Expansion/Rewriting (QueryRewriter)
3. Hybrid Search: Multi-query Vector + BM25 keyword scoring
4. Re-ranking (Cohere Rerank or LLM fallback)
5. Corrective RAG (CRAG): Quality evaluation + corrective re-retrieval
6. Multi-hop Reasoning: Decompose → answer sub-queries → synthesize

This service replaces direct vector search in DocumentQAAgent when
ENABLE_ADVANCED_RAG=True.
"""
from typing import List, Dict, Any, Optional, Tuple
import logging
import time

from core.config import settings
from core.qdrant import qdrant_manager
from services.embedding_service import embedding_service
from services.query_rewriter import query_rewriter
from services.reranker import reranker
from services.corrective_rag import corrective_rag
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

logger = logging.getLogger(__name__)


class AdvancedRAGService:
    """
    Advanced RAG pipeline orchestrating:
    - Multi-query expansion
    - BM25 keyword re-scoring
    - Cross-encoder re-ranking
    - CRAG self-correction
    - Multi-hop reasoning for complex queries
    """

    def __init__(self):
        self.query_rewriter = query_rewriter
        self.reranker = reranker
        self.corrective_rag = corrective_rag

    async def retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float,
        complexity: str = "moderate"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute the full Advanced RAG retrieval pipeline.

        Returns:
            Tuple of (contexts, pipeline_metadata)
        """
        start_time = time.time()
        pipeline_meta = {
            "pipeline": "advanced_rag",
            "stages": [],
            "query_variants": [],
            "crag_quality": None,
            "crag_attempts": 0,
            "reranked": False
        }

        # ─── Stage 1: Query Rewriting ────────────────────────────────────
        if settings.ENABLE_QUERY_REWRITING:
            all_queries = self.query_rewriter.generate_multi_queries(
                query,
                num_variants=settings.QUERY_REWRITE_VARIANTS
            )

            # Add step-back query for complex queries
            if complexity in ("moderate", "complex"):
                step_back = self.query_rewriter.generate_step_back_query(query)
                if step_back and step_back not in all_queries:
                    all_queries.append(step_back)

            pipeline_meta["query_variants"] = all_queries
            pipeline_meta["stages"].append("query_rewriting")
        else:
            all_queries = [query]

        logger.info(f"🔄 Queries to search: {len(all_queries)}")

        # ─── Stage 2: Multi-Query Vector Retrieval ────────────────────────
        # Fetch more results initially (will be re-ranked down to top_k)
        initial_top_k = settings.ADVANCED_RAG_INITIAL_TOP_K
        raw_contexts = await self._multi_query_retrieve(
            queries=all_queries,
            user_id=user_id,
            document_ids=document_ids,
            top_k=initial_top_k,
            score_threshold=score_threshold
        )
        pipeline_meta["stages"].append("multi_query_retrieval")
        logger.info(f"📥 Multi-query retrieval: {len(raw_contexts)} unique contexts")

        # ─── Stage 3: BM25 Keyword Re-scoring ─────────────────────────────
        if settings.ENABLE_BM25_RESCORING and raw_contexts:
            raw_contexts = self._bm25_rescore(query, raw_contexts)
            pipeline_meta["stages"].append("bm25_rescoring")

        # ─── Stage 4: Re-ranking ──────────────────────────────────────────
        if settings.ENABLE_RERANKING and len(raw_contexts) > settings.ADVANCED_RAG_FINAL_TOP_K:
            reranked_contexts = self.reranker.rerank(
                query=query,
                contexts=raw_contexts,
                top_n=settings.ADVANCED_RAG_FINAL_TOP_K
            )
            pipeline_meta["stages"].append("reranking")
            pipeline_meta["reranked"] = True
            logger.info(f"🏆 After reranking: {len(reranked_contexts)} contexts")
        else:
            reranked_contexts = raw_contexts[:settings.ADVANCED_RAG_FINAL_TOP_K]

        # ─── Stage 5: CRAG Quality Evaluation & Correction ───────────────
        if settings.ENABLE_CORRECTIVE_RAG and reranked_contexts:
            quality, confidence, reason = self.corrective_rag.evaluate_retrieval_quality(
                query=query,
                contexts=reranked_contexts
            )
            pipeline_meta["crag_quality"] = quality
            pipeline_meta["crag_confidence"] = confidence
            pipeline_meta["crag_reason"] = reason
            pipeline_meta["stages"].append("crag_evaluation")

            # If quality is insufficient, try corrective re-retrieval
            if quality == corrective_rag.QUALITY_INSUFFICIENT:
                corrected_contexts = await self._corrective_retrieve(
                    original_query=query,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    failed_contexts=reranked_contexts,
                    pipeline_meta=pipeline_meta
                )
                if corrected_contexts:
                    reranked_contexts = corrected_contexts
                    pipeline_meta["stages"].append("crag_correction")

        elapsed = time.time() - start_time
        pipeline_meta["elapsed_seconds"] = round(elapsed, 2)

        logger.info(
            f"✅ Advanced RAG complete: {len(reranked_contexts)} contexts in {elapsed:.2f}s "
            f"| stages: {' → '.join(pipeline_meta['stages'])}"
        )

        return reranked_contexts, pipeline_meta

    async def retrieve_with_multihop(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Multi-hop retrieval: decompose complex query → answer each sub-query → synthesize.
        Returns contexts from all sub-queries merged and de-duplicated.
        """
        sub_queries = self.query_rewriter.decompose_complex_query(query)

        if len(sub_queries) <= 1:
            # Not complex enough for multi-hop, use regular advanced retrieval
            return await self.retrieve(
                query=query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=score_threshold,
                complexity="complex"
            )

        logger.info(f"🔀 Multi-hop: {len(sub_queries)} sub-queries")

        # Retrieve contexts for each sub-query
        all_contexts = []
        seen_ids = set()

        for sub_query in sub_queries:
            sub_contexts, _ = await self.retrieve(
                query=sub_query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=max(3, top_k // len(sub_queries)),
                score_threshold=score_threshold,
                complexity="simple"
            )
            for ctx in sub_contexts:
                ctx_id = ctx.get("chunk_id")
                if ctx_id not in seen_ids:
                    ctx["sub_query"] = sub_query
                    all_contexts.append(ctx)
                    seen_ids.add(ctx_id)

        pipeline_meta = {
            "pipeline": "multi_hop_rag",
            "sub_queries": sub_queries,
            "total_contexts": len(all_contexts)
        }

        # Final re-ranking of merged contexts
        if settings.ENABLE_RERANKING and len(all_contexts) > top_k:
            all_contexts = self.reranker.rerank(
                query=query,
                contexts=all_contexts,
                top_n=top_k
            )

        return all_contexts[:top_k], pipeline_meta

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _multi_query_retrieve(
        self,
        queries: List[str],
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Execute vector retrieval for multiple query variants.
        Merge and de-duplicate results, keeping highest score per chunk.
        """
        seen_ids: Dict[str, Dict] = {}

        for q in queries:
            try:
                results = await self._vector_retrieve(
                    query=q,
                    user_id=user_id,
                    document_ids=document_ids,
                    top_k=top_k,
                    score_threshold=score_threshold
                )
                for ctx in results:
                    chunk_id = ctx.get("chunk_id")
                    if chunk_id not in seen_ids or ctx["score"] > seen_ids[chunk_id]["score"]:
                        seen_ids[chunk_id] = ctx
            except Exception as e:
                logger.warning(f"⚠️ Retrieval failed for query '{q[:50]}': {e}")

        # Sort by score descending
        merged = sorted(seen_ids.values(), key=lambda x: x["score"], reverse=True)
        return merged

    async def _vector_retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Core vector retrieval from Qdrant.
        """
        try:
            query_vector = embedding_service.embed_query(query)

            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]

            if document_ids:
                filter_conditions.append(
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids))
                )
            else:
                # No document filter - skip if no docs selected (security)
                return []

            query_filter = Filter(must=filter_conditions)

            search_results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )

            # Fallback with lower threshold
            if len(search_results) < max(2, top_k // 2) and settings.RAG_ENABLE_FALLBACK:
                min_threshold = settings.RAG_MIN_SCORE_THRESHOLD
                if score_threshold > min_threshold:
                    search_results = qdrant_manager.client.search(
                        collection_name=qdrant_manager.collection_name,
                        query_vector=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=min_threshold
                    )

            contexts = []
            for result in search_results:
                contexts.append({
                    "chunk_id": result.id,
                    "score": result.score,
                    "chunk_text": result.payload.get("chunk_text", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "document_id": result.payload.get("document_id", ""),
                    "file_name": result.payload.get("file_name", ""),
                    "title": result.payload.get("title", ""),
                    "source": "vector"
                })

            return contexts

        except Exception as e:
            logger.error(f"❌ Vector retrieve error: {e}")
            return []

    def _bm25_rescore(
        self,
        query: str,
        contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Re-score contexts using BM25 keyword matching and combine with vector score.
        This boosts exact keyword matches for domain-specific terms.

        Uses rank-bm25 library for efficient BM25 scoring.
        """
        try:
            from rank_bm25 import BM25Okapi

            # Tokenize corpus (simple whitespace + lower)
            corpus = [ctx.get("chunk_text", "").lower().split() for ctx in contexts]
            if not any(corpus):
                return contexts

            bm25 = BM25Okapi(corpus)
            query_tokens = query.lower().split()
            bm25_scores = bm25.get_scores(query_tokens)

            # Normalize BM25 scores to 0-1
            max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0

            # Combine: 70% vector score + 30% BM25 score
            vector_weight = settings.BM25_VECTOR_WEIGHT
            bm25_weight = 1.0 - vector_weight

            rescored = []
            for ctx, bm25_score in zip(contexts, bm25_scores):
                ctx_copy = ctx.copy()
                normalized_bm25 = bm25_score / max_bm25
                original_score = ctx_copy.get("score", 0.0)
                ctx_copy["vector_score"] = original_score
                ctx_copy["bm25_score"] = normalized_bm25
                ctx_copy["score"] = (vector_weight * original_score) + (bm25_weight * normalized_bm25)
                rescored.append(ctx_copy)

            rescored.sort(key=lambda x: x["score"], reverse=True)
            logger.info(f"📊 BM25 rescoring applied to {len(rescored)} contexts")
            return rescored

        except ImportError:
            logger.warning("⚠️ rank-bm25 not installed, skipping BM25 rescoring")
            return contexts
        except Exception as e:
            logger.warning(f"⚠️ BM25 rescoring failed: {e}")
            return contexts

    async def _corrective_retrieve(
        self,
        original_query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float,
        failed_contexts: List[Dict[str, Any]],
        pipeline_meta: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Corrective re-retrieval when initial results are insufficient.
        Tries a refined query with lower threshold.
        """
        max_attempts = settings.CRAG_MAX_ATTEMPTS
        best_contexts = failed_contexts

        for attempt in range(1, max_attempts + 1):
            corrected_query = self.corrective_rag.generate_corrective_query(
                original_query=original_query,
                failed_contexts=failed_contexts,
                attempt=attempt
            )

            if not corrected_query:
                break

            # Lower threshold for corrective search
            new_threshold = max(
                settings.RAG_MIN_SCORE_THRESHOLD,
                score_threshold - (0.1 * attempt)
            )

            logger.info(f"🔧 Corrective attempt {attempt}: '{corrected_query}' (threshold: {new_threshold})")
            pipeline_meta["crag_attempts"] = attempt

            new_contexts = await self._vector_retrieve(
                query=corrected_query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                score_threshold=new_threshold
            )

            if new_contexts:
                # Re-evaluate quality
                quality, confidence, _ = self.corrective_rag.evaluate_retrieval_quality(
                    query=original_query,
                    contexts=new_contexts
                )
                pipeline_meta["crag_quality"] = quality

                if quality != corrective_rag.QUALITY_INSUFFICIENT:
                    logger.info(f"✅ Corrective retrieval succeeded (attempt {attempt}): {quality}")
                    best_contexts = new_contexts
                    break

        return best_contexts


# Global singleton
advanced_rag_service = AdvancedRAGService()
