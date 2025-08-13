"""
Command builder factory
Routes backup jobs to appropriate command builders based on destination type
"""
from .backup_command_builder import BackupCommandBuilder
from .restic_command_builder import ResticCommandBuilder


class CommandBuilderFactory:
    """Factory for creating appropriate command builders"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self._builders = {}
    
    def get_builder(self, dest_type):
        """Get appropriate command builder for destination type"""
        if dest_type not in self._builders:
            if dest_type == 'restic':
                self._builders[dest_type] = ResticCommandBuilder(self.backup_config)
            else:
                # Default to rsync builder for ssh, local, rsyncd
                self._builders[dest_type] = BackupCommandBuilder(self.backup_config)
        
        return self._builders[dest_type]
    
    def build_command(self, job_config, job_name, dry_run):
        """
        Build backup command using appropriate builder.
        Returns CommandInfo with exec_argv, log_cmd_str, src_display, dst_display.
        """
        dest_type = job_config.get('dest_type', '')
        builder = self.get_builder(dest_type)
        
        if dest_type == 'restic':
            return builder.build_restic_command(job_config, job_name, dry_run)
        else:
            return builder.build_rsync_command(job_config, job_name, dry_run)