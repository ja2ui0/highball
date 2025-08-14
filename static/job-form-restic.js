// Restic functionality
// Handles Restic repository configuration, URI generation, and validation

const ResticManager = {
    showRepoFields() {
        const type = document.getElementById('restic_repo_type')?.value;
        document.getElementById('restic_local').classList.toggle('hidden', type !== 'local');
        document.getElementById('restic_rest').classList.toggle('hidden', type !== 'rest');
        document.getElementById('restic_s3').classList.toggle('hidden', type !== 's3');
        document.getElementById('restic_rclone').classList.toggle('hidden', type !== 'rclone');
        document.getElementById('restic_sftp').classList.toggle('hidden', type !== 'sftp');
        
        // Update URI previews
        ResticURIUpdater.updatePreviews();
    }
};

// Restic URI updater - generates URI previews
const ResticURIUpdater = {
    updatePreviews() {
        const repoType = document.getElementById('restic_repo_type')?.value;
        
        switch (repoType) {
            case 'rest':
                this.updateRestURI();
                break;
            case 's3':
                this.updateS3URI();
                break;
            case 'rclone':
                this.updateRcloneURI();
                break;
            case 'sftp':
                this.updateSftpURI();
                break;
        }
    },

    updateRestURI() {
        const hostname = document.getElementsByName('restic_rest_hostname')[0]?.value || 'hostname';
        const port = document.getElementsByName('restic_rest_port')[0]?.value || '8000';
        const path = document.getElementsByName('restic_rest_path')[0]?.value || '';
        const useHttps = document.getElementsByName('restic_rest_use_https')[0]?.checked ?? true;
        
        const scheme = useHttps ? 'https' : 'http';
        const portStr = (port && port !== '80' && port !== '443') ? `:${port}` : '';
        const pathStr = path ? (path.startsWith('/') ? path : `/${path}`) : '';
        
        const uri = `rest:${scheme}://${hostname}${portStr}${pathStr}`;
        this.setPreview('rest_uri_preview', uri);
    },

    updateS3URI() {
        const endpoint = document.getElementsByName('restic_s3_endpoint')[0]?.value || 's3.amazonaws.com';
        const bucket = document.getElementsByName('restic_s3_bucket')[0]?.value || 'bucket';
        const prefix = document.getElementsByName('restic_s3_prefix')[0]?.value || '';
        
        const uri = prefix ? `s3:${endpoint}/${bucket}/${prefix}` : `s3:${endpoint}/${bucket}`;
        this.setPreview('s3_uri_preview', uri);
    },

    updateRcloneURI() {
        const remote = document.getElementsByName('restic_rclone_remote')[0]?.value || 'remote';
        const path = document.getElementsByName('restic_rclone_path')[0]?.value || 'path';
        
        const uri = `rclone:${remote}:${path}`;
        this.setPreview('rclone_uri_preview', uri);
    },

    updateSftpURI() {
        const hostname = document.getElementsByName('restic_sftp_hostname')[0]?.value || 'hostname';
        const username = document.getElementsByName('restic_sftp_username')[0]?.value || 'user';
        const path = document.getElementsByName('restic_sftp_path')[0]?.value || '/path';
        
        const uri = `sftp:${username}@${hostname}:${path}`;
        this.setPreview('sftp_uri_preview', uri);
    },

    setPreview(elementId, uri) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = uri;
        }
    }
};

