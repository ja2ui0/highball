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
        // Pure client-side DOM elements only
        this.restoreControls = document.getElementById('restoreControls');
        this.selectAllToggle = document.getElementById('selectAllToggle');
        this.selectionPane = document.getElementById('selectionPane');
        
        // Setup backup browser integration (external system integration)
        this.setupBackupBrowserIntegration();
        
        // Auto-load backup job when page loads (external system integration)
        window.addEventListener('load', () => {
            if (window.loadBackupJob) {
                window.loadBackupJob();
            }
        });
    }
    
    setupBackupBrowserIntegration() {
        // External system integration: backup browser selection updates
        window.originalUpdateSelectionDisplay = window.updateSelectionDisplay || function() {};
        window.updateSelectionDisplay = () => {
            window.originalUpdateSelectionDisplay();
            // All validation logic moved to HTMX server-side
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
            // Pure client-side UI: grey out selection pane when Select All is active
            this.selectionPane.style.opacity = '0.5';
            this.selectionPane.style.pointerEvents = 'none';
        } else {
            // Pure client-side UI: re-enable selection pane
            this.selectionPane.style.opacity = '1';
            this.selectionPane.style.pointerEvents = 'auto';
        }
        
        // Validation logic moved to HTMX server-side
    }
    
    // REMOVED: All validation logic moved to HTMX server-side
    // - clearRestoreValidationError() → HTMX validation endpoints
    // - checkOverwriteRisk() → HTMX validation endpoints  
    // - checkForOverwrites() → HTMX validation endpoints
    // Templates should use hx-trigger, hx-post, hx-target for validation
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