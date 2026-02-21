import base64
from dataclasses import dataclass

@dataclass
class CachedResponse:
    """Cached response model"""
    status_code: int
    headers: dict
    body: bytes

    def to_dict(self) -> dict:
        """Convert response to dict"""
        body_in_base64 = base64.b64encode(self.body).decode("utf-8")
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": body_in_base64
        }
    
    # Здесь @classmethod используется как альтернативный конструктор
    @classmethod
    def from_dict(cls, data: dict) -> "CachedResponse":
        """Convert dict to cached response"""
        body_in_bytes = base64.b64decode(data["body"].encode("utf-8"))
        return cls(
            status_code = data["status_code"],
            headers = data["headers"],
            body = body_in_bytes
        )
