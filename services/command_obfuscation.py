"""
Command obfuscation utilities
Centralized functions for hiding sensitive information in command logging
"""
from typing import List, Optional


def obfuscate_password_in_command(command: List[str], password: Optional[str] = None) -> List[str]:
    """Replace password in command with asterisks for logging using simple string replacement"""
    safe_command = []
    
    for arg in command:
        safe_arg = arg
        
        # If we have the actual password value, do simple string replacement
        if password and password in arg:
            safe_arg = arg.replace(password, '***')
        
        safe_command.append(safe_arg)
            
    return safe_command


def obfuscate_password_in_list(args: List[str], password: Optional[str] = None) -> List[str]:
    """Replace password in argument list with asterisks for logging"""
    if not args:
        return []
    return obfuscate_password_in_command(args, password)