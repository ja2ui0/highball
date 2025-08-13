// Job form core utilities - shared components
// Form field visibility management and status rendering

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
        document.getElementById('dest_restic').classList.toggle('hidden', type !== 'restic');
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
            warning: '[WARNING] ',
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

// Generic API caller - eliminates duplication
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