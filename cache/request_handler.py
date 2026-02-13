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
        path = request.path_qs
