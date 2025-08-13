// Rsync daemon functionality
// Handles rsync share discovery and validation

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