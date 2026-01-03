"""
HTTP Request/Response Parser Module
Handles parsing of HTTP requests and responses
"""

import re
from typing import Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP request"""
    method: str
    target: str
    version: str
    headers: Dict[str, str]
    body: bytes = b''
    
    @property
    def host(self) -> Optional[str]:
        """Extract host from request"""
        # First try to get from absolute URI
        if self.target.startswith('http://') or self.target.startswith('https://'):
            match = re.match(r'https?://([^/]+)', self.target)
            if match:
                return match.group(1)
        
        # Fall back to Host header
        return self.headers.get('host') or self.headers.get('Host')
    
    @property
    def port(self) -> int:
        """Extract port from request"""
        # Check if port is in target (for absolute URIs)
        if self.target.startswith('http://') or self.target.startswith('https://'):
            match = re.match(r'https?://([^/:]+):(\d+)', self.target)
            if match:
                return int(match.group(2))
        
        # Default based on method
        if self.method.upper() == 'CONNECT':
            # CONNECT host:port format
            if ':' in self.target:
                try:
                    return int(self.target.split(':')[1])
                except (ValueError, IndexError):
                    return 443
            return 443
        
        # Default HTTP/HTTPS ports
        if self.target.startswith('https://'):
            return 443
        return 80
    
    @property
    def hostname(self) -> Optional[str]:
        """Extract hostname without port"""
        host = self.host
        if not host:
            return None
        # Remove port if present
        return host.split(':')[0] if ':' in host else host
    
    def get_target_for_upstream(self) -> str:
        """Get target suitable for upstream server (relative path)"""
        if self.method.upper() == 'CONNECT':
            return self.target
        
        # If absolute URI, convert to relative path
        if self.target.startswith('http://') or self.target.startswith('https://'):
            match = re.match(r'https?://[^/]+(/.*)', self.target)
            if match:
                return match.group(1)
            return '/'
        return self.target


class HTTPParser:
    """Parser for HTTP requests and responses"""
    
    MAX_HEADER_SIZE = 8192  # 8KB max header size
    MAX_LINE_SIZE = 4096    # 4KB max line size
    
    @staticmethod
    async def parse_request(reader) -> Tuple[Optional[HTTPRequest], bytes]:
        """
        Parse HTTP request from asyncio StreamReader
        
        Returns:
            Tuple of (HTTPRequest, remaining_data)
        """
        try:
            # Read until header terminator
            raw_request = await reader.readuntil(b'\r\n\r\n')
            header_data = raw_request[:-4]  # Remove \r\n\r\n
            
            lines = header_data.split(b'\r\n')
            if not lines:
                return None, b''
            
            # Parse request line
            request_line = lines[0].decode('utf-8', errors='ignore').strip()
            parts = request_line.split()
            
            if len(parts) < 2:
                return None, b''
            
            method = parts[0].upper()
            target = parts[1]
            version = parts[2] if len(parts) > 2 else 'HTTP/1.1'
            
            # Parse headers
            headers = {}
            for line in lines[1:]:
                if not line:
                    break
                header_str = line.decode('utf-8', errors='ignore')
                if ':' in header_str:
                    key, value = header_str.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Get Content-Length if present
            content_length = 0
            for key in headers:
                if key.lower() == 'content-length':
                    try:
                        content_length = int(headers[key])
                    except ValueError:
                        pass
                    break
            
            # Read body if present
            body = b''
            if content_length > 0:
                body = await reader.readexactly(content_length)
            
            request = HTTPRequest(
                method=method,
                target=target,
                version=version,
                headers=headers,
                body=body
            )
            
            return request, b''
            
        except Exception as e:
            return None, b''
    
    @staticmethod
    def format_request(request: HTTPRequest) -> bytes:
        """Format HTTPRequest back to bytes for sending to upstream server"""
        # Use relative target for upstream
        target = request.get_target_for_upstream()
        
        # Build request line
        request_line = f"{request.method} {target} {request.version}\r\n"
        
        # Build headers
        header_lines = request_line
        for key, value in request.headers.items():
            header_lines += f"{key}: {value}\r\n"
        
        header_lines += "\r\n"
        
        # Combine headers and body
        return header_lines.encode() + request.body
    
    @staticmethod
    def format_error_response(status_code: int, reason: str = '') -> bytes:
        """Format HTTP error response"""
        status_map = {
            400: 'Bad Request',
            403: 'Forbidden',
            404: 'Not Found',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout',
        }
        
        reason = reason or status_map.get(status_code, 'Error')
        
        html_body = f'''<!DOCTYPE html>
<html>
<head>
    <title>{status_code} {reason}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        p {{ color: #666; }}
    </style>
</head>
<body>
    <h1>{status_code} {reason}</h1>
    <p>The proxy server encountered an error processing your request.</p>
</body>
</html>'''
        
        response = f"HTTP/1.1 {status_code} {reason}\r\n"
        response += f"Content-Type: text/html\r\n"
        response += f"Content-Length: {len(html_body)}\r\n"
        response += f"Connection: close\r\n"
        response += f"\r\n"
        
        return response.encode() + html_body.encode()
