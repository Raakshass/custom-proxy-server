"""
Filter Manager Module
Handles domain/IP blacklist filtering and Authentication
"""

import ipaddress
import base64
from typing import Set, Tuple, Optional, Dict


class FilterManager:
    """Manages filtering rules for domains and IPs"""
    
    def __init__(self, blacklist_file: Optional[str] = None):
        """Initialize filter manager"""
        self.blocked_domains: Set[str] = set()
        self.blocked_domain_suffixes: Set[str] = set()
        self.blocked_ips: Set[str] = set()
        self.blocked_ip_ranges: list = []
        
        if blacklist_file:
            self.load_blacklist(blacklist_file)
    
    def load_blacklist(self, blacklist_file: str) -> None:
        """Load blacklist from file"""
        try:
            with open(blacklist_file, 'r') as f:
                for line in f:
                    # Remove comments and whitespace
                    line = line.split('#')[0].strip()
                    if not line:
                        continue
                    
                    self._add_rule(line)
        except FileNotFoundError:
            print(f"Warning: Blacklist file not found: {blacklist_file}")
        except Exception as e:
            print(f"Error loading blacklist: {e}")
    
    def _add_rule(self, rule: str) -> None:
        """Add a single rule to the filter"""
        rule = rule.lower().strip()
        
        # Try to parse as IP address or CIDR range
        if '/' in rule:
            # CIDR range
            try:
                network = ipaddress.ip_network(rule, strict=False)
                self.blocked_ip_ranges.append(network)
                return
            except ValueError:
                pass
        
        try:
            # Individual IP address
            ipaddress.ip_address(rule)
            self.blocked_ips.add(rule)
            return
        except ValueError:
            pass
        
        # Domain name
        if rule.startswith('*.'):
            # Wildcard domain (suffix match)
            self.blocked_domain_suffixes.add(rule[2:])  # Remove '*.'
        else:
            # Exact domain match
            self.blocked_domains.add(rule)
    
    def is_blocked(self, host: str) -> Tuple[bool, str]:
        """Check if host is blocked"""
        # Separate host and port
        hostname = host.split(':')[0] if ':' in host else host
        hostname = hostname.lower().strip()
        
        # Check exact IP match
        if hostname in self.blocked_ips:
            return True, f"IP {hostname} is blacklisted"
        
        # Check CIDR ranges
        try:
            ip_obj = ipaddress.ip_address(hostname)
            for cidr_range in self.blocked_ip_ranges:
                if ip_obj in cidr_range:
                    return True, f"IP {hostname} is in blocked range {cidr_range}"
        except ValueError:
            pass  # Not an IP address
        
        # Check exact domain match
        if hostname in self.blocked_domains:
            return True, f"Domain {hostname} is blacklisted"
        
        # Check domain suffix match (*.example.com blocks sub.example.com)
        for suffix in self.blocked_domain_suffixes:
            if hostname == suffix or hostname.endswith('.' + suffix):
                return True, f"Domain {hostname} matches blocked pattern *.{suffix}"
        
        return False, "Not blocked"


class AuthenticationManager:
    """Manages proxy authentication"""
    
    def __init__(self, credentials_file: Optional[str] = None):
        """
        Initialize authentication manager
        Args:
            credentials_file: Path to file with 'username:password' lines
        """
        self.users: Dict[str, str] = {}
        self.enabled = False
        
        if credentials_file:
            self.load_credentials(credentials_file)
            
    def load_credentials(self, filepath: str) -> None:
        """Load credentials from file"""
        try:
            with open(filepath, 'r') as f:
                count = 0
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if ':' in line:
                            user, pw = line.split(':', 1)
                            self.users[user.strip()] = pw.strip()
                            count += 1
                
                if count > 0:
                    self.enabled = True
                    print(f"[*] Loaded {count} users for authentication")
        except FileNotFoundError:
            print(f"Warning: Auth file not found: {filepath}")
            
    def validate(self, auth_header: Optional[str]) -> bool:
        """
        Validate Proxy-Authorization header
        Header format: 'Basic <base64(user:pass)>'
        """
        if not self.enabled:
            return True  # Allow everyone if auth is disabled
            
        if not auth_header or not auth_header.startswith('Basic '):
            return False
            
        try:
            # Decode base64
            encoded = auth_header.split(' ')[1]
            decoded = base64.b64decode(encoded).decode('utf-8')
            
            if ':' not in decoded:
                return False
                
            username, password = decoded.split(':', 1)
            
            # Check against loaded users
            if username in self.users and self.users[username] == password:
                return True
                
            return False
            
        except Exception:
            return False
