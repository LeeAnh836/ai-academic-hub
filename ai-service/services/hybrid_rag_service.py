"""
Hybrid RAG Service
Kết hợp Vector RAG (Qdrant) và Graph RAG (Neo4j) để tăng cường retrieval

Strategy:
- Vector Search: Tìm semantic similarity (good for fuzzy matching)
- Graph Search: Tìm structured relationships (good for entity-centric queries)
- Hybrid: Combine & re-rank results
"""
from typing import List, Dict, Any, Optional
import time

from core.config import settings
from core.qdrant import qdrant_manager
from core.neo4j_manager import neo4j_manager
from services.embedding_service import embedding_service
from services.graph_rag_service import graph_rag_service
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny


class HybridRAGService:
    """
    Hybrid RAG combining Vector + Graph retrieval
    
    Modes:
    - vector_only: Only Qdrant (default if Neo4j disabled)
    - graph_only: Only Neo4j
    - hybrid: Combine both and merge results
    """
    
    def __init__(self):
        """Initialize hybrid service"""
        self.mode = settings.GRAPH_RAG_MODE
        self.graph_enabled = settings.ENABLE_GRAPH_RAG and neo4j_manager.enabled
    
    async def hybrid_retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining vector + graph
        
        Args:
            query: User query
            user_id: User ID for filtering
            document_ids: Optional document IDs
            top_k: Number of results
            score_threshold: Min similarity score
        
        Returns:
            List of context dicts with merged results
        """
        try:
            # Determine retrieval strategy based on mode and availability
            mode = self._determine_mode()
            
            print(f"🔍 Hybrid RAG Mode: {mode}")
            
            if mode == "vector_only":
                return await self._vector_retrieve(
                    query, user_id, document_ids, top_k, score_threshold
                )
            
            elif mode == "graph_only":
                return await self._graph_retrieve(
                    query, user_id, document_ids, top_k
                )
            
            else:  # hybrid mode
                return await self._hybrid_retrieve(
                    query, user_id, document_ids, top_k, score_threshold
                )
        
        except Exception as e:
            print(f"❌ Hybrid retrieve error: {e}")
            # Fallback to vector-only
            return await self._vector_retrieve(
                query, user_id, document_ids, top_k, score_threshold
            )
    
    def _determine_mode(self) -> str:
        """Determine which retrieval mode to use"""
        if not self.graph_enabled:
            return "vector_only"
        
        if self.mode == "graph_only":
            return "graph_only"
        
        if self.mode == "hybrid":
            return "hybrid"
        
        return "vector_only"
    
    # ============================================
    # Vector Retrieval (Qdrant)
    # ============================================
    
    async def _vector_retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """Vector-based retrieval from Qdrant"""
        try:
            # Generate query embedding
            query_vector = embedding_service.embed_query(query)
            
            # Build filter
            filter_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=user_id))
            ]
            
            if document_ids:
                filter_conditions.append(
                    FieldCondition(key="document_id", match=MatchAny(any=document_ids))
                )
            
            query_filter = Filter(must=filter_conditions)
            
            # Search in Qdrant
            search_results = qdrant_manager.client.search(
                collection_name=qdrant_manager.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Fallback with lower threshold if not enough results
            if len(search_results) < max(2, top_k // 2) and settings.RAG_ENABLE_FALLBACK:
                min_threshold = settings.RAG_MIN_SCORE_THRESHOLD
                if score_threshold > min_threshold:
                    print(f"⚠️ Fallback: {score_threshold} -> {min_threshold}")
                    search_results = qdrant_manager.client.search(
                        collection_name=qdrant_manager.collection_name,
                        query_vector=query_vector,
                        query_filter=query_filter,
                        limit=top_k,
                        score_threshold=min_threshold
                    )
            
            # Format results
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
            
            print(f"📊 Vector: {len(contexts)} results")
            return contexts
        
        except Exception as e:
            print(f"❌ Vector retrieve error: {e}")
            return []
    
    # ============================================
    # Graph Retrieval (Neo4j)
    # ============================================
    
    async def _graph_retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Graph-based retrieval from Neo4j"""
        try:
            graph_contexts = graph_rag_service.retrieve_graph_context(
                query=query,
                user_id=user_id,
                document_ids=document_ids,
                top_k=top_k,
                traversal_depth=settings.GRAPH_TRAVERSAL_DEPTH
            )
            
            # Format graph contexts to match vector context format
            contexts = []
            for idx, ctx in enumerate(graph_contexts):
                contexts.append({
                    "chunk_id": f"graph_{idx}",
                    "score": 1.0 - (idx * 0.1),  # Synthetic score (decreasing)
                    "chunk_text": self._format_graph_context(ctx),
                    "chunk_index": idx,
                    "document_id": "graph",
                    "file_name": "Knowledge Graph",
                    "title": ctx.get("entity", ""),
                    "source": "graph",
                    "entity": ctx.get("entity"),
                    "type": ctx.get("type"),
                    "related_entities": ctx.get("related_entities", [])
                })
            
            print(f"🕸️ Graph: {len(contexts)} results")
            return contexts
        
        except Exception as e:
            print(f"❌ Graph retrieve error: {e}")
            return []
    
    def _format_graph_context(self, graph_ctx: Dict[str, Any]) -> str:
        """Format graph context into readable text"""
        parts = []
        
        # Entity info
        entity = graph_ctx.get("entity", "")
        entity_type = graph_ctx.get("type", "")
        parts.append(f"**{entity}** ({entity_type})")
        
        # Context text
        context = graph_ctx.get("context", "")
        if context:
            parts.append(f"\n{context}")
        
        # Related entities
        related = graph_ctx.get("related_entities", [])
        if related:
            parts.append(f"\nLiên quan: {', '.join(related[:5])}")
        
        # Relationships
        relationships = graph_ctx.get("relationships", [])
        if relationships:
            parts.append(f"\nQuan hệ: {', '.join(set(relationships[:5]))}")
        
        return "\n".join(parts)
    
    # ============================================
    # Hybrid Retrieval (Combined)
    # ============================================
    
    async def _hybrid_retrieve(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]],
        top_k: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval: Combine vector + graph results
        
        Strategy:
        1. Get results from both sources
        2. Merge and deduplicate
        3. Re-rank based on combined score
        4. Return top-k
        """
        try:
            start_time = time.time()
            
            # 1. Get vector results (60% of top_k)
            vector_k = max(3, int(top_k * 0.6))
            vector_contexts = await self._vector_retrieve(
                query, user_id, document_ids, vector_k, score_threshold
            )
            
            # 2. Get graph results (40% of top_k)
            graph_k = max(2, int(top_k * 0.4))
            graph_contexts = await self._graph_retrieve(
                query, user_id, document_ids, graph_k
            )
            
            # 3. Merge results
            merged = self._merge_and_rerank(
                vector_contexts,
                graph_contexts,
                vector_weight=0.7,  # Favor vector results slightly
                graph_weight=0.3
            )
            
            # 4. Return top-k
            final_contexts = merged[:top_k]
            
            elapsed = time.time() - start_time
            print(f"🔀 Hybrid: {len(vector_contexts)}V + {len(graph_contexts)}G = {len(final_contexts)} results ({elapsed:.2f}s)")
            
            return final_contexts
        
        except Exception as e:
            print(f"❌ Hybrid merge error: {e}")
            # Fallback to vector only
            return await self._vector_retrieve(
                query, user_id, document_ids, top_k, score_threshold
            )
    
    def _merge_and_rerank(
        self,
        vector_contexts: List[Dict],
        graph_contexts: List[Dict],
        vector_weight: float = 0.7,
        graph_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Merge and re-rank contexts from both sources
        
        Scoring:
        - Vector contexts: Already have similarity scores
        - Graph contexts: Synthetic scores based on position
        - Combined: weighted average
        """
        all_contexts = []
        
        # Add vector contexts with weighted scores
        for ctx in vector_contexts:
            ctx_copy = ctx.copy()
            ctx_copy["final_score"] = ctx["score"] * vector_weight
            ctx_copy["vector_score"] = ctx["score"]
            ctx_copy["graph_score"] = 0.0
            all_contexts.append(ctx_copy)
        
        # Add graph contexts with weighted scores
        for ctx in graph_contexts:
            ctx_copy = ctx.copy()
            ctx_copy["final_score"] = ctx["score"] * graph_weight
            ctx_copy["vector_score"] = 0.0
            ctx_copy["graph_score"] = ctx["score"]
            all_contexts.append(ctx_copy)
        
        # Sort by final score
        all_contexts.sort(key=lambda x: x["final_score"], reverse=True)
        
        return all_contexts
    
    # ============================================
    # Context Formatting for LLM
    # ============================================
    
    def format_contexts_for_llm(
        self,
        contexts: List[Dict[str, Any]]
    ) -> str:
        """Format hybrid contexts for LLM prompt"""
        if not contexts:
            return ""
        
        formatted_parts = []
        
        for idx, ctx in enumerate(contexts):
            source = ctx.get("source", "vector")
            
            if source == "vector":
                # Vector context format
                formatted_parts.append(
                    f"[Tài liệu {idx+1} - {ctx.get('file_name', 'Unknown')}]\n"
                    f"{ctx.get('chunk_text', '')}"
                )
            
            else:  # graph context
                # Graph context format
                entity = ctx.get("entity", "")
                text = ctx.get("chunk_text", "")
                formatted_parts.append(
                    f"[Kiến thức {idx+1} - {entity}]\n"
                    f"{text}"
                )
        
        return "\n\n".join(formatted_parts)


# Global instance
hybrid_rag_service = HybridRAGService()