// Restic validation
const ResticValidator = {
    validate() {
        // Collect form data for validation
        const formData = this.collectFormData();
        
        if (!formData) {
            StatusRenderer.show('restic_validation_status', 'Please fill required fields first', 'error');
            return;
        }

        StatusRenderer.show('restic_validation_status', 'Validating...', 'warning');
        StatusRenderer.hideDetails('restic_validation_details');

        // Use form validation endpoint
        this.submitFormValidation(formData);
    },

    collectFormData() {
        // Collect all form fields needed for validation
        const formData = new FormData();
        
        // Required fields
        const jobName = document.getElementsByName('job_name')[0]?.value?.trim();
        const sourceType = document.getElementsByName('source_type')[0]?.value;
        const destType = document.getElementsByName('dest_type')[0]?.value;
        const resticRepoType = document.getElementsByName('restic_repo_type')[0]?.value;
        const resticPassword = document.getElementsByName('restic_password')[0]?.value;
        
        if (!jobName || !sourceType || destType !== 'restic' || !resticRepoType || !resticPassword) {
            return null;
        }
        
        // Add basic fields
        formData.append('job_name', jobName);
        formData.append('source_type', sourceType);
        formData.append('dest_type', destType);
        formData.append('restic_repo_type', resticRepoType);
        formData.append('restic_password', resticPassword);
        
        // Add source fields
        if (sourceType === 'ssh') {
            formData.append('source_ssh_hostname', document.getElementsByName('source_ssh_hostname')[0]?.value || '');
            formData.append('source_ssh_username', document.getElementsByName('source_ssh_username')[0]?.value || '');
            formData.append('source_ssh_path', document.getElementsByName('source_ssh_path')[0]?.value || '');
        } else if (sourceType === 'local') {
            formData.append('source_local_path', document.getElementsByName('source_local_path')[0]?.value || '');
        }
        
        // Add restic repository type specific fields
        this.addResticFields(formData, resticRepoType);
        
        return formData;
    },

    addResticFields(formData, repoType) {
        switch (repoType) {
            case 'local':
                formData.append('restic_local_path', document.getElementsByName('restic_local_path')[0]?.value || '');
                break;
            case 'rest':
                formData.append('restic_rest_hostname', document.getElementsByName('restic_rest_hostname')[0]?.value || '');
                formData.append('restic_rest_port', document.getElementsByName('restic_rest_port')[0]?.value || '8000');
                formData.append('restic_rest_path', document.getElementsByName('restic_rest_path')[0]?.value || '');
                formData.append('restic_rest_use_https', document.getElementsByName('restic_rest_use_https')[0]?.checked ? 'on' : '');
                formData.append('restic_rest_username', document.getElementsByName('restic_rest_username')[0]?.value || '');
                formData.append('restic_rest_password', document.getElementsByName('restic_rest_password')[0]?.value || '');
                break;
            case 's3':
                formData.append('restic_s3_endpoint', document.getElementsByName('restic_s3_endpoint')[0]?.value || 's3.amazonaws.com');
                formData.append('restic_s3_bucket', document.getElementsByName('restic_s3_bucket')[0]?.value || '');
                formData.append('restic_s3_prefix', document.getElementsByName('restic_s3_prefix')[0]?.value || '');
                formData.append('restic_aws_access_key', document.getElementsByName('restic_aws_access_key')[0]?.value || '');
                formData.append('restic_aws_secret_key', document.getElementsByName('restic_aws_secret_key')[0]?.value || '');
                break;
            case 'rclone':
                formData.append('restic_rclone_remote', document.getElementsByName('restic_rclone_remote')[0]?.value || '');
                formData.append('restic_rclone_path', document.getElementsByName('restic_rclone_path')[0]?.value || '');
                break;
            case 'sftp':
                formData.append('restic_sftp_hostname', document.getElementsByName('restic_sftp_hostname')[0]?.value || '');
                formData.append('restic_sftp_username', document.getElementsByName('restic_sftp_username')[0]?.value || '');
                formData.append('restic_sftp_path', document.getElementsByName('restic_sftp_path')[0]?.value || '');
                break;
        }
    },

    async submitFormValidation(formData) {
        try {
            const response = await fetch('/validate-restic-form', {
                method: 'POST',
                // Let browser set Content-Type for FormData
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            this.handleValidationSuccess(data);
        } catch (error) {
            this.handleValidationError(error);
        }
    },

    handleValidationSuccess(data) {
        if (data.success) {
            StatusRenderer.show('restic_validation_status', 'Configuration valid', 'success');
            
            const detailsContent = [
                '<strong>Validation Results:</strong>',
                `- ${data.message}`,
                data.repository_status ? `- Repository status: ${data.repository_status}` : '',
                data.snapshot_count !== undefined ? `- Snapshots: ${data.snapshot_count}` : '',
                data.latest_backup ? `- Latest backup: ${data.latest_backup}` : '',
                data.tested_from ? `- Tested from: ${data.tested_from}` : '',
                data.details && data.details.repo_uri ? `- Repository URI: ${data.details.repo_uri}` : ''
            ].filter(line => line && !line.endsWith('- ')).join('<br>');
            
            StatusRenderer.showDetails('restic_validation_details', detailsContent);
        } else {
            this.handleValidationError(new Error(data.message || 'Validation failed'));
        }
    },

    handleValidationError(error) {
        StatusRenderer.show('restic_validation_status', 'Validation failed', 'error');
        const errorContent = `<strong>Error:</strong><br>${error.message}`;
        StatusRenderer.showDetails('restic_validation_details', errorContent);
    }
};

// Password visibility toggle
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const icon = document.querySelector(`.password-toggle-icon[data-target="${inputId}"]`);
    
    if (input && icon) {
        if (input.type === 'password') {
            input.type = 'text';
            icon.textContent = 'Hide';
        } else {
            input.type = 'password';
            icon.textContent = 'Show';
        }
    }
}

// Event handlers for real-time URI updates
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for URI preview updates
    const resticInputs = [
        'restic_rest_hostname', 'restic_rest_port', 'restic_rest_path', 'restic_rest_use_https',
        'restic_s3_endpoint', 'restic_s3_bucket', 'restic_s3_prefix',
        'restic_rclone_remote', 'restic_rclone_path',
        'restic_sftp_hostname', 'restic_sftp_username', 'restic_sftp_path'
    ];

    resticInputs.forEach(inputName => {
        const elements = document.getElementsByName(inputName);
        elements.forEach(element => {
            if (element.type === 'checkbox') {
                element.addEventListener('change', () => ResticURIUpdater.updatePreviews());
            } else {
                element.addEventListener('input', () => ResticURIUpdater.updatePreviews());
            }
        });
    });
});