/**
 * Restore Restic Provider - Restic-specific restore implementation
 * Handles Restic restore validation, request building, and response processing
 */

document.addEventListener('DOMContentLoaded', function() {
    // Register this provider with the core restore system
    if (window.RestoreCore) {
        window.RestoreCore.registerRestoreProvider('restic', ResticRestoreProvider);
    }
});

const ResticRestoreProvider = {
    needsPassword: function() {
        return true; // Restic always needs password for restore operations
    },
    
    validateRestoreRequest: function(config) {
        // Validate Restic-specific restore requirements
        if (!config.select_all && !config.snapshot_id) {
            return {
                valid: false,
                error: 'Please select a snapshot first'
            };
        }
        
        if (!config.select_all && config.selected_paths.length === 0) {
            return {
                valid: false,
                error: 'Please select files/folders to restore or use "Select All" option'
            };
        }
        
        return { valid: true };
    },
    
    buildRestoreRequest: function(config) {
        // Use multipart form data for better array handling and security
        const formData = new FormData();
        formData.append('job_name', config.job_name);
        formData.append('snapshot_id', config.snapshot_id);
        formData.append('restore_target', config.restore_target);
        
        if (config.dry_run) {
            formData.append('dry_run', 'on');
        }
        
        if (config.select_all) {
            formData.append('select_all', 'on');
        }
        
        if (config.password) {
            formData.append('password', config.password);
        }
        
        // Add selected paths for granular restore
        config.selected_paths.forEach(path => {
            formData.append('selected_paths', path);
        });
        
        return formData;
    },
    
    buildRestoreSummary: function(config) {
        // Build HTML summary for password confirmation modal
        const restoreType = config.select_all 
            ? 'Full snapshot restore' 
            : `${config.selected_paths.length} selected items`;
            
        const snapshot = config.select_all 
            ? 'Latest snapshot' 
            : config.snapshot_id;
            
        return `
            <div><strong>Job:</strong> ${config.job_name}</div>
            <div><strong>Snapshot:</strong> ${snapshot}</div>
            <div><strong>Restore type:</strong> ${restoreType}</div>
            <div><strong>Target:</strong> /restore (in Highball container)</div>
            <div><strong>Provider:</strong> Restic</div>
        `;
    },
    
    handleDryRunResponse: function(result) {
        // Handle dry run response from server
        if (result.success) {
            // Simple success message - detailed output is already in the logs
            window.RestoreCore.showAlert('Dry run completed successfully!', true);
        } else {
            window.RestoreCore.showAlert(`Dry run failed: ${result.error}`);
        }
    },
    
    handleRestoreResponse: function(result, config) {
        // Handle actual restore response and start progress monitoring
        if (result.success) {
            this.startProgressMonitoring(config.job_name);
        } else {
            window.RestoreCore.hideProgressModal();
            window.RestoreCore.showAlert(`Restore failed: ${result.error}`);
        }
    },
    
    startProgressMonitoring: function(jobName) {
        // Start monitoring Restic restore progress
        window.RestoreCore.showProgressModal('Restic restore in progress...', 0);
        
        // TODO: Implement actual progress polling endpoint
        // For now, simulate progress for demonstration
        this.simulateResticProgress(jobName);
    },
    
    simulateResticProgress: function(jobName) {
        // Simulated progress - replace with actual polling later
        let progress = 0;
        const phases = [
            'Initializing restore...',
            'Verifying snapshot...',
            'Restoring files...',
            'Finalizing restore...',
            'Restore completed!'
        ];
        
        let phaseIndex = 0;
        const interval = setInterval(() => {
            progress += 20;
            
            if (phaseIndex < phases.length) {
                window.RestoreCore.showProgressModal(phases[phaseIndex], progress);
                phaseIndex++;
            }
            
            if (progress >= 100) {
                clearInterval(interval);
                window.RestoreCore.showProgressModal('Restic restore completed!', 100);
                const closeButton = document.getElementById('closeProgress');
                if (closeButton) {
                    closeButton.style.display = 'block';
                }
                
                // Optionally refresh job status or logs
                this.refreshJobStatus(jobName);
            }
        }, 1500);
    },
    
    refreshJobStatus: function(jobName) {
        // Refresh job status after restore completion
        // Could trigger a refresh of the job status section
        setTimeout(() => {
            const refreshButton = document.getElementById('refreshLogs');
            if (refreshButton) {
                // Trigger log refresh to show restore completion
                refreshButton.click();
            }
        }, 1000);
    },
    
    // Future: Real progress polling implementation
    pollRestoreProgress: function(jobName) {
        // This would make periodic requests to /restore-progress?job=<jobName>
        // and parse JSON progress responses from restic --json output
        // Implementation would go here when we add the progress endpoint
    }
};