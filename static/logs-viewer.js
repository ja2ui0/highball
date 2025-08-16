/**
 * Logs Viewer JavaScript
 * Handles log viewing functionality and job log navigation
 */

// DOM elements
const logContent = document.getElementById('logContent');
const refreshButton = document.getElementById('refreshLogs');
const clearButton = document.getElementById('clearLogs');

function viewJobLog() {
    const jobSelect = document.getElementById('jobSelect');
    const jobName = jobSelect.value;
    if (jobName) {
        window.location.href = `/logs?job=${encodeURIComponent(jobName)}`;
    } else {
        // Return to system logs
        window.location.href = '/logs';
    }
}

function refreshLogs() {
    // Reload the current page to refresh log content
    window.location.reload();
}

function clearLogs() {
    logContent.textContent = '';
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (refreshButton) {
        refreshButton.addEventListener('click', refreshLogs);
    }
    if (clearButton) {
        clearButton.addEventListener('click', clearLogs);
    }
});