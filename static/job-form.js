// Job form JavaScript - handles dynamic form fields and validation
// Consolidated and modernized version eliminating redundancy

// Form field visibility management
const FormManager = {
    showSourceFields() {
        const type = document.getElementById('source_type').value;
        document.getElementById('source_local').classList.toggle('hidden', type !== 'local');
        document.getElementById('source_ssh').classList.toggle('hidden', type !== 'ssh');
    },

    showDestFields() {
        const type = document.getElementById('dest_type').value;
        document.getElementById('dest_local').classList.toggle('hidden', type !== 'local');
        document.getElementById('dest_ssh').classList.toggle('hidden', type !== 'ssh');
        document.getElementById('dest_rsyncd').classList.toggle('hidden', type !== 'rsyncd');
    },

    showCronField() {
        const schedule = document.getElementById('schedule').value;
        const cronField = document.getElementById('cron_field');
        cronField.classList.toggle('hidden', schedule !== 'cron');
    }
};

// Status display using CSS classes instead of inline styles
const StatusRenderer = {
    show(elementId, message, type = 'info') {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        // Clear existing status classes
        element.className = element.className.replace(/status-\w+/g, '');
        
        // Add appropriate status class
        element.classList.add(`status-${type}`);
        element.textContent = this.getStatusText(type, message);
    },

    getStatusText(type, message) {
        const prefixes = {
            success: '[OK] ',
            error: 'X ',
            warning: '⚠ ',
            info: ''
        };
        return `${prefixes[type] || ''}${message}`;
    },

    showDetails(elementId, content) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.innerHTML = content;
        element.classList.remove('hidden');
    },

    hideDetails(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.add('hidden');
        }
    }
};

// Generic API caller - eliminates the 58-line duplication
const APIClient = {
    async call(endpoint, params, onSuccess, onError) {
        const url = `${endpoint}?${new URLSearchParams(params).toString()}`;
        
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            onSuccess(data);
        } catch (error) {
            onError(error);
        }
    }
};

// SSH validation - consolidated function eliminating duplication
const SSHValidator = {
    validate(fields, statusId, detailsId) {
        const values = fields.map(name => {
            const element = document.getElementsByName(name)[0];
            return element ? element.value.trim() : '';
        });

        // Check if all required fields are filled
        if (values.some(value => !value)) {
            StatusRenderer.show(statusId, 'Please fill all SSH fields', 'error');
            StatusRenderer.hideDetails(detailsId);
            return;
        }

        const [hostname, username, path] = values;
        const source = `${username}@${hostname}:${path}`;
        
        StatusRenderer.show(statusId, 'Testing...', 'warning');
        StatusRenderer.hideDetails(detailsId);

        APIClient.call(
            '/validate-ssh',
            { source },
            (data) => this.handleValidationSuccess(data, statusId, detailsId),
            (error) => this.handleValidationError(error, statusId, detailsId)
        );
    },

    handleValidationSuccess(data, statusId, detailsId) {
        if (data.success) {
            StatusRenderer.show(statusId, 'Validated', 'success');
            
            const details = data.details || {};
            const detailsContent = [
                '<strong>Validation Results:</strong>',
                `- ${details.ssh_status || data.message}`,
                details.rsync_status ? `- ${details.rsync_status}` : '',
                details.path_status ? `- ${details.path_status}` : '',
                data.tested_from ? `- Tested from: ${data.tested_from}` : ''
            ].filter(line => line && !line.endsWith('- ')).join('<br>');
            
            StatusRenderer.showDetails(detailsId, detailsContent);
        } else {
            this.handleValidationError(new Error(data.message), statusId, detailsId);
        }
    },

    handleValidationError(error, statusId, detailsId) {
        StatusRenderer.show(statusId, 'Validation failed', 'error');
        const errorContent = `<strong>Error:</strong><br>${error.message}`;
        StatusRenderer.showDetails(detailsId, errorContent);
    }
};

