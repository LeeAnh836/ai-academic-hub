"""
LLM Cache Manager
Redis-backed cache for repeated helper LLM calls (intent classification,
query rewriting, CRAG checks). Falls back to in-process memory cache.
"""
import hashlib
import json
import logging
import time
from typing import Any, Optional

import redis

from core.config import settings

logger = logging.getLogger(__name__)


class LLMCacheManager:
    """Cache manager for deterministic or near-deterministic helper LLM tasks."""

    def __init__(self):
        self.client = None
        self.enabled = False
        self._memory_cache: dict[str, tuple[float, str]] = {}

    def connect(self):
        """Connect to Redis if cache is enabled; memory fallback always available."""
        if not settings.ENABLE_LLM_CACHE:
            self.enabled = False
            logger.info("🧠 LLM cache disabled by config")
            return

        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
            )
            self.client.ping()
            self.enabled = True
            logger.info("✅ LLM cache connected to Redis")
        except Exception as e:
            self.enabled = False
            logger.warning(f"⚠️ Redis unavailable for LLM cache, using memory fallback: {e}")

    def disconnect(self):
        if self.client:
            self.client.close()

    def build_key(self, namespace: str, payload: dict[str, Any]) -> str:
        """Create a stable namespaced cache key from payload."""
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"llmcache:{namespace}:{digest}"

    def get(self, key: str) -> Optional[Any]:
        """Get cached JSON value if present and valid."""
        if not settings.ENABLE_LLM_CACHE:
            return None

        if self.enabled and self.client:
            try:
                value = self.client.get(key)
                if value is not None:
                    return json.loads(value)
            except Exception as e:
                logger.debug(f"LLM cache Redis get failed, fallback to memory: {e}")

        # Memory fallback
        mem_item = self._memory_cache.get(key)
        if not mem_item:
            return None
        expires_at, value = mem_item
        if expires_at < time.time():
            self._memory_cache.pop(key, None)
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set cache value in Redis (if available) and memory fallback."""
        if not settings.ENABLE_LLM_CACHE:
            return False

        ttl = ttl_seconds or settings.LLM_CACHE_TTL_SECONDS
        serialized = json.dumps(value, ensure_ascii=False, default=str)

        redis_ok = False
        if self.enabled and self.client:
            try:
                self.client.setex(key, ttl, serialized)
                redis_ok = True
            except Exception as e:
                logger.debug(f"LLM cache Redis set failed, fallback to memory: {e}")

        self._memory_cache[key] = (time.time() + ttl, serialized)
        return redis_ok or True


llm_cache = LLMCacheManager()
