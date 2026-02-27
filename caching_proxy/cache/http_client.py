import aiohttp
import asyncio
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class HTTPClient:

    def __init__(self, origin_url: str, timeout: int = 30):
        self.origin_url = origin_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def forward_request(
            self,
            path: str,
            method: str = "GET",
            headers: dict| None = None,
            body: bytes| None = None
            ) -> tuple[int,dict,bytes]:
        """Forwards request to Origin"""

        if not self._session:
            raise RuntimeError("No active HTTP client session" \
            "Please start one using async context manager")
        
        full_url = urljoin(self.origin_url, path.lstrip("/"))

        safe_headers = self._sanitize_headers(headers or {})
        safe_headers["Accept-Encoding"] = "gzip, deflate"

        try: 
            logger.info(f"Forwarding {method} to {full_url}")

            async with self._session.request(
                method=method.upper(),
                url=full_url,
                headers=safe_headers,
                data=body,
                allow_redirects=True
            ) as response:
                status = response.status
                headers_dict = dict(response.headers)
                body_bytes = await response.read()

                logger.info(f"Recieved response: {status} from {full_url}")
                return status, headers_dict, body_bytes
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise
        except asyncio.TimeoutError as e:
            logger.error(f"Reached timeout while connecting to {full_url}")
            raise

    @staticmethod
    def _sanitize_headers(headers: dict) -> dict:
        """Deleting potentially dangerous headers"""
        blocked_headers = {
        'host', 'connection', 'keep-alive', 'proxy-connection',
        'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
        'transfer-encoding', 'upgrade'
        }

        return {
            k: v for k,v in headers.items() if k.lower() not in blocked_headers
        }