"""
Network scanning handler
Scans for rsync daemons on the network
"""

import subprocess
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.template_service import TemplateService

class NetworkHandler:
    """Handles network scanning for rsync services"""
    
    def scan_network_for_rsyncd(self, handler, network_range):
        """Scan network range for rsync daemons and return JSON results"""
        try:
            # Parse and validate network range
            network = ipaddress.ip_network(network_range, strict=False)
            host_ips = list(network.hosts())
            
            if len(host_ips) > 254:
                TemplateService.send_json_response(handler, {
                    'error': f'Network range too large ({len(host_ips)} host addresses). Maximum 254 addresses.'
                })
                return
            
            # Scan network
            results = self._scan_hosts(host_ips)
            
            # Return results
            TemplateService.send_json_response(handler, {
                'network_range': network_range,
                'total_checked': len(host_ips),
                'found_servers': len(results),
                'servers': results
            })
            
        except ValueError as e:
            TemplateService.send_json_response(handler, {'error': f'Invalid network range: {str(e)}'})
        except Exception as e:
            TemplateService.send_json_response(handler, {'error': f'Scan failed: {str(e)}'})
    
    def _scan_hosts(self, host_ips):
        """Scan list of IP addresses for rsync services"""
        results = []
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_ip = {
                executor.submit(self._check_rsync_host, str(ip)): str(ip) 
                for ip in host_ips
            }
            
            for future in as_completed(future_to_ip):
                result = future.result()
                if result:
                    results.append(result)
        
        # Sort results by IP address
        results.sort(key=lambda x: ipaddress.ip_address(x['ip']))
        return results
    
    def _check_rsync_host(self, ip_str):
        """Check if a single IP has rsync daemon running"""
        try:
            # Check if port 873 is open
            if not self._is_port_open(ip_str, 873):
                return None
            
            # Port is open, try to get rsync module list
            try:
                cmd = ['rsync', f'{ip_str}::']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout:
                    modules = self._parse_rsync_modules(result.stdout, ip_str)
                    
                    if modules:
                        return {
                            'ip': ip_str,
                            'status': 'found',
                            'modules': modules
                        }
                        
            except subprocess.TimeoutExpired:
                return {'ip': ip_str, 'status': 'timeout'}
            except Exception as e:
                return {'ip': ip_str, 'status': 'error', 'error': str(e)}
                
        except Exception:
            pass
        
        return None
    
    def _is_port_open(self, ip_str, port):
        """Check if port is open on given IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip_str, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _parse_rsync_modules(self, rsync_output, ip_address):
        """Parse rsync module list output"""
        modules = []
        for line in rsync_output.strip().split('\n'):
            if line.strip() and not line.startswith('@'):
                parts = line.split()
                if parts:
                    module_name = parts[0]
                    description = ' '.join(parts[1:]) if len(parts) > 1 else ''
                    modules.append({
                        'name': module_name,
                        'description': description,
                        'path': f'rsync://{ip_address}/{module_name}'
                    })
        return modules
