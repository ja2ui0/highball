/**
 * Development Logs JavaScript  
 * Handles log refresh and clear functionality for system debugging
 */

// DOM elements
const logContent = document.getElementById('logContent');
const refreshButton = document.getElementById('refreshLogs');
const clearButton = document.getElementById('clearLogs');

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