/**
 * Maintenance form behavior
 * Handles show/hide of maintenance section based on destination type
 * and progressive disclosure of manual options
 */

function initMaintenanceForm() {
    // Initialize toggle states based on current mode
    updateMaintenanceDisplay();
}

function toggleMaintenanceFirst() {
    const toggle = document.getElementById('maintenanceFirstToggle');
    const hiddenField = document.getElementById('restic_maintenance');
    
    if (toggle.classList.contains('left')) {
        // Switch from Auto to User
        toggle.classList.remove('left');
        toggle.classList.add('right');
        hiddenField.value = 'user';
    } else {
        // Switch from User to Auto  
        toggle.classList.remove('right');
        toggle.classList.add('left');
        hiddenField.value = 'auto';
    }
    
    updateMaintenanceDisplay();
}

function toggleMaintenanceSecond() {
    const toggle = document.getElementById('maintenanceSecondToggle');
    const hiddenField = document.getElementById('restic_maintenance');
    
    if (toggle.classList.contains('left')) {
        // Switch from Config to Off
        toggle.classList.remove('left');
        toggle.classList.add('right');
        hiddenField.value = 'off';
    } else {
        // Switch from Off to Config
        toggle.classList.remove('right');
        toggle.classList.add('left');
        hiddenField.value = 'user';
    }
    
    updateMaintenanceDisplay();
}

function updateMaintenanceDisplay() {
    const mode = document.getElementById('restic_maintenance').value;
    
    // Elements to show/hide
    const autoHelpText = document.getElementById('auto_help_text');
    const userModeSection = document.getElementById('user_mode_section');
    const configHelpText = document.getElementById('config_help_text');
    const offHelpText = document.getElementById('off_help_text');
    const manualConfigOptions = document.getElementById('manual_config_options');
    
    if (mode === 'auto') {
        // Show auto help text, hide user section
        autoHelpText.classList.remove('hidden');
        userModeSection.classList.add('hidden');
    } else if (mode === 'user') {
        // Hide auto help text, show user section with config mode
        autoHelpText.classList.add('hidden');
        userModeSection.classList.remove('hidden');
        configHelpText.classList.remove('hidden');
        offHelpText.classList.add('hidden');
        manualConfigOptions.classList.remove('hidden');
    } else if (mode === 'off') {
        // Hide auto help text, show user section with off mode
        autoHelpText.classList.add('hidden');
        userModeSection.classList.remove('hidden');
        configHelpText.classList.add('hidden');
        offHelpText.classList.remove('hidden');
        manualConfigOptions.classList.add('hidden');
    }
}

function showMaintenanceSection() {
    const maintenanceSection = document.getElementById('maintenance_section');
    if (maintenanceSection) {
        maintenanceSection.classList.remove('hidden');
    }
}

function hideMaintenanceSection() {
    const maintenanceSection = document.getElementById('maintenance_section');
    if (maintenanceSection) {
        maintenanceSection.classList.add('hidden');
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', initMaintenanceForm);