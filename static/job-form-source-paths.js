/**
 * Source path validation and management for job forms
 */

let pathCounter = 1;

function addPath() {
    pathCounter++;
    const container = document.getElementById('source_paths_container');
    const template = document.getElementById('path_entry_template');
    const newPath = template.cloneNode(true);
    
    // Update the new path entry
    newPath.id = '';
    newPath.classList.remove('hidden');
    newPath.setAttribute('data-path-index', pathCounter - 1);
    
    // Update header
    const header = newPath.querySelector('.path-header');
    header.innerHTML = `<span>Source Path ${pathCounter}</span><button type="button" class="remove-path-btn button button-danger" onclick="removePath(this)">Remove</button>`;
    
    // Update form fields
    const pathInput = newPath.querySelector('.path-input');
    pathInput.id = `source_path_${pathCounter - 1}`;
    pathInput.placeholder = getPathPlaceholder();
    
    const includesInput = newPath.querySelector('.includes-input');
    includesInput.id = `source_includes_${pathCounter - 1}`;
    
    const excludesInput = newPath.querySelector('.excludes-input');
    excludesInput.id = `source_excludes_${pathCounter - 1}`;
    
    // Update labels
    newPath.querySelector('.path-label').setAttribute('for', `source_path_${pathCounter - 1}`);
    newPath.querySelector('.includes-label').setAttribute('for', `source_includes_${pathCounter - 1}`);
    newPath.querySelector('.excludes-label').setAttribute('for', `source_excludes_${pathCounter - 1}`);
    
    container.appendChild(newPath);
    
    // Show remove buttons if we have multiple paths
    updateRemoveButtons();
}

function removePath(button) {
    const pathEntry = button.closest('.path-entry');
    pathEntry.remove();
    updatePathNumbers();
    updateRemoveButtons();
}

function updatePathNumbers() {
    const pathEntries = document.querySelectorAll('.path-entry:not(#path_entry_template)');
    pathEntries.forEach((entry, index) => {
        const header = entry.querySelector('.path-header');
        
        // First path (index 0) never gets a remove button
        if (index === 0) {
            header.innerHTML = `<span>Source Path ${index + 1}</span>`;
        } else {
            header.innerHTML = `<span>Source Path ${index + 1}</span><button type="button" class="remove-path-btn button button-danger" onclick="removePath(this)">Remove</button>`;
        }
        
        entry.setAttribute('data-path-index', index);
    });
}

function updateRemoveButtons() {
    // Remove button visibility is now handled in updatePathNumbers
    // This function kept for backward compatibility
}

function getPathPlaceholder() {
    const sourceType = document.getElementById('source_type').value;
    if (sourceType === 'local') {
        return '/var/lib/docker/volumes/data';
    } else if (sourceType === 'ssh') {
        return '/mnt/data';
    }
    return '/path/to/backup';
}

function validatePath(button) {
    console.log('validatePath called', button);
    
    const pathEntry = button.closest('.path-entry');
    const pathInput = pathEntry.querySelector('.path-input');
    const resultDiv = pathEntry.querySelector('.path-validation-result');
    
    console.log('Elements found:', { pathEntry, pathInput, resultDiv });
    
    const path = pathInput.value.trim();
    console.log('Path value:', path);
    
    if (!path) {
        resultDiv.innerHTML = '<span class="validation-error">[ERROR] Please enter a path first</span>';
        return;
    }
    
    // Show loading state
    button.disabled = true;
    button.textContent = 'Validating...';
    resultDiv.innerHTML = '<span class="validation-pending">Checking path permissions...</span>';
    
    // Get source configuration for validation
    const formData = new FormData();
    const sourceType = document.getElementById('source_type').value;
    console.log('Source type:', sourceType);
    
    formData.append('source_type', sourceType);
    
    // Add source connection details
    if (sourceType === 'ssh') {
        const hostname = document.querySelector('input[name="source_ssh_hostname"]');
        const username = document.querySelector('input[name="source_ssh_username"]');
        if (hostname) formData.append('source_ssh_hostname', hostname.value);
        if (username) formData.append('source_ssh_username', username.value);
        console.log('SSH details:', { hostname: hostname?.value, username: username?.value });
    }
    
    // Add just this path for validation
    formData.append('source_paths[]', path);
    
    console.log('Making fetch request to /validate-source-paths');
    
    fetch('/validate-source-paths', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        console.log('Response received:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        button.disabled = false;
        button.textContent = 'Validate Path';
        
        if (data.success && data.paths_detail && data.paths_detail.length > 0) {
            const pathResult = data.paths_detail[0];
            let html = '';
            
            if (pathResult.valid) {
                if (pathResult.can_backup && pathResult.can_restore_to_source) {
                    html = `<span class="validation-success">[OK] Path is RWX</span>`;
                } else if (pathResult.can_backup && !pathResult.can_restore_to_source) {
                    html = `<span class="status-warning">[WARN] Path is RO - can backup but cannot restore to source</span>`;
                } else {
                    html = `<span class="validation-error">[ERROR] Insufficient permissions</span>`;
                }
            } else {
                html = `<span class="validation-error">[ERROR] ${pathResult.message || 'Path validation failed'}</span>`;
            }
            
            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `<span class="validation-error">[ERROR] ${data.message || 'Validation failed'}</span>`;
        }
    })
    .catch(error => {
        button.disabled = false;
        button.textContent = 'Validate Path';
        resultDiv.innerHTML = `<div class="validation-error">Validation error: ${error.message}</div>`;
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const sourceTypeSelect = document.getElementById('source_type');
    if (sourceTypeSelect) {
        sourceTypeSelect.addEventListener('change', function() {
            const placeholder = getPathPlaceholder();
            document.querySelectorAll('.path-input').forEach(input => {
                input.placeholder = placeholder;
            });
        });
    }
    
    // Initialize placeholders
    const placeholder = getPathPlaceholder();
    document.querySelectorAll('.path-input').forEach(input => {
        input.placeholder = placeholder;
    });
    
    updateRemoveButtons();
});