/**
 * Restore Core - Generic restore UI handling and orchestration
 * Handles modals, form validation, progress display, and provider delegation
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
    const confirmRestoreButton = document.getElementById('confirmRestore');
    const cancelRestoreButton = document.getElementById('cancelRestore');
    const closeProgressButton = document.getElementById('closeProgress');
    const passwordModal = document.getElementById('passwordModal');
    const progressModal = document.getElementById('progressModal');
    
    if (startRestoreButton) {
        startRestoreButton.addEventListener('click', startRestore);
    }
    
    if (confirmRestoreButton) {
        confirmRestoreButton.addEventListener('click', confirmRestore);
    }
    
    if (cancelRestoreButton) {
        cancelRestoreButton.addEventListener('click', hidePasswordModal);
    }
    
    if (closeProgressButton) {
        closeProgressButton.addEventListener('click', hideProgressModal);
    }
    
    // Modal background click to close
    if (passwordModal) {
        passwordModal.addEventListener('click', function(e) {
            if (e.target === passwordModal) hidePasswordModal();
        });
    }
    
    if (progressModal) {
        progressModal.addEventListener('click', function(e) {
            if (e.target === progressModal && document.getElementById('closeProgress').style.display !== 'none') {
                hideProgressModal();
            }
        });
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
    
    currentRestoreConfig = baseConfig;
    
    if (isDryRun) {
        // Execute dry run directly
        executeDryRun(provider);
    } else {
        // Check if provider needs password
        if (provider.needsPassword()) {
            showPasswordModal(provider);
        } else {
            executeRestore(provider);
        }
    }
}

function showPasswordModal(provider) {
    const passwordModal = document.getElementById('passwordModal');
    const summaryContent = document.getElementById('summaryContent');
    const modalPassword = document.getElementById('modalPassword');
    
    if (!passwordModal || !summaryContent || !modalPassword) {
        showAlert('Modal elements not found');
        return;
    }
    
    // Let provider build summary content
    const summaryHtml = provider.buildRestoreSummary(currentRestoreConfig);
    summaryContent.innerHTML = summaryHtml;
    
    // Clear previous password and errors
    modalPassword.value = '';
    document.getElementById('modalError').classList.add('hidden');
    
    // Show modal
    passwordModal.classList.remove('hidden');
    modalPassword.focus();
}

function hidePasswordModal() {
    const passwordModal = document.getElementById('passwordModal');
    if (passwordModal) {
        passwordModal.classList.add('hidden');
    }
    currentRestoreConfig = null;
}

function confirmRestore() {
    const modalPassword = document.getElementById('modalPassword');
    const password = modalPassword ? modalPassword.value.trim() : '';
    
    if (!password) {
        showModalError('Password is required');
        return;
    }
    
    // Add password to config
    currentRestoreConfig.password = password;
    
    // Get provider and execute restore
    const provider = RESTORE_PROVIDERS[currentRestoreConfig.job_type];
    if (!provider) {
        showModalError('Provider not found');
        return;
    }
    
    // Hide password modal and execute restore
    hidePasswordModal();
    executeRestore(provider);
}

function executeDryRun(provider) {
    showProgressModal('Executing dry run...', 0);
    
    executeRestoreRequest(provider, currentRestoreConfig)
        .then(result => {
            hideProgressModal();
            provider.handleDryRunResponse(result);
        })
        .catch(error => {
            hideProgressModal();
            showAlert(`Dry run error: ${error.message}`);
        });
}

function executeRestore(provider) {
    showProgressModal('Starting restore...', 0);
    
    executeRestoreRequest(provider, currentRestoreConfig)
        .then(result => {
            if (result.success) {
                provider.handleRestoreResponse(result, currentRestoreConfig);
            } else {
                hideProgressModal();
                showAlert(`Restore failed: ${result.error}`);
            }
        })
        .catch(error => {
            hideProgressModal();
            showAlert(`Restore error: ${error.message}`);
        });
}

function executeRestoreRequest(provider, config) {
    // Let provider build the request
    const requestData = provider.buildRestoreRequest(config);
    
    return fetch('/restore', {
        method: 'POST',
        body: requestData
    }).then(response => response.json());
}

// UI Helper Functions
function showProgressModal(message, progress) {
    const progressModal = document.getElementById('progressModal');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');
    const closeButton = document.getElementById('closeProgress');
    
    if (progressText) progressText.textContent = message;
    if (progressFill) progressFill.style.width = progress + '%';
    if (closeButton) closeButton.style.display = progress >= 100 ? 'block' : 'none';
    if (progressModal) progressModal.classList.remove('hidden');
}

function hideProgressModal() {
    const progressModal = document.getElementById('progressModal');
    if (progressModal) {
        progressModal.classList.add('hidden');
    }
}

function showModalError(message) {
    const errorDiv = document.getElementById('modalError');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }
}

function showAlert(message) {
    alert(message); // Could be enhanced with better UI later
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
    const checkboxes = document.querySelectorAll('.tree-item input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.getAttribute('data-path')).filter(path => path);
}

function getCurrentSnapshotId() {
    const snapshotSelect = document.getElementById('snapshotSelect');
    return snapshotSelect ? snapshotSelect.value : null;
}

// Export functions for provider implementations
window.RestoreCore = {
    showProgressModal: showProgressModal,
    hideProgressModal: hideProgressModal,
    showAlert: showAlert,
    registerRestoreProvider: registerRestoreProvider
};