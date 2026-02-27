from dataclasses import dataclass


@dataclass
class ProxyConfig:
    """Конфигурация прокси-сервера"""
    port: int
    origin: str
    cache_max_size: int = 1000
    cache_ttl: int = 3600  # 1 час по умолчанию
    log_level: str = 'INFO'
    
    def validate(self) -> None:
        """Валидация конфигурации"""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port number: {self.port}")
        
        if not self.origin.startswith(('http://', 'https://')):
            raise ValueError(f"Origin must start with http:// or https://: {self.origin}")
        
        if self.cache_max_size < 1:
            raise ValueError(f"Cache max size must be positive: {self.cache_max_size}")