// Rsync share discovery
const RsyncDiscovery = {
    discover() {
        const hostname = document.getElementsByName('dest_rsyncd_hostname')[0]?.value?.trim();
        
        if (!hostname) {
            StatusRenderer.show('discover_status', 'Please enter hostname first', 'error');
            return;
        }

        const params = { hostname, share: 'dummy' };
        
        // Add source SSH config if available
        const sourceHostname = document.getElementsByName('source_ssh_hostname')[0]?.value?.trim();
        const sourceUsername = document.getElementsByName('source_ssh_username')[0]?.value?.trim();
        
        if (sourceHostname && sourceUsername) {
            params.source_hostname = sourceHostname;
            params.source_username = sourceUsername;
        }

        StatusRenderer.show('discover_status', 'Discovering shares...', 'warning');
        StatusRenderer.hideDetails('rsyncd_validation_details');
        this.hideShareSelection();

        APIClient.call(
            '/validate-rsyncd',
            params,
            (data) => this.handleDiscoverySuccess(data, hostname),
            (error) => this.handleDiscoveryError(error)
        );
    },

    handleDiscoverySuccess(data, hostname) {
        const shares = data.available_shares || [];
        
        if (shares.length > 0) {
            StatusRenderer.show('discover_status', `Found ${shares.length} shares`, 'success');
            this.populateShareDropdown(shares);
            this.showShareSelection();
            
            const detailsContent = [
                '<strong>Discovery Results:</strong>',
                `- Found ${shares.length} shares on ${hostname}`,
                data.tested_from ? `- Tested from: ${data.tested_from}` : '',
                `- Available shares: ${shares.join(', ')}`
            ].filter(line => line && !line.endsWith('- ')).join('<br>');
            
            StatusRenderer.showDetails('rsyncd_validation_details', detailsContent);
        } else {
            StatusRenderer.show('discover_status', 'No shares found', 'error');
            const errorContent = [
                '<strong>Error:</strong>',
                data.message || 'No shares available',
                data.tested_from ? `<strong>Tested from:</strong> ${data.tested_from}` : ''
            ].filter(line => line).join('<br>');
            
            StatusRenderer.showDetails('rsyncd_validation_details', errorContent);
        }
    },

    handleDiscoveryError(error) {
        StatusRenderer.show('discover_status', 'Discovery failed', 'error');
        const errorContent = `<strong>Error:</strong> ${error.message}<br>Check browser console for details.`;
        StatusRenderer.showDetails('rsyncd_validation_details', errorContent);
        console.error('Share discovery error:', error);
    },

    populateShareDropdown(shares) {
        const dropdown = document.getElementById('dest_rsyncd_share');
        if (!dropdown) return;
        
        dropdown.innerHTML = '<option value="">Select a share...</option>';
        shares.forEach(share => {
            const option = document.createElement('option');
            option.value = share;
            option.textContent = share;
            dropdown.appendChild(option);
        });
    },

    showShareSelection() {
        const element = document.getElementById('share_selection');
        if (element) element.classList.remove('hidden');
    },

    hideShareSelection() {
        const element = document.getElementById('share_selection');
        if (element) element.classList.add('hidden');
    }
};

// Global functions for backward compatibility
function showSourceFields() {
    FormManager.showSourceFields();
}

function showDestFields() {
    FormManager.showDestFields();
}

function showCronField() {
    FormManager.showCronField();
}

function validateSource() {
    SSHValidator.validate(['source_ssh_hostname', 'source_ssh_username', 'source_ssh_path'], 
                         'source_validation_status', 'source_validation_details');
}

function validateDestSSH() {
    SSHValidator.validate(['dest_ssh_hostname', 'dest_ssh_username', 'dest_ssh_path'], 
                         'dest_ssh_validation_status', 'dest_ssh_validation_details');
}

function discoverShares() {
    RsyncDiscovery.discover();
}

// Legacy function aliases for compatibility
function validateDestRsyncd() {
    discoverShares();
}