"""
Logging Module
Handles proxy access logging and event tracking
"""

import logging
import logging.handlers
from pathlib import Path


class ProxyLogger:
    """Centralized logging for proxy server"""
    
    def __init__(self, log_dir: str = 'logs', level: str = 'INFO', 
                 max_bytes: int = 10485760, backup_count: int = 7):
        """Initialize proxy logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create loggers for different aspects
        self.access_logger = self._setup_logger('access', 'access.log', 
                                               max_bytes, backup_count)
        self.error_logger = self._setup_logger('error', 'error.log',
                                              max_bytes, backup_count)
        self.debug_logger = self._setup_logger('debug', 'debug.log',
                                              max_bytes, backup_count)
        
        # Set levels
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.access_logger.setLevel(log_level)
        self.error_logger.setLevel(logging.ERROR)
        self.debug_logger.setLevel(logging.DEBUG)
    
    def _setup_logger(self, name: str, filename: str, 
                      max_bytes: int, backup_count: int) -> logging.Logger:
        """Setup individual logger with rotation"""
        logger = logging.getLogger(name)
        
        # File handler with rotation
        log_file = self.log_dir / filename
        handler = logging.handlers.RotatingFileHandler(
            str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        
        # Format: timestamp | level | message
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        logger.propagate = False
        
        return logger
    
    def log_request_allowed(self, client_addr: str, client_port: int, 
                           target_host: str, target_port: int,
                           request_line: str, status_code: int = 0,
                           bytes_sent: int = 0, bytes_received: int = 0) -> None:
        """Log an allowed request"""
        status_str = f"HTTP {status_code}" if status_code else "PENDING"
        self.access_logger.info(
            f"ALLOWED | {client_addr}:{client_port} -> {target_host}:{target_port} | "
            f"{request_line} | {status_str} | "
            f"Sent: {bytes_sent} | Received: {bytes_received}"
        )
    
    def log_request_blocked(self, client_addr: str, client_port: int,
                           target_host: str, request_line: str,
                           reason: str) -> None:
        """Log a blocked request"""
        self.access_logger.info(
            f"BLOCKED | {client_addr}:{client_port} -> {target_host} | "
            f"{request_line} | Reason: {reason}"
        )
    
    def log_error(self, error_type: str, client_addr: str = '',
                 target_host: str = '', details: str = '') -> None:
        """Log an error"""
        msg = f"{error_type}"
        if client_addr:
            msg += f" | Client: {client_addr}"
        if target_host:
            msg += f" | Host: {target_host}"
        if details:
            msg += f" | {details}"
        
        self.error_logger.error(msg)
    
    def log_debug(self, event: str, **kwargs) -> None:
        """Log debug information"""
        details = ' | '.join(f"{k}={v}" for k, v in kwargs.items())
        if details:
            self.debug_logger.debug(f"{event} | {details}")
        else:
            self.debug_logger.debug(event)
    
    def log_server_start(self, host: str, port: int) -> None:
        """Log server startup"""
        self.access_logger.info(f"SERVER_START | Listening on {host}:{port}")
    
    def log_server_stop(self) -> None:
        """Log server shutdown"""
        self.access_logger.info("SERVER_STOP | Server shutting down")


class ConnectionTracker:
    """Tracks active connections for metrics"""
    
    def __init__(self):
        self.active_connections = 0
        self.total_connections = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.blocked_requests = 0
        self.allowed_requests = 0
    
    def record_connection_start(self) -> None:
        """Record a new connection"""
        self.active_connections += 1
        self.total_connections += 1
    
    def record_connection_end(self) -> None:
        """Record connection end"""
        if self.active_connections > 0:
            self.active_connections -= 1
    
    def record_allowed_request(self, bytes_sent: int = 0, 
                              bytes_received: int = 0) -> None:
        """Record allowed request"""
        self.allowed_requests += 1
        self.total_bytes_sent += bytes_sent
        self.total_bytes_received += bytes_received
    
    def record_blocked_request(self) -> None:
        """Record blocked request"""
        self.blocked_requests += 1
    
    def get_stats(self) -> dict:
        """Get current statistics"""
        return {
            'active_connections': self.active_connections,
            'total_connections': self.total_connections,
            'allowed_requests': self.allowed_requests,
            'blocked_requests': self.blocked_requests,
            'total_bytes_sent': self.total_bytes_sent,
            'total_bytes_received': self.total_bytes_received,
        }
    
    def get_formatted_stats(self) -> str:
        """Get formatted statistics string"""
        stats = self.get_stats()
        return (
            f"Active: {stats['active_connections']} | "
            f"Total: {stats['total_connections']} | "
            f"Allowed: {stats['allowed_requests']} | "
            f"Blocked: {stats['blocked_requests']} | "
            f"Sent: {stats['total_bytes_sent']:,} bytes | "
            f"Received: {stats['total_bytes_received']:,} bytes"
        )
