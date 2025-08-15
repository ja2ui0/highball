/**
 * Restore Core - Generic restore UI handling and orchestration
 * Handles form validation, progress display, and provider delegation
 */

let currentRestoreConfig = null;

// Provider registry for restore operations
const RESTORE_PROVIDERS = {};

// Initialize restore functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeRestoreCore();
});

function initializeRestoreCore() {
    const startRestoreButton = document.getElementById('startRestore');
    
    if (startRestoreButton) {
        startRestoreButton.addEventListener('click', startRestore);
    }
}

function registerRestoreProvider(providerType, providerImplementation) {
    /**
     * Register a restore provider implementation
     * providerImplementation should have methods:
     * - validateRestoreRequest(config)
     * - buildRestoreRequest(config) 
     * - handleRestoreResponse(response)
     * - needsPassword() - boolean
     */
    RESTORE_PROVIDERS[providerType] = providerImplementation;
}

function startRestore() {
    // Clear any previous error messages
    const errorDiv = document.getElementById('restoreValidationError');
    if (errorDiv) {
        errorDiv.classList.add('hidden');
    }
    
    // Get job name and type from page
    const jobName = getJobNameFromPage();
    const jobType = getJobTypeFromPage();
    
    if (!jobName) {
        showAlert('Unable to determine job name');
        return;
    }
    
    const provider = RESTORE_PROVIDERS[jobType];
    if (!provider) {
        showAlert(`Restore not supported for job type: ${jobType}`);
        return;
    }
    
    // Gather restore configuration
    const isDryRun = document.getElementById('dryRunToggle').checked;
    const selectAllChecked = document.getElementById('selectAllToggle').checked;
    const selectedPaths = gatherSelectedPaths();
    const currentSnapshot = getCurrentSnapshotId();
    
    // Build base restore config
    const baseConfig = {
        job_name: jobName,
        job_type: jobType,
        restore_target: getRestoreTarget(),
        dry_run: isDryRun,
        select_all: selectAllChecked,
        selected_paths: selectedPaths,
        snapshot_id: selectAllChecked ? 'latest' : currentSnapshot
    };
    
    // Let provider validate the request
    const validationResult = provider.validateRestoreRequest(baseConfig);
    if (!validationResult.valid) {
        showAlert(validationResult.error);
        return;
    }
    
    // For non-dry-run, check for confirmation if overwrites would occur
    if (!isDryRun) {
        // Check if confirmation is required and provided (for any overwrite situation)
        const confirmationSection = document.getElementById('confirmationSection');
        if (confirmationSection && !confirmationSection.classList.contains('hidden')) {
            const confirmationField = document.getElementById('overwriteConfirmation');
            const confirmation = confirmationField ? confirmationField.value.trim() : '';
            
            if (confirmation !== 'OVERWRITE') {
                showAlert('Please type "OVERWRITE" to confirm data replacement');
                return;
            }
        }
    }
    
    currentRestoreConfig = baseConfig;
    
    if (isDryRun) {
        // Execute dry run directly
        executeDryRun(provider);
    } else {
        // Execute actual restore
        executeRestore(provider);
    }
}

function executeDryRun(provider) {
    showProgressDisplay('Executing dry run...', 0);
    
    executeRestoreRequest(provider, currentRestoreConfig)
        .then(result => {
            hideProgressDisplay();
            provider.handleDryRunResponse(result);
        })
        .catch(error => {
            hideProgressDisplay();
            showAlert(`Dry run error: ${error.message}`);
        });
}

function executeRestore(provider) {
    showProgressDisplay('Starting restore...', 0);
    
    // Debug: Check if config is null
    if (!currentRestoreConfig) {
        hideProgressDisplay();
        showAlert('Error: Restore configuration is missing');
        return;
    }
    
    executeRestoreRequest(provider, currentRestoreConfig)
        .then(result => {
            if (result.success) {
                provider.handleRestoreResponse(result, currentRestoreConfig);
            } else {
                hideProgressDisplay();
                showAlert(`Restore failed: ${result.error}`);
            }
        })
        .catch(error => {
            hideProgressDisplay();
            showAlert(`Restore error: ${error.message}`);
        });
}

function executeRestoreRequest(provider, config) {
    // Let provider build the request
    const requestData = provider.buildRestoreRequest(config);
    
    // Create an AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
        controller.abort();
    }, 30000);
    
    return fetch('/restore', {
        method: 'POST',
        // Don't set Content-Type header - let browser set it for FormData
        body: requestData,
        signal: controller.signal
    }).then(response => {
        clearTimeout(timeoutId);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    }).then(data => {
        return data;
    }).catch(error => {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timed out');
        }
        throw error;
    });
}

// UI Helper Functions
function showProgressDisplay(message, progress) {
    const progressDiv = document.getElementById('restoreProgress');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');
    
    if (progressText) progressText.textContent = message;
    if (progressFill) progressFill.style.width = progress + '%';
    if (progressDiv) progressDiv.classList.remove('hidden');
}

function hideProgressDisplay() {
    const progressDiv = document.getElementById('restoreProgress');
    if (progressDiv) {
        progressDiv.classList.add('hidden');
    }
}

function showAlert(message, isSuccess = false) {
    // Show message inline with appropriate styling
    const alertDiv = document.getElementById('restoreValidationError');
    if (alertDiv) {
        alertDiv.textContent = message;
        alertDiv.classList.remove('hidden', 'status-error', 'status-success');
        alertDiv.classList.add(isSuccess ? 'status-success' : 'status-error');
        // No auto-hide - user should manually clear status messages
    } else {
        // Fallback to browser alert if error div not found
        alert(message);
    }
}

// Page Data Extraction Functions
function getJobNameFromPage() {
    const jobNameElement = document.querySelector('h1');
    return jobNameElement ? jobNameElement.textContent.replace('Inspect Job: ', '') : '';
}

function getJobTypeFromPage() {
    const jobTypeElement = document.querySelector('.job-type-info strong');
    return jobTypeElement ? jobTypeElement.textContent.toLowerCase() : '';
}

function getRestoreTarget() {
    const restoreTargetSelect = document.getElementById('restoreTarget');
    return restoreTargetSelect ? restoreTargetSelect.value : 'highball';
}

function gatherSelectedPaths() {
    // Use the backup browser's selection tracking instead of DOM parsing
    if (window.BackupBrowser && window.BackupBrowser.getSelection) {
        const selection = window.BackupBrowser.getSelection();
        const allPaths = [
            ...Array.from(selection.directories || []),
            ...Array.from(selection.files || [])
        ];
        
        return allPaths;
    } else {
        // Fallback to DOM parsing (though this won't work with current implementation)
        const checkboxes = document.querySelectorAll('.tree-item input[type="checkbox"]:checked');
        const paths = Array.from(checkboxes).map(cb => cb.getAttribute('data-path')).filter(path => path);
        
        return paths;
    }
}

function getCurrentSnapshotId() {
    const snapshotSelect = document.getElementById('snapshotSelect');
    return snapshotSelect ? snapshotSelect.value : null;
}

// Export functions for provider implementations
window.RestoreCore = {
    showProgressDisplay: showProgressDisplay,
    hideProgressDisplay: hideProgressDisplay,
    showAlert: showAlert,
    registerRestoreProvider: registerRestoreProvider
};