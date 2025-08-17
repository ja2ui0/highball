/**
 * Restic utility functions for HTMX forms
 */

function initializeResticRepository() {
    // Get form data from the current form
    const form = document.querySelector('form');
    if (!form) {
        console.error('No form found for repository initialization');
        return;
    }
    
    const formData = new FormData(form);
    
    // Show loading state
    const button = document.getElementById('init_restic_button');
    if (button) {
        button.disabled = true;
        button.textContent = 'Initializing...';
    }
    
    // Use HTMX to send initialization request
    fetch('/htmx/initialize-restic', {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(html => {
        // Update the validation area with the result
        const validationArea = document.getElementById('restic_validation_status') || 
                              document.querySelector('.validation-result');
        if (validationArea) {
            validationArea.innerHTML = html;
        }
        
        // Re-enable button
        if (button) {
            button.disabled = false;
            button.textContent = 'Initialize Repository';
        }
    })
    .catch(error => {
        console.error('Repository initialization error:', error);
        
        // Show error message
        const validationArea = document.getElementById('restic_validation_status') || 
                              document.querySelector('.validation-result');
        if (validationArea) {
            validationArea.innerHTML = `<div class="validation-error">[ERROR] Initialization failed: ${error.message}</div>`;
        }
        
        // Re-enable button
        if (button) {
            button.disabled = false;
            button.textContent = 'Initialize Repository';
        }
    });
}