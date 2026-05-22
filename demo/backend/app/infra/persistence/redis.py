"""
Redis Infrastructure Layer.

Manages Redis connection pool and provides async Redis client.
"""
import logging
from typing import Optional
from functools import lru_cache

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

logger = logging.getLogger("lcp.redis")


class RedisManager:
    """
    Singleton Redis Manager.
    Manages connection pool and provides async Redis client.
    """
    _instance: Optional['RedisManager'] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False

    async def initialize(self):
        """Initialize Redis connection pool."""
        if self._initialized:
            return

        try:
            redis_url = settings.REDIS_URL
            if not redis_url:
                logger.info("REDIS_URL not configured; using local in-memory event mode")
                self._initialized = True
                return

            # Create connection pool
            self._pool = aioredis.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=3
            )
            
            # Create client
            self._client = Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            logger.info("Redis connection pool initialized successfully")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}", exc_info=True)
            self._client = None
            self._pool = None
            self._initialized = True

    async def get_client(self) -> Optional[Redis]:
        """Get Redis client. Returns None if not initialized."""
        if not self._initialized:
            await self.initialize()
        return self._client

    async def shutdown(self):
        """Close Redis connection pool."""
        if self._client:
            try:
                await self._client.aclose()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")
            finally:
                self._client = None

        if self._pool:
            try:
                await self._pool.aclose()
                logger.info("Redis connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Redis pool: {e}")
            finally:
                self._pool = None

        self._initialized = False


# Global singleton instance
_redis_manager = RedisManager()


async def get_redis_manager() -> RedisManager:
    """Get Redis manager singleton."""
    return _redis_manager


async def get_redis_client() -> Optional[Redis]:
    """
    FastAPI dependency: Get Redis client.
    Returns None if Redis is not configured or unavailable.
    """
    manager = await get_redis_manager()
    return await manager.get_client()
