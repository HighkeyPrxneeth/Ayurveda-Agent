"""
Response Caching Service

Implements TTL-based caching for common queries to improve performance.
Uses an in-memory cache with configurable TTL and max size.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from threading import Lock


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with expiration tracking."""
    value: Any
    created_at: datetime
    ttl_seconds: int
    hit_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get the age of the entry in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate the cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class ResponseCache:
    """
    TTL-based response cache for Ayurveda queries.
    
    Features:
    - Configurable TTL per entry type
    - Maximum size with LRU eviction
    - Thread-safe operations
    - Statistics tracking
    """
    
    # Default TTL values (in seconds)
    TTL_SIMPLE_QUERY = 3600      # 1 hour for simple queries
    TTL_DOSHA_ASSESSMENT = 86400  # 24 hours for Dosha assessments (deterministic)
    TTL_TREATMENT_PLAN = 1800     # 30 minutes for treatment plans
    
    def __init__(self, max_size: int = 500):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = Lock()
        self._stats = CacheStats()
        logger.info("ResponseCache initialized with max_size=%d", max_size)
    
    def _generate_key(self, query: str, context: Optional[dict] = None) -> str:
        """Generate a unique cache key from query and context."""
        key_data = {"query": query.lower().strip()}
        if context:
            # Include relevant context in key (sorted for consistency)
            key_data["context"] = json.dumps(context, sort_keys=True)
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def get(self, query: str, context: Optional[dict] = None) -> Optional[Any]:
        """
        Retrieve a cached response.
        
        Args:
            query: The user's query
            context: Optional context (dosha scores, health conditions)
            
        Returns:
            Cached response or None if not found/expired
        """
        key = self._generate_key(query, context)
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                logger.debug("Cache entry expired: %s", key)
                return None
            
            entry.hit_count += 1
            self._stats.hits += 1
            logger.debug("Cache hit: %s (hits=%d)", key, entry.hit_count)
            return entry.value
    
    def set(
        self, 
        query: str, 
        value: Any, 
        context: Optional[dict] = None,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store a response in the cache.
        
        Args:
            query: The user's query
            value: The response to cache
            context: Optional context for key generation
            ttl_seconds: Custom TTL (uses default if not specified)
        """
        key = self._generate_key(query, context)
        ttl = ttl_seconds or self.TTL_SIMPLE_QUERY
        
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl_seconds=ttl
            )
            logger.debug("Cache set: %s (ttl=%ds)", key, ttl)
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry from the cache."""
        if not self._cache:
            return
        
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at
        )
        del self._cache[oldest_key]
        self._stats.evictions += 1
        logger.debug("Evicted oldest entry: %s", oldest_key)
    
    def invalidate(self, query: str, context: Optional[dict] = None) -> bool:
        """Invalidate a specific cache entry."""
        key = self._generate_key(query, context)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> int:
        """Clear all cache entries. Returns count of cleared entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info("Cache cleared: %d entries removed", count)
            return count
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "evictions": self._stats.evictions,
                "hit_rate": round(self._stats.hit_rate, 3)
            }


# Singleton instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get or create the singleton cache instance."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache

