import json 
import hashlib
import logging
from redis import asyncio as aioredis

from .interface import ICachedStorage
from .response_model import CachedResponse

logger = logging.getLogger(__name__)


class RedisCache(ICachedStorage):
    """Implementation of interface"""

    CACHE_KEY_PREFIX = "proxy:cache"

    def __init__(self,
                 redis_url:str = "redis://localhost:6379",
                 max_connections: int = 30,
                 decode_responses: bool = False,
                 socket_keepalive: bool = True,
                 socket_connect_timeout: int = 5,
                 health_check_interval: int = 30
                 ):
         """
        Redis client initialization with connection pool
        
        Args:
            redis_url: URL Redis сервера
            max_connections: max connections in a pool
            decode_responses: Auto decode responses
            socket_keepalive: TCP keep-alive
            socket_connect_timeout: Connection timeout
            health_check_interval: Redis connection health check interval
        """
         
         self.redis_url = redis_url
         self._redis: aioredis.ConnectionPool | None = None

         self._pool_config = {
            'max_connections': max_connections,
            'decode_responses': decode_responses,
            'socket_keepalive': socket_keepalive,
            'socket_connect_timeout': socket_connect_timeout,
            'health_check_interval': health_check_interval,
            'retry_on_timeout': True,
            'retry_on_error': [ConnectionError, TimeoutError]
        }
         
    async def intialize(self):
        """
        Method to initialize Redis connection
        """
        if self._redis is None: 
            logger.info(f"Connecting to redis : {self.redis_url}")
        
        self._connection_pool = aioredis.ConnectionPool.from_url(
            self.redis_url,
            **self._pool_config)
        
        self._redis = aioredis.Redis(connection_pool=self._connection_pool)

        try:
            await self._redis.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis with error : {e}")
            raise aioredis.ConnectionError()
        
    async def get(self, key: str) -> CachedResponse | None:
        """
        Method to get value from Redis cache by the key
        """

        if not self._redis:
            raise RuntimeError("Redis connection is not initialized. Please run initialize()")
        
        try:
            prefixed_key = self._get_prefix_with_key(key)
            data = await self._redis.get(prefixed_key)
            if data is None:
                return None
            
            # Deserialize from JSON 
            cached_dict = json.loads(data)
            return CachedResponse.from_dict(cached_dict)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data for key {key} : {e}")
            await self._redis.delete(prefixed_key)
            return None

        except Exception as e:
            logger.error(f"Error while getting value of {key} : {e}")
            return None
        

    async def set(
            self,
            key: str,
            value: CachedResponse,
            ttl: int | None = None
    ):
        if not self._redis:
            raise RuntimeError("Redis connection is not initialized. Please run initialize()")
        
        try:
            prefixed_key = self._get_prefix_with_key(key)
            # Serialize to JSON
            serialized = json.dumps(value.to_dict())

            if ttl:
                await self._redis.setex(prefixed_key, ttl, serialized)
            else:
                await self._redis.set(prefixed_key, serialized)

            logger.debug(f"Cached response for key {key} with TTL {ttl}")


        except Exception as e:
            logger.error(f"Error setting key {key} in Redis : {e} ")


    async def clear(self) -> None:
        """Clear all proxy cache
        Clears only data with PROXY prefix
        """
        if not self._redis:
            raise RuntimeError("Redis connection is not initialized. Please run initialize()")
        
        try:
            pattern_for_delete = f"{self.CACHE_KEY_PREFIX}*"
            cursor = 0
            deleted_rows_count = 0

            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match=pattern_for_delete,
                    count=500
                )

                if keys:
                    deleted = await self._redis.delete(**keys)
                    deleted_rows_count += deleted

                if cursor == 0:
                    break

            logger.info(f"Successfully cleared {deleted_rows_count} from Redis cache")
        
        except Exception as e:
            logger.error(f"Error clearing Redis cache : {e}")
            raise
    

    async def is_exists(self, key: str) -> bool:
        """Check value for existing in the Redis by the key"""
        if not self._redis:
            raise RuntimeError("Redis connection is not initialized. Please run initialize()")
        
        try:
            prefixed_key = self._get_prefix_with_key(key)
            return await self._redis.exists(prefixed_key) > 0

        except Exception as e:
            logger.error(f"There's error while checking existance : {e}")
            return False
        
    async def close(self) -> None:
        if self._redis:
            logger.info("Closing active Redis connection")
            await self._redis.close()
            await self._connection_pool.disconnect()
            self._redis = None
            self._connection_pool = None

    def _get_prefix_with_key(self, key: str):
        return f"{self.CACHE_KEY_PREFIX}{key}"
    

    @staticmethod
    def generate_key(method: str, url: str, headers: dict | None = None) -> str:
        """Func to generate key that based on 
        HTTP method and headers"""
        key_parts = [method.upper(), url]

        if headers:
            relevant_headers = ["accept", "accept-encoding", "accept-language"]
            for header in relevant_headers:
                header_lower = header.lower()
                # Looking for case-sensetinve header
                for h_key, h_value in headers.items():
                    if h_key.lower() == header_lower:
                        key_parts.append(f"{header_lower}:{h_value}")
                        break

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()