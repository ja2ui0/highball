// Global functions for backward compatibility
// These functions are called from the HTML templates

function showSourceFields() {
    FormManager.showSourceFields();
}

function showDestFields() {
    FormManager.showDestFields();
}

function showCronField() {
    FormManager.showCronField();
}

function showResticRepoFields() {
    ResticManager.showRepoFields();
}

function validateSource() {
    SSHValidator.validate(['source_ssh_hostname', 'source_ssh_username'], 
                         'source_validation_status', 'source_validation_details');
}

function validateDestSSH() {
    SSHValidator.validate(['dest_ssh_hostname', 'dest_ssh_username', 'dest_ssh_path'], 
                         'dest_ssh_validation_status', 'dest_ssh_validation_details');
}

function validateRestic() {
    ResticValidator.validate();
}

function discoverShares() {
    RsyncDiscovery.discover();
}

// Legacy function aliases for compatibility
function validateDestRsyncd() {
    discoverShares();
}