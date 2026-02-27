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

        headers.pop('Accept-Encoding', None)
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
                await self.cache.save_value(cache_key, cached, ttl=3600)
                logger.info("Saving value to Redis.....")

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
                # Создаем копию заголовков
        response_headers = {}
        
        # Копируем только безопасные заголовки
        safe_headers = [
            'content-type', 'date', 'server', 'access-control-allow-origin',
            'strict-transport-security', 'x-content-type-options',
            'x-frame-options', 'x-xss-protection', 'cache-control',
            'age', 'cf-cache-status', 'cf-ray', 'vary'
        ]
        
        for key, value in headers.items():
            if key.lower() in safe_headers:
                response_headers[key] = value
        
        # Добавляем наш заголовок кэша
        response_headers[self.CACHE_HIT_HEADER] = self.CACHE_HIT_VALUE if cache_hit else self.CACHE_MISS_VALUE
        
        # Явно указываем Content-Length вместо chunked encoding
        response_headers['Content-Length'] = str(len(body))

        return web.Response(
            status=status_code,
            headers=response_headers,
            body=body
        )
    
    def _build_response_from_cache(
            self,
            cached: CachedResponse,
            cache_hit: bool
    ) -> web.Response:
        """Building response from the cached data"""
        response_headers = {}
        
        # Копируем только безопасные заголовки из кэша
        safe_headers = [
            'content-type', 'date', 'server', 'access-control-allow-origin',
            'strict-transport-security', 'x-content-type-options',
            'x-frame-options', 'x-xss-protection', 'cache-control',
            'age', 'cf-cache-status', 'cf-ray', 'vary'
        ]
        
        for key, value in cached.headers.items():
            if key.lower() in safe_headers:
                response_headers[key] = value
        
        # Добавляем наш заголовок кэша
        response_headers[self.CACHE_HIT_HEADER] = self.CACHE_HIT_VALUE if cache_hit else self.CACHE_MISS_VALUE
        
        # Явно указываем Content-Length
        response_headers['Content-Length'] = str(len(cached.body))

        return web.Response(
            status=cached.status_code,
            headers=response_headers,
            body=cached.body
        )  
      
      
    @staticmethod
    def _should_cache_response(status: int, headers: dict) -> bool:
        """Defines should server cache response"""
        if status == 200:
            return True
        return False