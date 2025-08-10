// Add Job Form JavaScript
// Handles dynamic form fields and validation for backup job creation

function showSourceFields() {
    var type = document.getElementById('source_type').value;
    document.getElementById('source_local').style.display = type === 'local' ? 'block' : 'none';
    document.getElementById('source_ssh').style.display = type === 'ssh' ? 'block' : 'none';
}

function showDestFields() {
    var type = document.getElementById('dest_type').value;
    document.getElementById('dest_local').style.display = type === 'local' ? 'block' : 'none';
    document.getElementById('dest_ssh').style.display = type === 'ssh' ? 'block' : 'none';
    document.getElementById('dest_rsyncd').style.display = type === 'rsyncd' ? 'block' : 'none';
}

function validateSource() {
    var hostname = document.getElementsByName('source_ssh_hostname')[0].value;
    var username = document.getElementsByName('source_ssh_username')[0].value;
    var path = document.getElementsByName('source_ssh_path')[0].value;
    
    if (!hostname || !username || !path) {
        document.getElementById('source_validation_status').innerHTML = '<span style="color: #dc3545;">Please fill all SSH fields</span>';
        return;
    }
    
    var source = username + '@' + hostname + ':' + path;
    callValidationEndpoint('/validate-ssh', 'source=' + encodeURIComponent(source), 'source_validation_status', 'source_validation_details');
}

function validateDestSSH() {
    var hostname = document.getElementsByName('dest_ssh_hostname')[0].value;
    var username = document.getElementsByName('dest_ssh_username')[0].value;
    var path = document.getElementsByName('dest_ssh_path')[0].value;
    
    if (!hostname || !username || !path) {
        document.getElementById('dest_ssh_validation_status').innerHTML = '<span style="color: #dc3545;">Please fill all SSH fields</span>';
        return;
    }
    
    var source = username + '@' + hostname + ':' + path;
    callValidationEndpoint('/validate-ssh', 'source=' + encodeURIComponent(source), 'dest_ssh_validation_status', 'dest_ssh_validation_details');
}

function discoverShares() {
    var hostname = document.getElementsByName('dest_rsyncd_hostname')[0].value;
    
    if (!hostname) {
        document.getElementById('discover_status').innerHTML = '<span style="color: #dc3545;">Please enter hostname first</span>';
        return;
    }
    
    var statusElement = document.getElementById('discover_status');
    var detailsElement = document.getElementById('rsyncd_validation_details');
    var shareSelection = document.getElementById('share_selection');
    var shareDropdown = document.getElementById('dest_rsyncd_share');
    
    statusElement.innerHTML = '<span style="color: #ffc107;">Discovering shares...</span>';
    detailsElement.style.display = 'none';
    shareSelection.style.display = 'none';
    
    // Get source SSH config for proper testing
    var sourceHostname = document.getElementsByName('source_ssh_hostname')[0] ? document.getElementsByName('source_ssh_hostname')[0].value : '';
    var sourceUsername = document.getElementsByName('source_ssh_username')[0] ? document.getElementsByName('source_ssh_username')[0].value : '';
    
    var params = 'hostname=' + encodeURIComponent(hostname) + '&share=dummy';
    if (sourceHostname && sourceUsername) {
        params += '&source_hostname=' + encodeURIComponent(sourceHostname) + '&source_username=' + encodeURIComponent(sourceUsername);
    }
    
    var url = '/validate-rsyncd?' + params;
    
    fetch(url)
        .then(function(response) { 
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            return response.json(); 
        })
        .then(function(data) {
            if (data.available_shares && data.available_shares.length > 0) {
                statusElement.innerHTML = '<span style="color: #28a745;">[OK] Found ' + data.available_shares.length + ' shares</span>';
                
                // Populate dropdown
                shareDropdown.innerHTML = '<option value="">Select a share...</option>';
                for (var i = 0; i < data.available_shares.length; i++) {
                    var option = document.createElement('option');
                    option.value = data.available_shares[i];
                    option.textContent = data.available_shares[i];
                    shareDropdown.appendChild(option);
                }
                
                shareSelection.style.display = 'block';
                
                // Show discovery details
                var detailsHtml = '<strong>Discovery Results:</strong><br>';
                detailsHtml += '- Found ' + data.available_shares.length + ' shares on ' + hostname + '<br>';
                if (data.tested_from) detailsHtml += '- Tested from: ' + data.tested_from + '<br>';
                detailsHtml += '- Available shares: ' + data.available_shares.join(', ');
                
                detailsElement.innerHTML = detailsHtml;
                detailsElement.style.display = 'block';
                
            } else {
                statusElement.innerHTML = '<span style="color: #dc3545;">X No shares found</span>';
                detailsElement.innerHTML = '<strong>Error:</strong><br>' + (data.message || 'No shares available');
                if (data.tested_from) detailsElement.innerHTML += '<br><strong>Tested from:</strong> ' + data.tested_from;
                detailsElement.style.display = 'block';
            }
        })
        .catch(function(error) {
            statusElement.innerHTML = '<span style="color: #dc3545;">X Discovery failed</span>';
            detailsElement.innerHTML = '<strong>Error:</strong> ' + error.message + '<br>Check browser console for details.';
            detailsElement.style.display = 'block';
            console.error('Share discovery error:', error);
        });
}

