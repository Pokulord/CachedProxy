import logging
from aiohttp import web

from .interface import ICachedStorage
from .redis_cache import RedisCache
from .http_client import HTTPClient
from .request_handler import ProxyRequestHandler

logger = logging.getLogger(__name__)

class CachingProxyServer:
    def __init__(
            self,
            port: int, 
            origin_url: str,
            cache: ICachedStorage | None = None,
            redis_url: str = "redis://localhost:6379"
            ):
        self.port = port
        self.origin_url = origin_url
        self.cache = cache
        self.redis_url = redis_url
        self.app: web.Application | None = None
        self.http_client: HTTPClient | None = None
        self.handler: ProxyRequestHandler | None = None
        self._runner: web.AppRunner | None = None

    async def start(self):
        """Running proxy server"""
        logger.info(f"Starting proxy server on port {self.port}")
        logger.info(f"Origin server: {self.origin_url}")

        # Initializing cache
        if self.cache is None:
            try:
                logger.info(f"Connecting to Redis at {self.redis_url}")
                self.cache = RedisCache(redis_url=self.redis_url)
                await self.cache.intialize()
                logger.info("Using Redis cache....")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        else:
            await self.cache.intialize()

        
        self.http_client = HTTPClient(self.origin_url)
        await self.http_client.__aenter__()

        self.handler = ProxyRequestHandler(self.cache, self.http_client)

        self.app = web.Application()

        #Registering routes in app ("*" - all HTTP methods, 
        # "/ ... capture URL part as path var")
        self.app.router.add_route("*", "/{path:.*}", self.handler.handle_request)

        self._runner = web.AppRunner(self.app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()

        logger.info(f"Caching proxy server is running on http://localhost:{self.port}")
        logger.info("Press Ctrl + C to stop")

        try:
            import asyncio
            await asyncio.Event().wait()
        finally:
            await self.stop()

    async def stop(self):
        logger.info("Stopping proxy server....")
        if self.http_client:
            await self.http_client.__aexit__(None,None,None)
        logger.info("Server stopped")

    async def clear_cache(self):
        logger.info("Clearing cache....")
        await self.cache.clear()
        logger.info("Cache successfully cleared")
        
