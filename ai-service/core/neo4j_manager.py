"""
Neo4j Manager for GraphRAG
Quản lý kết nối đến Neo4j Aura (Cloud)
"""
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError

from core.config import settings


class Neo4jManager:
    """
    Neo4j Connection Manager for GraphRAG
    
    Features:
    - Secure connection to Neo4j Aura (cloud)
    - Connection pooling
    - Schema management
    - Cypher query execution
    """
    
    def __init__(self):
        """Initialize Neo4j manager"""
        self.driver: Optional[Driver] = None
        self.enabled = False
        self.database = settings.NEO4J_DATABASE
    
    def connect(self):
        """
        Connect to Neo4j Aura
        
        Raises:
            Exception: If connection fails
        """
        if not settings.ENABLE_NEO4J:
            print("⚠️ Neo4j is disabled in config")
            return
        
        if not settings.NEO4J_URI:
            print("⚠️ Neo4j URI not configured")
            return
        
        try:
            # Create driver with connection pooling
            # Note: neo4j+s:// scheme already includes TLS encryption
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=50,
                connection_acquisition_timeout=2.0  # 2 seconds for cloud
            )
            
            # Verify connectivity
            self.driver.verify_connectivity()
            
            # Initialize schema
            self._initialize_schema()
            
            self.enabled = True
            print(f"✅ Connected to Neo4j Aura: {settings.NEO4J_URI}")
            
        except AuthError as e:
            print(f"❌ Neo4j authentication failed: {e}")
            print("💡 Check NEO4J_USERNAME and NEO4J_PASSWORD in .env")
            raise
        
        except ServiceUnavailable as e:
            print(f"❌ Neo4j service unavailable: {e}")
            print("💡 Check NEO4J_URI in .env (e.g., neo4j+s://xxxxx.databases.neo4j.io)")
            raise
        
        except Exception as e:
            print(f"❌ Neo4j connection error: {e}")
            raise
    
    def _initialize_schema(self):
        """
        Initialize Neo4j schema with indexes and constraints
        
        Schema Design for GraphRAG:
        - Document nodes: (:Document {id, title, user_id})
        - Chunk nodes: (:Chunk {id, text, index})
        - Entity nodes: (:Entity {name, type})
        - Concept nodes: (:Concept {name})
        - Relationships: CONTAINS, MENTIONS, RELATES_TO, PART_OF
        """
        try:
            with self.driver.session(database=self.database) as session:
                # Create constraints (auto-creates indexes)
                constraints = [
                    # Document constraint
                    """
                    CREATE CONSTRAINT document_id IF NOT EXISTS
                    FOR (d:Document) REQUIRE d.id IS UNIQUE
                    """,
                    # Chunk constraint
                    """
                    CREATE CONSTRAINT chunk_id IF NOT EXISTS
                    FOR (c:Chunk) REQUIRE c.id IS UNIQUE
                    """,
                    # Entity constraint
                    """
                    CREATE CONSTRAINT entity_name_type IF NOT EXISTS
                    FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE
                    """,
                    # Concept constraint
                    """
                    CREATE CONSTRAINT concept_name IF NOT EXISTS
                    FOR (c:Concept) REQUIRE c.name IS UNIQUE
                    """
                ]
                
                for constraint in constraints:
                    try:
                        session.run(constraint)
                    except Exception as e:
                        # Constraint might already exist
                        if "existing constraint" not in str(e).lower():
                            print(f"⚠️ Schema warning: {e}")
                
                # Create additional indexes for performance
                indexes = [
                    "CREATE INDEX document_user_id IF NOT EXISTS FOR (d:Document) ON (d.user_id)",
                    "CREATE INDEX chunk_document_id IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
                    "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                ]
                
                for index in indexes:
                    try:
                        session.run(index)
                    except Exception as e:
                        if "existing index" not in str(e).lower():
                            print(f"⚠️ Index warning: {e}")
                
                print("✅ Neo4j schema initialized")
        
        except Exception as e:
            print(f"❌ Schema initialization error: {e}")
            raise
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute Cypher query and return results
        
        Args:
            query: Cypher query string
            parameters: Query parameters
        
        Returns:
            List of result records as dicts
        """
        if not self.enabled:
            raise Exception("Neo4j is not enabled or connected")
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        
        except Exception as e:
            print(f"❌ Neo4j query error: {e}")
            raise
    
    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute write transaction
        
        Args:
            query: Cypher query
            parameters: Query parameters
        
        Returns:
            Summary statistics
        """
        if not self.enabled:
            raise Exception("Neo4j is not enabled or connected")
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                summary = result.consume()
                
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_deleted": summary.counters.relationships_deleted
                }
        
        except Exception as e:
            print(f"❌ Neo4j write error: {e}")
            raise
    
    def check_connection(self) -> bool:
        """Check if connection is alive"""
        if not self.enabled or not self.driver:
            return False
        
        try:
            self.driver.verify_connectivity()
            return True
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            query = """
            MATCH (n) 
            RETURN 
                count(n) as total_nodes,
                count(DISTINCT labels(n)) as node_types
            """
            result = self.execute_query(query)
            
            query_rels = "MATCH ()-[r]->() RETURN count(r) as total_relationships"
            rels = self.execute_query(query_rels)
            
            stats = result[0] if result else {}
            stats["total_relationships"] = rels[0]["total_relationships"] if rels else 0
            stats["enabled"] = True
            stats["connected"] = self.check_connection()
            
            return stats
        
        except Exception as e:
            print(f"❌ Stats error: {e}")
            return {"enabled": True, "error": str(e)}
    
    def clear_document(self, document_id: str):
        """
        Clear all nodes and relationships for a document
        
        Args:
            document_id: Document UUID
        """
        if not self.enabled:
            return
        
        try:
            query = """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[r1]->(c:Chunk)
            OPTIONAL MATCH (c)-[r2]->(e)
            DELETE r1, r2, c, d
            """
            
            self.execute_write(query, {"document_id": document_id})
            print(f"✅ Cleared graph data for document: {document_id}")
        
        except Exception as e:
            print(f"❌ Clear document error: {e}")
            raise
    
    def disconnect(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            print("Neo4j connection closed")
        self.enabled = False


# Global instance
neo4j_manager = Neo4jManager()
