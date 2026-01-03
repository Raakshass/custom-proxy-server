"""
Manual Test Script for Proxy Server
Run this to test the proxy functionality
"""

import subprocess
import time
import sys

# ANSI color codes for Windows/Unix
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_test(name):
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print(f"{'='*60}")

def print_pass(msg):
    print(f"{GREEN}✓ PASS{RESET}: {msg}")

def print_fail(msg):
    print(f"{RED}✗ FAIL{RESET}: {msg}")

def print_info(msg):
    print(f"{YELLOW}→{RESET} {msg}")

def run_curl(url, should_succeed=True):
    """Run curl command through proxy"""
    cmd = ['curl.exe', '-x', 'http://127.0.0.1:8888', url, '-s', '-o', 'nul', '-w', '%{http_code}']
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        status_code = result.stdout.strip()
        
        print_info(f"Request: {url}")
        print_info(f"Status: {status_code}")
        
        if should_succeed and status_code == '200':
            print_pass(f"Request succeeded with 200 OK")
            return True
        elif not should_succeed and status_code == '403':
            print_pass(f"Request blocked with 403 Forbidden")
            return True
        else:
            print_fail(f"Expected {'200' if should_succeed else '403'}, got {status_code}")
            return False
    except subprocess.TimeoutExpired:
        print_fail("Request timed out")
        return False
    except FileNotFoundError:
        print_fail("curl.exe not found. Using Python fallback...")
        return run_curl_python(url, should_succeed)
    except Exception as e:
        print_fail(f"Error: {str(e)}")
        return False

def run_curl_python(url, should_succeed=True):
    """Fallback: Use Python urllib instead of curl"""
    import urllib.request
    import urllib.error
    
    try:
        proxy_handler = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:8888', 'https': 'http://127.0.0.1:8888'})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)
        
        response = urllib.request.urlopen(url, timeout=10)
        status_code = response.getcode()
        
        print_info(f"Request: {url}")
        print_info(f"Status: {status_code}")
        
        if should_succeed and status_code == 200:
            print_pass(f"Request succeeded with 200 OK")
            return True
        else:
            print_fail(f"Unexpected status: {status_code}")
            return False
    except urllib.error.HTTPError as e:
        if not should_succeed and e.code == 403:
            print_pass(f"Request blocked with 403 Forbidden")
            return True
        else:
            print_fail(f"HTTP Error: {e.code}")
            return False
    except Exception as e:
        print_fail(f"Error: {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("PROXY SERVER TEST SUITE")
    print("="*60)
    print("\nMake sure proxy server is running on 127.0.0.1:8888")
    print("Press Enter to continue...")
    input()
    
    results = []
    
    # Test 1: Simple HTTP request
    print_test("1. Simple HTTP Request")
    results.append(run_curl('http://httpbin.org/get', should_succeed=True))
    time.sleep(1)
    
    # Test 2: HTTPS request (CONNECT)
    print_test("2. HTTPS Request (CONNECT Tunneling)")
    results.append(run_curl('https://httpbin.org/get', should_succeed=True))
    time.sleep(1)
    
    # Test 3: Blocked domain - example.com
    print_test("3. Blocked Domain - example.com")
    results.append(run_curl('http://example.com', should_succeed=False))
    time.sleep(1)
    
    # Test 4: Blocked domain - facebook.com
    print_test("4. Blocked Domain - facebook.com")
    results.append(run_curl('http://facebook.com', should_succeed=False))
    time.sleep(1)
    
    # Test 5: Another allowed site
    print_test("5. Another Allowed Site - httpbin.org/status/200")
    results.append(run_curl('http://httpbin.org/status/200', should_succeed=True))
    time.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {GREEN}{passed}{RESET}/{total}")
    print(f"Failed: {RED}{total - passed}{RESET}/{total}")
    
    if passed == total:
        print(f"\n{GREEN}✓ All tests passed!{RESET}")
        return 0
    else:
        print(f"\n{RED}✗ Some tests failed{RESET}")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
