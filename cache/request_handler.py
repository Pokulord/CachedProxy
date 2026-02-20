import logging
from aiohttp import web

from .interface import ICachedStorage
from .redis_cache import CachedResponse
from .redis_cache import RedisCache
from .http_client import HTTPClient

logger = logging.getLogger(__name__)

class ProxyRequestHandler:
    
    CACHE_HIT_HEADER = "X-Cache"
    CACHE_HIT_VALUE = "HIT"
    CACHE_MISS_VALUE = "MISS"

    def __init__(self, cache: ICachedStorage, http_client: HTTPClient):
        self.cache = cache
        self.http_client =  http_client

    async def handle_request(self, request: web.Request) -> web.Response:
        method = request.method
        # path_qs returns url-path with query parameters (?id=1)
        path = request.path_qs
        headers = dict(request.headers)
        body = await request.read() if request.can_read_body else None

        # We caching only GET-requests

        if method.upper() != "GET":
            return await self._forward_non_cacheable(path, method, headers, body)
        
        # Generating cache key 
        cache_key = RedisCache.generate_key(method,path, headers)
        cached_response = await self.cache.get(cache_key)

        if cached_response:
            logger.info(f"Cache HIT for {method} {path}")
            return self._build_response_from_cache(cached_response, cache_hit = True)
        logger.info(f"Cache MISS for {method} {path}")

        try:
            status, resp_headers, resp_body = await self.http_client.forward_request(
                path=path,
                method=method,
                headers=headers,
                body=body
            )
            # Кэшируем успешные ответы
            if self._should_cache_response(status, resp_headers):
                cached = CachedResponse(
                    status_code=status,
                    headers=resp_headers,
                    body=resp_body
                )
                await self.cache.get(cache_key, cached, ttl=3600)

            return self._build_response(status, resp_headers, resp_body, cache_hit=False)

        except Exception as e:
            logger.error(f"Error while forwarding request : {e}")
            return web.Response(
                status=502,
                text=f"Bad gateway : {str(e)}",
                headers={self.CACHE_HIT_HEADER: self.CACHE_MISS_VALUE}
            )
        
    async def _forward_non_cacheable(
            self,
            path: str,
            method: str,
            headers: str,
            body: bytes | None
    ) -> web.Response:
        """Forwarding requests with method != GET 
        PUT, POST, PATCH, DELETE
        """
        try:
            status, resp_headers, resp_body = await self.http_client.forward_request(
                path=path,
                method=method,
                headers=headers,
                body=body
            )
            return self._build_response(status, resp_headers, resp_body, cache_hit=False)

        except Exception as e:
            logger.error(f"Error forwarding non-cacheable request: {e}")
            # We need to use cache_hit = False cause of forming request "from zero" - not from cache
            return web.Response(status=502, text=f"Bad Gateway: {str(e)}")
        

    def _build_response(
            self,
            status_code: int,
            headers: dict,
            body: bytes,
            cache_hit: bool
    ) -> web.Response:
        """Building HTTP response"""
        headers = dict(headers)
        headers[self.CACHE_HIT_HEADER] = self.CACHE_HIT_VALUE if cache_hit else self.CACHE_MISS_VALUE

        return web.Response(
            status=status_code,
            headers=headers,
            body=body
        )
    
    def _build_response_from_cache(
            self,
            cached: CachedResponse,
            cache_hit: bool
    ) -> web.Response:
        """Building response from the cached data"""
        headers = dict(cached.headers)
        headers[self.CACHE_HIT_HEADER] = self.CACHE_HIT_VALUE if cache_hit else self.CACHE_MISS_VALUE

        return web.Response(
            status=cached.status_code,
            headers=headers,
            body=cached.body
        )  
      
    @staticmethod
    def _should_cache_response(status: int, headers: dict) -> bool:
        """Defines should server cache response"""
        if status != 200:
            return False
        
        cache_control = headers.get("Cache-Control", "").lower()
        if "no-store" in cache_control or "private" in cache_control:
            return False
        
        if "Set-Cookie" in headers:
            return False
        
        return True