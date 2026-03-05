"""
GraphRAG Service
Xử lý knowledge graph construction và retrieval từ Neo4j

Features:
- Entity extraction using Gemini Flash (FREE tier)
- Knowledge graph building
- Graph-based retrieval
- Relationship traversal
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from langchain.schema import Document as LangchainDocument

from core.config import settings
from core.neo4j_manager import neo4j_manager
from core.model_manager import model_manager


class GraphRAGService:
    """Service xử lý GraphRAG với Neo4j"""
    
    def __init__(self):
        """Initialize GraphRAG service"""
        self.neo4j = neo4j_manager
        self.model_manager = model_manager
    
    # ============================================
    # INDEXING: Build Knowledge Graph
    # ============================================
    
    async def index_document_to_graph(
        self,
        document_id: str,
        user_id: str,
        chunks: List[LangchainDocument],
        file_name: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Index document into knowledge graph
        
        Process:
        1. Create Document node
        2. Create Chunk nodes
        3. Extract entities from each chunk using Gemini Flash
        4. Create Entity & Concept nodes
        5. Create relationships
        
        Args:
            document_id: Document UUID
            user_id: User UUID
            chunks: List of text chunks
            file_name: File name
            metadata: Document metadata
        
        Returns:
            Dict with statistics
        """
        if not self.neo4j.enabled:
            raise Exception("Neo4j is not enabled. Set ENABLE_NEO4J=true in .env")
        
        try:
            # 1. Create Document node
            self._create_document_node(
                document_id=document_id,
                user_id=user_id,
                file_name=file_name,
                metadata=metadata
            )
            
            total_entities = 0
            total_relationships = 0
            
            # 2. Process each chunk
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{document_id}_chunk_{idx}"
                chunk_text = chunk.page_content
                
                # Create Chunk node
                self._create_chunk_node(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_index=idx,
                    chunk_text=chunk_text
                )
                
                # Extract entities using Gemini Flash (FREE)
                entities, relationships = await self._extract_entities_and_relations(
                    text=chunk_text,
                    chunk_id=chunk_id
                )
                
                # Create Entity nodes and relationships
                if entities:
                    self._create_entities_and_relationships(
                        chunk_id=chunk_id,
                        entities=entities,
                        relationships=relationships
                    )
                    
                    total_entities += len(entities)
                    total_relationships += len(relationships)
                
                print(f"✅ Chunk {idx+1}/{len(chunks)}: {len(entities)} entities, {len(relationships)} relationships")
            
            # 3. Build document-level connections
            self._build_document_connections(document_id)
            
            return {
                "success": True,
                "document_id": document_id,
                "chunks_processed": len(chunks),
                "entities_extracted": total_entities,
                "relationships_created": total_relationships
            }
        
        except Exception as e:
            print(f"❌ Graph indexing error: {e}")
            raise Exception(f"Failed to index document to graph: {e}")
    
    def _create_document_node(
        self,
        document_id: str,
        user_id: str,
        file_name: str,
        metadata: Dict[str, Any]
    ):
        """Create Document node in Neo4j"""
        query = """
        MERGE (d:Document {id: $document_id})
        SET d.user_id = $user_id,
            d.file_name = $file_name,
            d.title = $title,
            d.category = $category,
            d.created_at = datetime()
        RETURN d
        """
        
        self.neo4j.execute_write(query, {
            "document_id": document_id,
            "user_id": user_id,
            "file_name": file_name,
            "title": metadata.get("title", file_name),
            "category": metadata.get("category", "general")
        })
    
    def _create_chunk_node(
        self,
        chunk_id: str,
        document_id: str,
        chunk_index: int,
        chunk_text: str
    ):
        """Create Chunk node and link to Document"""
        query = """
        MATCH (d:Document {id: $document_id})
        MERGE (c:Chunk {id: $chunk_id})
        SET c.document_id = $document_id,
            c.index = $chunk_index,
            c.text = $chunk_text
        MERGE (d)-[:CONTAINS]->(c)
        RETURN c
        """
        
        self.neo4j.execute_write(query, {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text[:1000]  # Limit text size in graph
        })
    
    async def _extract_entities_and_relations(
        self,
        text: str,
        chunk_id: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Extract entities and relationships using Gemini Flash
        
        Uses structured prompt to extract:
        - Entities (name, type: PERSON, ORGANIZATION, CONCEPT, TECHNOLOGY, etc.)
        - Relationships (source, relation, target)
        
        Args:
            text: Chunk text
            chunk_id: Chunk ID for reference
        
        Returns:
            Tuple of (entities list, relationships list)
        """
        try:
            # Get Gemini Flash model for cheap extraction
            provider_name, model_object = self.model_manager.get_model(
                task_type="entity_extraction",
                complexity="low"
            )
            
            # System instruction for entity extraction
            system_instruction = """Bạn là chuyên gia trích xuất thông tin từ văn bản học thuật.

NHIỆM VỤ: Trích xuất các thực thể (entities) và mối quan hệ (relationships) từ văn bản.

LOẠI THỰC THỂ:
- PERSON: Tên người (tác giả, nhà khoa học, lập trình viên)
- ORGANIZATION: Tổ chức, công ty, trường học
- TECHNOLOGY: Công nghệ, framework, tool, ngôn ngữ lập trình
- CONCEPT: Khái niệm, lý thuyết, phương pháp
- PRODUCT: Sản phẩm, dịch vụ
- EVENT: Sự kiện, phiên bản, release

LOẠI QUAN HỆ:
- USES: A sử dụng B
- PART_OF: A là một phần của B
- RELATES_TO: A liên quan đến B
- IMPLEMENTS: A triển khai B
- DEPENDS_ON: A phụ thuộc vào B
- CREATED_BY: A được tạo bởi B

OUTPUT FORMAT (JSON):
{
  "entities": [
    {"name": "Docker", "type": "TECHNOLOGY"},
    {"name": "Container", "type": "CONCEPT"}
  ],
  "relationships": [
    {"source": "Docker", "relation": "IMPLEMENTS", "target": "Container"}
  ]
}

CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH THÊM."""
            
            # Build prompt
            prompt = f"""Trích xuất entities và relationships từ văn bản sau:

VĂNBẢN:
{text[:2000]}

TRẢ VỀ JSON:"""
            
            # Generate extraction
            response = self.model_manager.generate_text(
                provider_name=provider_name,
                model_identifier=model_object,
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000
            )
            
            # Parse JSON response
            entities, relationships = self._parse_extraction_response(response)
            
            # Limit entities to prevent graph explosion
            if len(entities) > settings.GRAPH_MAX_ENTITIES:
                entities = entities[:settings.GRAPH_MAX_ENTITIES]
            
            return entities, relationships
        
        except Exception as e:
            print(f"⚠️ Entity extraction error: {e}")
            # Return empty on error (don't fail entire indexing)
            return [], []
    
    def _parse_extraction_response(self, response: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse JSON response from LLM"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                entities = data.get("entities", [])
                relationships = data.get("relationships", [])
                return entities, relationships
            else:
                return [], []
        
        except json.JSONDecodeError:
            print("⚠️ Failed to parse extraction JSON")
            return [], []
    
    def _create_entities_and_relationships(
        self,
        chunk_id: str,
        entities: List[Dict],
        relationships: List[Dict]
    ):
        """Create Entity nodes and relationships in graph"""
        try:
            # Create entities
            for entity in entities:
                entity_name = entity.get("name", "").strip()
                entity_type = entity.get("type", "CONCEPT").upper()
                
                if not entity_name:
                    continue
                
                # Create Entity node and link to Chunk
                query = """
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (e:Entity {name: $name, type: $type})
                MERGE (c)-[:MENTIONS]->(e)
                RETURN e
                """
                
                self.neo4j.execute_write(query, {
                    "chunk_id": chunk_id,
                    "name": entity_name,
                    "type": entity_type
                })
            
            # Create relationships between entities
            for rel in relationships:
                source = rel.get("source", "").strip()
                relation = rel.get("relation", "RELATES_TO").upper()
                target = rel.get("target", "").strip()
                
                if not source or not target:
                    continue
                
                query = f"""
                MATCH (e1:Entity {{name: $source}})
                MATCH (e2:Entity {{name: $target}})
                MERGE (e1)-[r:{relation}]->(e2)
                RETURN r
                """
                
                self.neo4j.execute_write(query, {
                    "source": source,
                    "target": target
                })
        
        except Exception as e:
            print(f"⚠️ Entity creation error: {e}")
    
    def _build_document_connections(self, document_id: str):
        """Build higher-level connections within document"""
        try:
            # Connect entities mentioned in multiple chunks
            query = """
            MATCH (d:Document {id: $document_id})-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            WITH e, count(c) as mention_count
            WHERE mention_count > 1
            SET e.importance = mention_count
            """
            
            self.neo4j.execute_write(query, {"document_id": document_id})
        
        except Exception as e:
            print(f"⚠️ Document connection error: {e}")
    
    # ============================================
    # RETRIEVAL: Query Knowledge Graph
    # ============================================
    
    def retrieve_graph_context(
        self,
        query: str,
        user_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 10,
        traversal_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context from knowledge graph
        
        Strategy:
        1. Extract key entities from query
        2. Find matching entities in graph
        3. Traverse relationships to find related entities
        4. Return entity neighborhoods as context
        
        Args:
            query: User query
            user_id: User ID for filtering
            document_ids: Optional document filter
            top_k: Max entities to return
            traversal_depth: Relationship traversal depth
        
        Returns:
            List of context dicts with entities and relationships
        """
        if not self.neo4j.enabled:
            return []
        
        try:
            # Extract entities from query (simple keyword matching)
            query_entities = self._extract_query_entities(query)
            
            if not query_entities:
                # Fallback: return important entities from user's documents
                return self._get_important_entities(user_id, document_ids, top_k)
            
            # Find matching entities and traverse
            contexts = []
            
            for entity_name in query_entities[:5]:  # Limit to 5 query entities
                # Cypher query to find entity and its neighborhood
                cypher = f"""
                MATCH (d:Document {{user_id: $user_id}})-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($entity_name)
                """ + (
                    " AND d.id IN $document_ids" if document_ids else ""
                ) + f"""
                OPTIONAL MATCH (e)-[r*1..{traversal_depth}]-(related:Entity)
                RETURN e.name as entity, e.type as type, 
                       c.text as context,
                       collect(DISTINCT related.name)[0..5] as related_entities,
                       collect(DISTINCT type(r[0]))[0..5] as relationships
                LIMIT $limit
                """
                
                params = {
                    "user_id": user_id,
                    "entity_name": entity_name,
                    "limit": top_k
                }
                
                if document_ids:
                    params["document_ids"] = document_ids
                
                results = self.neo4j.execute_query(cypher, params)
                
                for result in results:
                    contexts.append({
                        "entity": result.get("entity"),
                        "type": result.get("type"),
                        "context": result.get("context", "")[:500],
                        "related_entities": result.get("related_entities", []),
                        "relationships": result.get("relationships", []),
                        "source": "graph"
                    })
            
            return contexts[:top_k]
        
        except Exception as e:
            print(f"⚠️ Graph retrieval error: {e}")
            return []
    
    def _extract_query_entities(self, query: str) -> List[str]:
        """Extract potential entities from query (simple approach)"""
        # Simple: extract capitalized words and technical terms
        words = query.split()
        entities = []
        
        for word in words:
            # Clean word
            word = re.sub(r'[^\w\s]', '', word)
            
            # Capitalized words or tech keywords
            if word and (word[0].isupper() or len(word) > 6):
                entities.append(word)
        
        return entities
    
    def _get_important_entities(
        self,
        user_id: str,
        document_ids: Optional[List[str]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get most important entities (mentioned most frequently)"""
        try:
            cypher = """
            MATCH (d:Document {user_id: $user_id})-[:CONTAINS]->(c:Chunk)-[:MENTIONS]->(e:Entity)
            """ + (
                "WHERE d.id IN $document_ids " if document_ids else ""
            )+ """
            WITH e, c, count(c) as mentions
            ORDER BY mentions DESC
            LIMIT $limit
            RETURN e.name as entity, e.type as type, c.text as context, mentions
            """
            
            params = {"user_id": user_id, "limit": limit}
            if document_ids:
                params["document_ids"] = document_ids
            
            results = self.neo4j.execute_query(cypher, params)
            
            return [
                {
                    "entity": r.get("entity"),
                    "type": r.get("type"),
                    "context": r.get("context", "")[:500],
                    "importance": r.get("mentions", 0),
                    "source": "graph"
                }
                for r in results
            ]
        
        except Exception as e:
            print(f"⚠️ Important entities error: {e}")
            return []
    
    # ============================================
    # UTILITIES
    # ============================================
    
    def delete_document_graph(self, document_id: str):
        """Delete document and all related graph data"""
        if not self.neo4j.enabled:
            return
        
        self.neo4j.clear_document(document_id)


# Global instance
graph_rag_service = GraphRAGService()
