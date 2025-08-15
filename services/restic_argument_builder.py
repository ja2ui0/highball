"""
Restic argument builder for different command types
Handles command-specific argument construction with consistent patterns
"""
from typing import Dict, List, Optional


class ResticArgumentBuilder:
    """Builds arguments for different Restic command types"""
    
    @staticmethod
    def build_backup_args(job_config: Dict) -> List[str]:
        """Build arguments for backup command"""
        args = []
        
        # Add JSON output for parsing
        args.append('--json')
        
        # Add tags
        tags = job_config.get('tags', [])
        for tag in tags:
            args.extend(['--tag', tag])
        
        # Add exclude patterns
        excludes = job_config.get('exclude_patterns', [])
        for pattern in excludes:
            args.extend(['--exclude', pattern])
        
        # Add verbose output if requested
        if job_config.get('verbose', True):  # Default to verbose for better logging
            args.append('--verbose')
        
        return args
    
    @staticmethod
    def build_restore_args(restore_config: Dict) -> List[str]:
        """Build arguments for restore command"""
        args = []
        
        # Add snapshot ID first (must come immediately after 'restore' command)
        snapshot_id = restore_config.get('snapshot_id', 'latest')
        if snapshot_id:
            args.append(snapshot_id)
        
        # Add target directory
        restore_target = restore_config.get('restore_target', 'highball')
        if restore_target == 'highball':
            args.extend(['--target', '/restore'])
        elif restore_target == 'source':
            # For restore-to-source, restore to root and let mount mapping handle the paths
            args.extend(['--target', '/'])
        
        # Add selected paths (for granular restore)
        if not restore_config.get('select_all', False):
            selected_paths = restore_config.get('selected_paths', [])
            for path in selected_paths:
                if path.strip():
                    args.extend(['--include', path])
        
        # Add dry run flag
        if restore_config.get('dry_run', False):
            args.append('--dry-run')
        
        # Add JSON output for progress tracking (not for dry runs)
        if not restore_config.get('dry_run', False):
            args.append('--json')
        
        return args
    
    @staticmethod
    def build_retention_args(retention: Dict) -> List[str]:
        """Build arguments for retention policy (forget command)"""
        args = ['--prune']  # Auto-prune when forgetting
        
        if 'keep_daily' in retention:
            args.extend(['--keep-daily', str(retention['keep_daily'])])
        if 'keep_weekly' in retention:
            args.extend(['--keep-weekly', str(retention['keep_weekly'])])
        if 'keep_monthly' in retention:
            args.extend(['--keep-monthly', str(retention['keep_monthly'])])
        if 'keep_yearly' in retention:
            args.extend(['--keep-yearly', str(retention['keep_yearly'])])
        
        return args
    
    @staticmethod
    def adjust_args_for_container(args: List[str]) -> List[str]:
        """
        Adjust arguments for container execution (update paths)
        
        This handles path adjustments needed when running inside containers
        where the filesystem layout may differ from the host.
        """
        if not args:
            return []
        
        adjusted = []
        i = 0
        while i < len(args):
            arg = args[i]
            
            # Adjust target path for restore operations  
            if arg == '--target' and i + 1 < len(args):
                adjusted.append('--target')
                target_path = args[i + 1]
                # For restore-to-source, keep target as '/' (mounted paths handle specificity)
                # For restore-to-highball, use '/restore-target'
                if target_path == '/':
                    adjusted.append('/')
                else:
                    adjusted.append('/restore-target')
                i += 2
            # Keep include paths as-is (they reference backup content paths)
            elif arg == '--include' and i + 1 < len(args):
                adjusted.append('--include')
                adjusted.append(args[i + 1])
                i += 2
            else:
                adjusted.append(arg)
                i += 1
        
        return adjusted
    
    @staticmethod
    def extract_target_from_args(args: List[str]) -> str:
        """Extract target directory from restore arguments"""
        if not args:
            return ""
        
        try:
            target_idx = args.index('--target')
            if target_idx + 1 < len(args):
                return args[target_idx + 1]
        except ValueError:
            pass
        
        return ""
    
    @staticmethod
    def extract_snapshot_id_from_args(args: List[str]) -> str:
        """Extract snapshot ID from restore arguments"""
        if not args:
            return ""
        
        # First argument after 'restore' command is snapshot ID
        for arg in args:
            if arg not in ['--target', '--include', '--exclude', '--dry-run', '--json'] and not arg.startswith('-'):
                return arg
        
        return ""