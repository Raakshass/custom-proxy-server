"""
Proxy Server Implementation
Main proxy server with async I/O, Caching, and Authentication
"""

import asyncio
import sys
from typing import Optional

# Import our modules
from http_parser import HTTPParser, HTTPRequest
from filter_manager import FilterManager, AuthenticationManager
from logger import ProxyLogger, ConnectionTracker
from cache import LRUCache


class ProxyServer:
    """Main proxy server implementation"""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 8888,
                 blacklist_file: Optional[str] = None,
                 auth_file: Optional[str] = None,
                 log_dir: str = 'logs', timeout: int = 30,
                 max_connections: int = 10000,
                 cache_enabled: bool = False):
        """Initialize proxy server"""
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_connections = max_connections
        
        # Initialize components
        self.filter_manager = FilterManager(blacklist_file)
        self.auth_manager = AuthenticationManager(auth_file)
        self.logger = ProxyLogger(log_dir=log_dir)
        self.tracker = ConnectionTracker()
        
        # Initialize Cache
        self.cache_enabled = cache_enabled
        self.cache = LRUCache() if cache_enabled else None
        if self.cache_enabled:
            print("[*] Caching enabled (LRU)")
        
        # Server state
        self.server = None
        self.running = True
    
    async def start(self) -> None:
        """Start the proxy server"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        addr = self.server.sockets[0].getsockname()
        self.logger.log_server_start(addr[0], addr[1])
        print(f"[*] Proxy server listening on {addr[0]}:{addr[1]}")
        
        async with self.server:
            await self.server.serve_forever()
    
    async def handle_client(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> None:
        """Handle incoming client connection"""
        client_addr = writer.get_extra_info('peername')
        client_ip, client_port = client_addr if client_addr else ('unknown', 0)
        
        self.tracker.record_connection_start()
        
        try:
            # Parse HTTP request
            try:
                request = await asyncio.wait_for(
                    HTTPParser.parse_request(reader),
                    timeout=self.timeout
                )
                
                if request[0] is None:
                    # Invalid request
                    return # Silent close for invalid/empty
                
                request_obj, _ = request # Unpack tuple
                request = request_obj    # Use the object
                
            except asyncio.TimeoutError:
                self.logger.log_error('TIMEOUT', client_ip, details='Request parsing timeout')
                return
            except Exception as e:
                self.logger.log_error('PARSE_ERROR', client_ip, details=str(e))
                return
            
            # --- AUTHENTICATION CHECK ---
            auth_header = request.headers.get('Proxy-Authorization')
            if not self.auth_manager.validate(auth_header):
                # Return 407 Proxy Authentication Required
                response = (
                    "HTTP/1.1 407 Proxy Authentication Required\r\n"
                    "Proxy-Authenticate: Basic realm=\"Proxy Server\"\r\n"
                    "Content-Length: 0\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                writer.write(response)
                await writer.drain()
                self.logger.log_request_blocked(client_ip, client_port, "AUTH", "AUTH", "Authentication Failed")
                return

            # Extract target information
            target_host = request.hostname
            target_port = request.port
            
            if not target_host:
                return
            
            # Log request details
            request_line = f"{request.method} {request.target} {request.version}"
            
            # Check filtering rules
            is_blocked, reason = self.filter_manager.is_blocked(target_host)
            
            if is_blocked:
                response = HTTPParser.format_error_response(403, 'Forbidden')
                writer.write(response)
                await writer.drain()
                self.logger.log_request_blocked(
                    client_ip, client_port, target_host, request_line, reason
                )
                self.tracker.record_blocked_request()
                return
            
            # Handle CONNECT method (HTTPS tunneling)
            if request.method.upper() == 'CONNECT':
                await self.handle_connect_tunnel(
                    reader, writer, target_host, target_port,
                    client_ip, client_port, request_line
                )
            else:
                # Handle regular HTTP request
                await self.handle_http_request(
                    reader, writer, request, target_host, target_port,
                    client_ip, client_port, request_line
                )
            
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            
            self.tracker.record_connection_end()
    
    async def handle_http_request(self, reader: asyncio.StreamReader,
                                 client_writer: asyncio.StreamWriter,
                                 request: HTTPRequest,
                                 target_host: str, target_port: int,
                                 client_ip: str, client_port: int,
                                 request_line: str) -> None:
        """Handle regular HTTP request"""
        
        # --- CACHE CHECK (GET only) ---
        if self.cache_enabled and request.method == 'GET':
            cached_resp = self.cache.get(request.target)
            if cached_resp:
                self.logger.log_debug("CACHE_HIT", url=request.target)
                # Reconstruct response
                header_data = cached_resp.headers
                body_data = cached_resp.body
                
                # Send back to client
                client_writer.write(header_data + body_data)
                await client_writer.drain()
                
                self.logger.log_request_allowed(
                    client_ip, client_port, target_host, target_port,
                    request_line + " [CACHE]", status_code=cached_resp.status_code, 
                    bytes_sent=len(body_data)
                )
                return

        try:
            # Connect to upstream server
            try:
                server_reader, server_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port),
                    timeout=self.timeout
                )
            except Exception as e:
                response = HTTPParser.format_error_response(502, 'Bad Gateway')
                client_writer.write(response)
                await client_writer.drain()
                return
            
            try:
                # Format and send request to upstream
                formatted_request = HTTPParser.format_request(request)
                server_writer.write(formatted_request)
                await server_writer.drain()
                
                # Relay response back to client & Capture for Cache
                response_buffer = b""
                header_buffer = b""
                body_buffer = b""
                headers_parsed = False
                
                while True:
                    data = await asyncio.wait_for(
                        server_reader.read(4096),
                        timeout=self.timeout
                    )
                    if not data:
                        break
                    
                    client_writer.write(data)
                    await client_writer.drain()
                    
                    # Buffer for caching
                    if self.cache_enabled and request.method == 'GET':
                        response_buffer += data
                        
                        # Try to split headers/body if not done yet
                        if not headers_parsed and b"\r\n\r\n" in response_buffer:
                            parts = response_buffer.split(b"\r\n\r\n", 1)
                            header_buffer = parts[0] + b"\r\n\r\n"
                            if len(parts) > 1:
                                body_buffer = parts[1]
                            headers_parsed = True
                        elif headers_parsed:
                            body_buffer += data

                # --- SAVE TO CACHE ---
                if self.cache_enabled and request.method == 'GET' and headers_parsed:
                    # Simple check: only cache 200 OK
                    if b"200 OK" in header_buffer:
                        self.cache.put(request.target, 200, header_buffer, body_buffer)
                        self.logger.log_debug("CACHE_MISS_STORED", url=request.target)

                # Log successful request
                self.logger.log_request_allowed(
                    client_ip, client_port, target_host, target_port,
                    request_line, status_code=200, bytes_sent=len(response_buffer)
                )
                self.tracker.record_allowed_request(bytes_received=len(response_buffer))
                
            finally:
                try:
                    server_writer.close()
                    await server_writer.wait_closed()
                except Exception:
                    pass
        
        except Exception as e:
            self.logger.log_error('HTTP_HANDLER_ERROR', client_ip, target_host, str(e)[:100])
    
    async def handle_connect_tunnel(self, reader: asyncio.StreamReader,
                                   writer: asyncio.StreamWriter,
                                   target_host: str, target_port: int,
                                   client_ip: str, client_port: int,
                                   request_line: str) -> None:
        """Handle HTTPS CONNECT tunneling"""
        try:
            # Connect to upstream server
            try:
                server_reader, server_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port),
                    timeout=self.timeout
                )
            except Exception:
                response = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
                writer.write(response)
                await writer.drain()
                return
            
            try:
                # Send "200 Connection Established" to client
                response = b"HTTP/1.1 200 Connection Established\r\n\r\n"
                writer.write(response)
                await writer.drain()
                
                # Create bidirectional tunnel
                await asyncio.gather(
                    self._forward_data(reader, server_writer, client_ip, True),
                    self._forward_data(server_reader, writer, client_ip, False)
                )
                
                self.logger.log_request_allowed(
                    client_ip, client_port, target_host, target_port,
                    request_line, status_code=200
                )
                self.tracker.record_allowed_request()
                
            finally:
                try:
                    server_writer.close()
                    await server_writer.wait_closed()
                except Exception:
                    pass
        
        except Exception as e:
            self.logger.log_error('CONNECT_HANDLER_ERROR', client_ip, target_host, str(e)[:100])
    
    async def _forward_data(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter,
                           client_ip: str, from_client: bool) -> None:
        """Forward data between client and server"""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HTTP/HTTPS Proxy Server')
    parser.add_argument('--host', default='127.0.0.1', help='Listen address')
    parser.add_argument('--port', type=int, default=8888, help='Listen port')
    parser.add_argument('--blacklist', help='Path to blacklist file')
    parser.add_argument('--auth-file', help='Path to users file for authentication')
    parser.add_argument('--cache', action='store_true', help='Enable LRU Caching')
    parser.add_argument('--log-dir', default='logs', help='Log directory')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout')
    parser.add_argument('--max-connections', type=int, default=10000,
                       help='Max concurrent connections')
    
    args = parser.parse_args()
    
    # Create and start server
    server = ProxyServer(
        host=args.host,
        port=args.port,
        blacklist_file=args.blacklist,
        auth_file=args.auth_file,
        cache_enabled=args.cache,
        log_dir=args.log_dir,
        timeout=args.timeout,
        max_connections=args.max_connections
    )
    
    # Display stats periodically
    async def print_stats():
        while server.running:
            await asyncio.sleep(60)
            stats = server.tracker.get_formatted_stats()
            print(f"\n[*] {stats}")
    
    try:
        await asyncio.gather(
            server.start(),
            print_stats()
        )
    except KeyboardInterrupt:
        print("\n[*] Server shutting down...")
        server.running = False
        server.logger.log_server_stop()


if __name__ == '__main__':
    asyncio.run(main())
