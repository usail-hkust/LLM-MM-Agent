"""
Distributed Event Bus using Redis Streams.

Structure: Channel(ProjectID) -> Redis Stream -> Local Queue.
Decouples the Service Layer (Write) from API Streaming (Read).
Supports multi-instance event broadcasting.
"""
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict

from app.core.config import settings
from app.infra.persistence.redis import get_redis_client

logger = logging.getLogger("lcp.events")


class DistributedEventBus:
    """
    Distributed Event Bus using Redis Streams.
    
    [ARCHITECTURE]
    - Publish: XADD to Redis Stream (persistent, cross-instance)
    - Subscribe: Background poller (XREAD) + Local Queue (for SSE)
    - History: XREVRANGE on subscribe (fixes Late Subscriber problem)
    
    [FIX] Implements history replay:
    1. New subscribers get recent messages via XREVRANGE
    2. Poller uses $ cursor to only listen for new messages
    3. Messages distributed via local asyncio.Queue to subscribers
    """
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._pollers: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._redis_client = None
        self._redis_checked = False
        self._redis_available = False
        self._fallback_logged = False
        self._shutdown_event = asyncio.Event()

    def _get_stream_key(self, channel: str) -> str:
        """Get Redis Stream key with prefix."""
        return f"{settings.REDIS_PREFIX}:stream:{channel}"

    async def _ensure_redis(self):
        """Ensure Redis client is available."""
        if self._redis_checked and not self._redis_available:
            return False

        if self._redis_client is None:
            self._redis_client = await get_redis_client()
            self._redis_checked = True
            if self._redis_client is None:
                self._redis_available = False
                if not self._fallback_logged:
                    logger.info("Redis not available; using in-memory event mode")
                    self._fallback_logged = True
                return False
            self._redis_available = True
        return True

    async def publish(self, channel: str, event_type: str, payload: Any):
        """
        Publish event to Redis Stream.
        Uses XADD to write to stream with MAXLEN to prevent unbounded growth.
        """
        msg = {"event": event_type, "data": payload}
        
        # Try Redis first
        if await self._ensure_redis():
            try:
                stream_key = self._get_stream_key(channel)
                # XADD with MAXLEN to cap stream size
                await self._redis_client.xadd(
                    stream_key,
                    {"message": json.dumps(msg)},
                    maxlen=settings.REDIS_STREAM_MAX_LEN,
                    approximate=True  # Use ~ for better performance
                )
                logger.debug(f"Published event to Redis stream: {channel}/{event_type}")
                return
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}", exc_info=True)
                # Fall through to in-memory mode
        
        # Fallback: In-memory distribution (if Redis unavailable)
        async with self._lock:
            queues = list(self._subscribers.get(channel, []))
        
        for q in queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for channel {channel}, dropping message.")

    async def subscribe(self, channel: str) -> asyncio.Queue:
        """
        Subscribe to channel.
        Returns a queue pre-filled with recent history from Redis Stream.
        [FIX] History replay happens BEFORE adding to subscriber list to avoid race conditions.
        """
        # Create queue for this subscriber
        queue_size = settings.EVENT_BUS_LOG_HISTORY_SIZE + settings.EVENT_BUS_HISTORY_SIZE + 200
        q = asyncio.Queue(maxsize=queue_size)
        
        # [FIX] Replay history FIRST, before adding to subscriber list
        # This ensures historical messages are delivered before any new messages from the poller
        if await self._ensure_redis():
            try:
                stream_key = self._get_stream_key(channel)
                # Get recent messages (last N messages)
                # We fetch both critical and log history sizes to cover all cases
                count = settings.EVENT_BUS_HISTORY_SIZE + settings.EVENT_BUS_LOG_HISTORY_SIZE
                messages = await self._redis_client.xrevrange(
                    stream_key,
                    count=count
                )
                
                # Replay in chronological order (oldest first)
                for stream_id, data in reversed(messages):
                    try:
                        msg_str = data.get("message")
                        if msg_str:
                            msg = json.loads(msg_str)
                            
                            # =========================================================================
                            # [CRITICAL FIX] Transient Event Isolation
                            # Problem: 
                            # Replaying "ERROR" events on page load caused infinite "Ghost Error" Toasts.
                            # Solution:
                            # Classify events. Only State (NODE_*) and Stream (EXEC_LOG) are historical.
                            # ERROR is a one-time notification and strictly MUST NOT be replayed.
                            # =========================================================================
                            if msg.get("event") == "ERROR":
                                continue
                                
                            q.put_nowait(msg)
                    except (json.JSONDecodeError, asyncio.QueueFull) as e:
                        logger.warning(f"Failed to replay message: {e}")
                
                logger.debug(f"Replayed {len(messages)} messages for channel {channel}")
            except Exception as e:
                logger.error(f"Failed to replay history from Redis: {e}", exc_info=True)
        
        # Now add to subscriber list and start poller (if needed)
        async with self._lock:
            self._subscribers[channel].append(q)
            
            # Start Redis poller only when Redis is available. In-memory mode
            # publishes directly to local queues and does not need polling.
            if self._redis_available and channel not in self._pollers:
                self._pollers[channel] = asyncio.create_task(
                    self._poller_task(channel)
                )
        
        logger.debug(f"New subscriber on {channel}")
        return q

    async def _poller_task(self, channel: str):
        """
        Background task that polls Redis Stream for new messages.
        Uses $ cursor to only read new messages (after subscription).
        """
        stream_key = self._get_stream_key(channel)
        last_id = "$"  # Only read new messages
        
        while not self._shutdown_event.is_set():
            try:
                if not await self._ensure_redis():
                    # Redis unavailable, wait and retry
                    await asyncio.sleep(1)
                    continue
                
                # XREAD with blocking (wait up to 1 second for new messages)
                streams = await self._redis_client.xread(
                    {stream_key: last_id},
                    count=10,  # Read up to 10 messages at a time
                    block=1000  # Block for 1 second
                )
                
                if streams:
                    # Process messages
                    for stream, messages in streams:
                        for stream_id, data in messages:
                            try:
                                msg_str = data.get("message")
                                if msg_str:
                                    msg = json.loads(msg_str)
                                    # Distribute to all subscribers
                                    async with self._lock:
                                        queues = list(self._subscribers.get(channel, []))
                                    
                                    for q in queues:
                                        try:
                                            q.put_nowait(msg)
                                        except asyncio.QueueFull:
                                            logger.warning(f"Queue full, dropping message on {channel}")
                                    
                                    last_id = stream_id
                            except (json.JSONDecodeError, Exception) as e:
                                logger.error(f"Error processing message from stream: {e}", exc_info=True)
                
            except asyncio.CancelledError:
                logger.debug(f"Poller for {channel} cancelled")
                break
            except Exception as e:
                logger.error(f"Error in poller for {channel}: {e}", exc_info=True)
                await asyncio.sleep(1)  # Wait before retrying

    async def unsubscribe(self, channel: str, q: asyncio.Queue):
        """Remove a subscriber from a channel."""
        async with self._lock:
            if channel in self._subscribers:
                try:
                    self._subscribers[channel].remove(q)
                    if not self._subscribers[channel]:
                        del self._subscribers[channel]
                        # Stop poller if no more subscribers
                        if channel in self._pollers:
                            self._pollers[channel].cancel()
                            del self._pollers[channel]
                except ValueError:
                    pass
        logger.debug(f"Subscriber removed from {channel}.")

    async def shutdown(self):
        """Shutdown all pollers and clean up resources."""
        logger.info("Shutting down DistributedEventBus...")
        self._shutdown_event.set()
        
        # Cancel all poller tasks
        async with self._lock:
            for channel, task in list(self._pollers.items()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._pollers.clear()
            self._subscribers.clear()
        
        logger.info("DistributedEventBus shutdown complete")


# Backward compatibility: Keep EventBus as alias
EventBus = DistributedEventBus

# Global Singleton
event_bus = DistributedEventBus()
