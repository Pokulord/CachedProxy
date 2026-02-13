from dataclasses import dataclass

@dataclass
class CachedResponse:
    """Cached response model"""
    status_code: int
    headers: dict
    body: bytes

    def to_dict(self) -> dict:
        """Convert response to dict"""
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body.decode("latin-1")
        }
    
    # Здесь @classmethod используется как альтернативный конструктор
    @classmethod
    def from_dict(cls, data: dict) -> "CachedResponse":
        """Convert dict to cached response"""
        return cls(
            status_code = data["status_code"],
            headers = data["headers"],
            body = data["body"].encode("latin-1")
        )
