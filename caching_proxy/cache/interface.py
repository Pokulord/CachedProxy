from abc import ABC, abstractmethod

from .response_model import CachedResponse

class ICachedStorage(ABC):
    """Interface for cached storage"""

    @abstractmethod
    async def get(self, key: str) -> CachedResponse | None:
        """Get value from cache"""
        ...

    @abstractmethod
    async def save_value(self, key: str, value: CachedResponse, ttl: int | None = None) -> None:
        """Save value in cache"""
        ...

    @abstractmethod
    async def is_exists(self, key: str) -> bool:
        """Check is value already in cache"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connection"""
        ...