function validateDestRsyncd() {
    // This function is now replaced by discoverShares()
    discoverShares();
}

function callValidationEndpoint(endpoint, params, statusElementId, detailsElementId) {
    var statusElement = document.getElementById(statusElementId);
    var detailsElement = document.getElementById(detailsElementId);
    
    var url = endpoint + '?' + params;
    
    statusElement.innerHTML = '<span style="color: #ffc107;">Testing...</span>';
    if (detailsElement) detailsElement.style.display = 'none';
    
    fetch(url)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                statusElement.innerHTML = '<span style="color: #28a745;">[OK] Validated</span>';
                if (detailsElement) {
                    var detailsHtml = '<strong>Validation Results:</strong><br>';
                    detailsHtml += '- ' + (data.details ? data.details.ssh_status : data.message) + '<br>';
                    if (data.details && data.details.rsync_status) detailsHtml += '- ' + data.details.rsync_status + '<br>';
                    if (data.details && data.details.path_status) detailsHtml += '- ' + data.details.path_status + '<br>';
                    if (data.tested_from) detailsHtml += '- Tested from: ' + data.tested_from + '<br>';
                    
                    // Show available shares for rsyncd validation
                    if (data.available_shares && data.available_shares.length > 0) {
                        detailsHtml += '<br><strong>Available shares:</strong><br>';
                        for (var i = 0; i < data.available_shares.length; i++) {
                            detailsHtml += '- ' + data.available_shares[i] + '<br>';
                        }
                    }
                    
                    detailsElement.innerHTML = detailsHtml;
                    detailsElement.style.display = 'block';
                }
            } else {
                statusElement.innerHTML = '<span style="color: #dc3545;">X Validation failed</span>';
                if (detailsElement) {
                    var errorHtml = '<strong>Error:</strong><br>' + data.message.replace(/\n/g, '<br>');
                    if (data.tested_from) errorHtml += '<br><strong>Tested from:</strong> ' + data.tested_from;
                    
                    // Show available shares even on failure
                    if (data.available_shares && data.available_shares.length > 0) {
                        errorHtml += '<br><br><strong>Available shares:</strong><br>';
                        for (var i = 0; i < data.available_shares.length; i++) {
                            errorHtml += '- ' + data.available_shares[i] + '<br>';
                        }
                    }
                    
                    detailsElement.innerHTML = errorHtml;
                    detailsElement.style.display = 'block';
                }
            }
        })
        .catch(function(error) {
            statusElement.innerHTML = '<span style="color: #dc3545;">X Network error</span>';
            if (detailsElement) {
                detailsElement.innerHTML = '<strong>Error:</strong> ' + error.message;
                detailsElement.style.display = 'block';
            }
        });
}
