/**
 * Job Inspect Page JavaScript (HTMX-enabled)
 * Handles restore controls and overwrite checking - log management migrated to HTMX
 */

class JobInspectManager {
    constructor(jobName) {
        this.jobName = jobName;
        this.restoreControls = null;
        this.selectAllToggle = null;
        this.selectionPane = null;
        
        this.init();
    }
    
    init() {
        // Get DOM elements (log elements removed - handled by HTMX)
        this.restoreControls = document.getElementById('restoreControls');
        this.selectAllToggle = document.getElementById('selectAllToggle');
        this.selectionPane = document.getElementById('selectionPane');
        
        // Setup backup browser integration
        this.setupBackupBrowserIntegration();
        
        // Auto-load backup job when page loads
        window.addEventListener('load', () => {
            if (window.loadBackupJob) {
                window.loadBackupJob();
            }
        });
        
        // Make functions globally available for restore system
        window.checkOverwriteRisk = this.checkOverwriteRisk.bind(this);
        window.checkForOverwrites = this.checkForOverwrites.bind(this);
    }
    
    setupBackupBrowserIntegration() {
        // Override the global selection update function for restore integration
        window.originalUpdateSelectionDisplay = window.updateSelectionDisplay || function() {};
        window.updateSelectionDisplay = () => {
            window.originalUpdateSelectionDisplay();
            
            // Clear validation errors when items are selected
            const hasSelections = document.querySelectorAll('.tree-item input[type="checkbox"]:checked').length > 0;
            if (hasSelections) {
                this.clearRestoreValidationError();
            }
            
            // Check for overwrites whenever selection changes
            this.checkOverwriteRisk();
        };
    }
    
    // Restore Controls
    toggleMode() {
        const modeToggle = document.getElementById('modeToggle');
        
        if (modeToggle && this.restoreControls) {
            if (modeToggle.classList.contains('left')) {
                // Switch to Restore mode
                modeToggle.classList.remove('left');
                modeToggle.classList.add('right');
                this.restoreControls.classList.remove('hidden');
            } else {
                // Switch to View mode
                modeToggle.classList.remove('right');
                modeToggle.classList.add('left');
                this.restoreControls.classList.add('hidden');
            }
        }
    }
    
    toggleSelectAll() {
        if (!this.selectAllToggle || !this.selectionPane) return;
        
        const isChecked = this.selectAllToggle.checked;
        
        if (isChecked) {
            // Grey out selection pane when Select All is active
            this.selectionPane.style.opacity = '0.5';
            this.selectionPane.style.pointerEvents = 'none';
            // Clear any validation errors since we now have a selection
            this.clearRestoreValidationError();
        } else {
            // Re-enable selection pane
            this.selectionPane.style.opacity = '1';
            this.selectionPane.style.pointerEvents = 'auto';
        }
        
        // Check for overwrites when Select All changes
        this.checkOverwriteRisk();
    }
    
    clearRestoreValidationError() {
        const errorDiv = document.getElementById('restoreValidationError');
        if (errorDiv) {
            errorDiv.classList.add('hidden');
        }
    }
    
    togglePasswordField() {
        // This function name is kept for compatibility, but now it handles confirmation
        this.checkOverwriteRisk();
    }
    
    handleRestoreTargetChange() {
        this.checkOverwriteRisk();
    }
    
    // Overwrite Detection System
    async checkOverwriteRisk() {
        const dryRunToggle = document.getElementById('dryRunToggle');
        const overwriteWarning = document.getElementById('overwriteWarning');
        const confirmationSection = document.getElementById('confirmationSection');
        
        if (!dryRunToggle || !overwriteWarning || !confirmationSection) return;
        
        // Hide confirmation elements by default
        overwriteWarning.classList.add('hidden');
        confirmationSection.classList.add('hidden');
        
        // ALWAYS check for overwrites - warn user regardless of dry run state
        const overwriteRisk = await this.checkForOverwrites();
        if (overwriteRisk.hasOverwrites) {
            // Always show warning with appropriate message
            const warningText = document.getElementById('overwriteWarningText');
            if (warningText) {
                if (dryRunToggle.checked) {
                    warningText.textContent = 'This dry run is testing a restore that would overwrite existing files.';
                } else {
                    warningText.textContent = 'This restore will overwrite existing files.';
                }
            }
            overwriteWarning.classList.remove('hidden');
            
            // Only require OVERWRITE confirmation for actual restores (not dry runs)
            if (!dryRunToggle.checked) {
                confirmationSection.classList.remove('hidden');
            }
        }
    }
    
    async checkForOverwrites() {
        try {
            const selectAllChecked = document.getElementById('selectAllToggle')?.checked || false;
            const selectedPaths = window.BackupBrowser ? window.BackupBrowser.getSelection() : [];
            const currentSnapshot = document.getElementById('snapshotSelect')?.value || '';
            const restoreTarget = document.getElementById('restoreTarget')?.value || 'highball';
            
            const formData = new FormData();
            formData.append('job_name', this.jobName);
            formData.append('snapshot_id', selectAllChecked ? 'latest' : currentSnapshot);
            formData.append('select_all', selectAllChecked ? 'on' : '');
            formData.append('restore_target', restoreTarget);
            
            // Add selected paths
            if (!selectAllChecked && selectedPaths.directories) {
                selectedPaths.directories.forEach(path => formData.append('selected_paths', path));
            }
            if (!selectAllChecked && selectedPaths.files) {
                selectedPaths.files.forEach(path => formData.append('selected_paths', path));
            }
            
            const response = await fetch('/check-restore-overwrites', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                return await response.json();
            } else {
                console.error('Failed to check overwrites');
                return { hasOverwrites: false };
            }
        } catch (error) {
            console.error('Error checking overwrites:', error);
            return { hasOverwrites: false };
        }
    }
}

// Global functions for compatibility
window.toggleMode = function() {
    if (window.jobInspectManager) {
        window.jobInspectManager.toggleMode();
    }
};

window.toggleSelectAll = function() {
    if (window.jobInspectManager) {
        window.jobInspectManager.toggleSelectAll();
    }
};

window.togglePasswordField = function() {
    if (window.jobInspectManager) {
        window.jobInspectManager.togglePasswordField();
    }
};

window.handleRestoreTargetChange = function() {
    if (window.jobInspectManager) {
        window.jobInspectManager.handleRestoreTargetChange();
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get job name from page title or other source
    const jobNameElement = document.querySelector('h1');
    const jobName = jobNameElement ? jobNameElement.textContent.replace('Inspect Job: ', '') : '';
    
    if (jobName) {
        window.jobInspectManager = new JobInspectManager(jobName);
    }
});