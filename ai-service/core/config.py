"""
AI Service Configuration
Cấu hình cho AI Service - xử lý embedding, RAG, LLM
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Cấu hình AI Service - Load từ .env file"""
    
    # Service Info
    SERVICE_NAME: str = "JVB AI Service"
    SERVICE_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = True
    
    # Qdrant Settings (Vector Database)
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "jvb_embeddings"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_GRPC_PORT: int = 6334
    
    # Neo4j Settings (Graph Database for GraphRAG)
    NEO4J_URI: Optional[str] = None  # e.g., "neo4j+s://xxxxx.databases.neo4j.io"
    NEO4J_USERNAME: Optional[str] = None  # Usually "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    NEO4J_DATABASE: str = "neo4j"  # Default database name
    ENABLE_NEO4J: bool = False  # Enable after setup
    
    # Cohere Settings (Embeddings & LLM)
    COHERE_API_KEY: str
    COHERE_EMBEDDING_MODEL: str = "embed-multilingual-v3.0"
    VECTOR_DIMENSION: int = 1024
    
    # Google Gemini Settings (PRIMARY LLM - FREE)
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_FLASH_MODEL: str = "gemini-1.5-flash-latest"
    GEMINI_PRO_MODEL: str = "gemini-1.5-pro-latest"
    
    # Groq Settings (FALLBACK LLM - FREE)
    GROQ_API_KEY: Optional[str] = None
    GROQ_LLAMA_MODEL: str = "llama-3.3-70b-versatile"

    # OpenAI Settings (GPT)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Anthropic Settings (Claude)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # Mistral Settings
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-small-latest"
    
    # Model Selection Strategy
    PRIMARY_PROVIDER: str = "gemini"  # gemini, groq, cohere
    FALLBACK_PROVIDER: str = "groq"
    ENABLE_GEMINI: bool = True
    ENABLE_GROQ: bool = True
    ENABLE_OPENAI: bool = False
    ENABLE_ANTHROPIC: bool = False
    ENABLE_MISTRAL: bool = True
    
    # RAG Settings
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.5  # Dynamic threshold
    RAG_MIN_SCORE_THRESHOLD: float = 0.3  # Minimum fallback threshold
    RAG_MAX_CONTEXT_LENGTH: int = 8000
    RAG_ENABLE_FALLBACK: bool = True  # Enable fallback retrieval
    
    # GraphRAG Settings
    ENABLE_GRAPH_RAG: bool = False  # Enable after Neo4j setup
    GRAPH_RAG_MODE: str = "hybrid"  # "vector_only", "graph_only", "hybrid"
    GRAPH_EXTRACTION_MODEL: str = "gemini"  # Use Gemini Flash for free entity extraction
    GRAPH_MAX_ENTITIES: int = 50  # Max entities to extract per chunk
    GRAPH_TOP_K: int = 10  # Top K related entities from graph
    GRAPH_TRAVERSAL_DEPTH: int = 2  # How deep to traverse relationships

    # Advanced RAG Settings
    ENABLE_ADVANCED_RAG: bool = True  # Enable full Advanced RAG pipeline
    # Query Rewriting
    ENABLE_QUERY_REWRITING: bool = True  # Multi-query expansion
    QUERY_REWRITE_VARIANTS: int = 3  # Number of query variants to generate
    # Hybrid Search (BM25 + Vector)
    ENABLE_BM25_RESCORING: bool = True  # BM25 keyword re-scoring on retrieved chunks
    BM25_VECTOR_WEIGHT: float = 0.7  # Weight for vector score in hybrid (1-this = BM25 weight)
    # Re-ranking
    ENABLE_RERANKING: bool = True  # Enable cross-encoder re-ranking
    ENABLE_COHERE_RERANK: bool = True  # Use Cohere Rerank API (requires COHERE_API_KEY)
    COHERE_RERANK_MODEL: str = "rerank-multilingual-v3.0"  # Cohere multilingual rerank model
    ADVANCED_RAG_INITIAL_TOP_K: int = 15  # Retrieve this many before re-ranking
    ADVANCED_RAG_FINAL_TOP_K: int = 5  # Return this many after re-ranking
    # Corrective RAG (CRAG)
    ENABLE_CORRECTIVE_RAG: bool = True  # Enable self-correction evaluation
    CRAG_MAX_ATTEMPTS: int = 2  # Max corrective re-retrieval attempts
    # Multi-hop Reasoning
    ENABLE_MULTI_HOP: bool = True  # Enable multi-hop for complex queries

    # LLM Cache Settings (for helper LLM calls, not final answers)
    ENABLE_LLM_CACHE: bool = True
    LLM_CACHE_TTL_SECONDS: int = 900  # 15 minutes
    
    # Intent Classification
    ENABLE_INTENT_CLASSIFICATION: bool = True
    ENABLE_DIRECT_CHAT: bool = True  # Allow chat without documents
    
    # LLM Settings
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 8000  # Near maximum for comprehensive explanations
    LLM_TIMEOUT: int = 240  # 4 minutes for very detailed answers
    
    # Chunking Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # MongoDB Settings (Conversation Memory)
    MONGODB_URI: str = "mongodb://mongo:27017"
    MONGODB_DB_NAME: str = "jvb_chat"
    MEMORY_TTL: int = 3600  # used for optional ephemeral context cleanups

    # Redis Settings (LLM cache only)
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Multi-Agent Settings
    ENABLE_MULTI_AGENT: bool = True
    ENABLE_PROMPT_PREPROCESSING: bool = True
    ENABLE_DATA_ANALYSIS: bool = True
    ENABLE_CODE_EXECUTION: bool = True
    
    # Code Execution Settings
    # Code Execution Settings
    DOCKER_HOST: str = "unix:///var/run/docker.sock"
    CODE_EXEC_TIMEOUT: int = 30  # 30 seconds
    CODE_EXEC_DOCKER_IMAGE: str = "python:3.11-slim"
    CODE_EXEC_MAX_OUTPUT_SIZE: int = 10000  # 10KB
    
    # Data Analysis Settings
    PANDAS_MAX_ROWS: int = 10000
    PANDAS_MAX_COLUMNS: int = 100
    ENABLE_CHART_GENERATION: bool = True
    
    # MCP Settings (Model Context Protocol)
    ENABLE_MCP: bool = False  # Will enable after setup
    MCP_SERVER_URL: Optional[str] = None
    
    # CORS Settings
    CORS_ORIGINS: str = "*"
    
    def get_cors_origins(self) -> list[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
