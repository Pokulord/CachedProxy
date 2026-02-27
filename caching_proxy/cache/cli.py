# src/cli.py
import argparse
import asyncio
import logging
import sys
from .config import ProxyConfig
from .server import CachingProxyServer
from .redis_cache import RedisCache


def setup_logging(level: str = 'INFO'):
    """Настройка логирования"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def parse_arguments() -> argparse.Namespace:
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Caching Proxy Server - A simple HTTP caching proxy'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        help='Port number for the proxy server'
    )
    
    parser.add_argument(
        '--origin',
        type=str,
        help='Origin server URL (e.g., http://dummyjson.com)'
    )
    
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear the cache and exit'
    )
    
    parser.add_argument(
        '--cache-size',
        type=int,
        default=1000,
        help='Maximum number of cached items (default: 1000)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


async def clear_cache_command():
    """Команда для очистки кэша"""
    cache = RedisCache()
    await cache.clear()
    print("Cache cleared successfully")


async def start_server_command(config: ProxyConfig):
    """Команда для запуска сервера"""
    config.validate()
    
    cache = RedisCache()
    server = CachingProxyServer(
        port=config.port,
        origin_url=config.origin,
        cache=cache
    )
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


def main():
    """Главная функция CLI"""
    args = parse_arguments()
    setup_logging(args.log_level)
    
    if args.clear_cache:
        asyncio.run(clear_cache_command())
        return
    
    if not args.port or not args.origin:
        print("Error: --port and --origin are required")
        print("Usage: caching-proxy --port <number> --origin <url>")
        sys.exit(1)
    
    config = ProxyConfig(
        port=args.port,
        origin=args.origin,
        cache_max_size=args.cache_size,
        log_level=args.log_level
    )
    
    try:
        asyncio.run(start_server_command(config))
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
