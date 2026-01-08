# High-Performance Asynchronous Network Proxy Server

## Demonstration - https://www.youtube.com/watch?v=h0mR5jPNbz8

## Overview

This project implements a production-grade forward proxy server in Python, designed to handle high-throughput HTTP and HTTPS traffic. The system handles traffic interception, inspection, and forwarding using a non-blocking, event-driven architecture based on Python's `asyncio` library.

Beyond basic traffic forwarding, the server implements an advanced feature set including a Least Recently Used (LRU) caching layer to optimize bandwidth, a robust Access Control List (ACL) system for domain and IP filtering, and Basic Authentication for security. The codebase is modular, type-hinted, and follows strict separation of concerns, making it suitable for academic analysis or extension into production environments.

## System Architecture

### Concurrency Model: Event-Driven I/O
The server rejects the traditional thread-per-connection or process-per-connection models, which suffer from high memory overhead and context-switching latency. Instead, it utilizes a single-threaded event loop.

*   **Mechanism**: Uses `asyncio` streams to handle network I/O.
*   **Scalability**: Capable of maintaining 10,000+ concurrent idle connections with approximately 1KB memory overhead per connection.
*   **Performance**: Non-blocking socket operations ensure that slow upstream servers do not block the processing of other client requests.

### Request Processing Pipeline
Data flows through the system in distinct stages:
1.  **Ingestion**: The `ProxyServer` accepts a TCP connection and delegates it to a client handler coroutine.
2.  **Parsing**: The `HTTPParser` reads the byte stream, extracting the Request Line (Method, URI, Version) and Headers. It handles both absolute URIs (common in proxy requests) and relative URIs.
3.  **Security & Control**:
    *   **Authentication**: The `AuthenticationManager` validates the `Proxy-Authorization` header against the credential store.
    *   **Filtering**: The `FilterManager` checks the destination host against the Access Control List (ACL).
4.  **Strategy Selection**:
    *   **Cache Hit**: If caching is enabled and the request is a `GET`, the `LRUCache` is queried.
    *   **HTTPS (CONNECT)**: A blind TCP tunnel is established for TLS traffic.
    *   **HTTP (Forward)**: The request is normalized and forwarded to the upstream server.
5.  **Response Handling**: Responses are streamed back to the client in 4KB chunks to minimize memory pressure.

## Features and Capabilities

### 1. Protocol Support
*   **HTTP/1.1 Forwarding**: Full parsing of headers and bodies. Handles `Content-Length` correctly to support POST/PUT payloads.
*   **HTTPS Tunneling**: Implements the HTTP `CONNECT` method to establish transparent TCP tunnels, allowing encrypted TLS traffic to pass through without decryption (preserving end-to-end encryption).

### 2. Traffic Control (ACL)
The filtering engine supports three distinct matching strategies:
*   **Exact Domain Match**: Blocks specific domains (e.g., `example.com`).
*   **Wildcard Suffix Match**: Recursively blocks subdomains using `*.pattern` (e.g., `*.ads.com` blocks `server1.ads.com`).
*   **CIDR IP Filtering**: Parses and blocks entire IP subnets (e.g., `192.168.0.0/24`) using the `ipaddress` module.

### 3. Caching Strategy
To reduce latency and upstream load, the server implements an in-memory LRU Cache.
*   **Key Generation**: Responses are indexed by the full request URI.
*   **Eviction Policy**: When the configured memory limit is reached, the least recently accessed items are discarded.
*   **Thread Safety**: Operations are atomic to ensure consistency during concurrent access.

### 4. Observability
A structured logging system records all system activity:
*   **Access Logs**: Detailed records of client IP, target, method, status code, and transfer size.
*   **Rotation**: Logs are automatically rotated based on size limits to prevent disk exhaustion.
*   **Statistics**: Real-time tracking of active connections, total bytes transferred, and block/allow ratios.

## Directory Structure

```text
proxy-project/
├── src/
│   ├── proxy_server.py    # Main entry point; manages the asyncio event loop and connection lifecycle.
│   ├── http_parser.py     # Protocol-compliant HTTP request parsing and raw byte generation.
│   ├── filter_manager.py  # Logic for ACL enforcement and Authentication validation.
│   ├── cache.py           # Implementation of the LRU caching data structure.
│   └── logger.py          # Configuration for rotating file logs and console output.
├── config/
│   ├── blocked_domains.txt # Plain text rules for domain and IP blocking.
│   └── users.txt           # Credential store (username:password) for authentication.
├── tests/                 # Automated test suite.
├── logs/                  # Runtime log storage.
└── run.bat                # Windows automation script for building and testing.
```
Setup and Configuration
Prerequisites
Python 3.8+ (No external dependencies required for core functionality).

Configuration Files
Blocklist (config/blocked_domains.txt):

text
# Comments are supported
example.com          # Exact match
*.tracker.com        # Wildcard match
10.0.0.0/8           # CIDR range
Credentials (config/users.txt):

text
admin:secret123
user:password
Execution
The server is configurable via command-line arguments.

Windows (using helper script):

powershell
.\run.bat start    # Starts server with default settings
.\run.bat test     # Runs the integration test suite
Manual Start (Full Options):

bash
python src/proxy_server.py \
    --host 0.0.0.0 \
    --port 8888 \
    --blacklist config/blocked_domains.txt \
    --auth-file config/users.txt \
    --cache \
    --log-dir logs \
    --max-connections 5000
Verification and Testing
Automated Testing
The project includes a comprehensive integration test suite (tests/test_manual.py) that verifies:

Standard HTTP forwarding.

HTTPS Tunneling (CONNECT).

Access Control enforcement (403 Forbidden).

Authentication challenges (407 Proxy Authentication Required).

Manual cURL Examples
1. Authenticated Request with Caching:

bash
curl -v -x http://admin:secret123@127.0.0.1:8888 http://httpbin.org/get
2. HTTPS Secure Tunnel:

bash
curl -v -x http://127.0.0.1:8888 https://www.google.com
3. Verification of Blocking:

bash
# Assuming 'example.com' is in blocked_domains.txt
curl -x http://127.0.0.1:8888 http://example.com
# Returns: 403 Forbidden
License
This software is provided for educational and evaluation purposes.

text
undefined
