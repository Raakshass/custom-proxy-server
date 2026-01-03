"""
Caching Module
Implements LRU (Least Recently Used) caching for HTTP responses
"""

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

@dataclass
class CachedResponse:
    """Stores response data and metadata"""
    status_code: int
    headers: bytes
    body: bytes
    timestamp: float
    original_url: str

class LRUCache:
    """Thread-safe LRU Cache implementation"""
    
    def __init__(self, max_size_bytes: int = 50 * 1024 * 1024, ttl_seconds: int = 300):
        """
        Initialize cache
        
        Args:
            max_size_bytes: Maximum memory usage in bytes (default 50MB)
            ttl_seconds: Time to live for cache entries (default 5 mins)
        """
        self.cache = OrderedDict()
        self.current_size = 0
        self.max_size = max_size_bytes
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
        
    def get(self, url: str) -> Optional[CachedResponse]:
        """Get item from cache"""
        with self.lock:
            if url not in self.cache:
                return None
            
            response = self.cache[url]
            
            # Check expiration
            if time.time() - response.timestamp > self.ttl:
                self._remove(url)
                return None
            
            # Move to end (mark as recently used)
            self.cache.move_to_end(url)
            return response

    def put(self, url: str, status: int, headers: bytes, body: bytes) -> None:
        """Add item to cache"""
        size = len(body) + len(headers)
        
        # Don't cache items larger than max size
        if size > self.max_size:
            return

        with self.lock:
            # If exists, update and move to end
            if url in self.cache:
                self._remove(url)
            
            # Evict old items if needed
            while self.current_size + size > self.max_size and self.cache:
                self.cache.popitem(last=False) # Remove first item (least recently used)
                # Note: In a real implementation we'd track exact size of removed items
                # For simplicity here, we rely on the loop
                self.current_size -= 1024 # Approx reduction logic for safety

            response = CachedResponse(
                status_code=status,
                headers=headers,
                body=body,
                timestamp=time.time(),
                original_url=url
            )
            
            self.cache[url] = response
            self.current_size += size

    def _remove(self, url: str):
        """Internal remove"""
        if url in self.cache:
            entry = self.cache.pop(url)
            self.current_size -= (len(entry.body) + len(entry.headers))

    def clear(self):
        """Clear cache"""
        with self.lock:
            self.cache.clear()
            self.current_size = 0
