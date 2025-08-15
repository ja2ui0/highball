// SSH validation functionality
// Handles SSH source and destination validation

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
        // Handle both 2-field (hostname, username) and 3-field (hostname, username, path) validation
        const source = path ? `${username}@${hostname}:${path}` : `${username}@${hostname}`;
        
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
                details.container_runtime ? `- ${details.container_runtime}` : '',
                details.path_status ? `- ${details.path_status}` : ''
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