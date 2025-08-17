/**
 * Notifications Form JavaScript
 * Handles notification provider management for job forms
 */

let availableProviders = [];  // Will be populated from server
let configuredProviders = []; // Track what's already configured

function initializeNotificationProviders() {
    // This will be called on page load to populate available providers
    try {
        const container = document.getElementById('notification_providers');
        if (!container) {
            console.log('No notification_providers container found');
            return;
        }
        
        const providersJson = container.dataset.availableProviders;
        if (providersJson && providersJson !== '') {
            availableProviders = JSON.parse(providersJson);
        }
        
        // Initialize existing providers for edit mode
        const existingProvidersJson = container.dataset.existingNotifications;
        if (existingProvidersJson && existingProvidersJson !== '') {
            const existingProviders = JSON.parse(existingProvidersJson);
            existingProviders.forEach(providerConfig => {
                addExistingNotificationProvider(providerConfig);
            });
        }
        
        updateAvailableProviders();
    } catch (error) {
        console.log('Could not initialize notification providers:', error);
    }
}

function addNotificationProvider() {
    const select = document.getElementById('add_notification_provider');
    const providerName = select.value;
    
    if (!providerName) return;
    
    // Create new provider configuration
    const template = document.getElementById('notification_template');
    const newProvider = template.cloneNode(true);
    newProvider.id = `notification_${providerName}_${Date.now()}`;
    newProvider.classList.remove('hidden');
    
    // Configure the provider
    const providerHeader = newProvider.querySelector('.provider-name');
    providerHeader.textContent = providerName.charAt(0).toUpperCase() + providerName.slice(1);
    
    const hiddenField = newProvider.querySelector('.provider-name-hidden');
    hiddenField.value = providerName;
    
    // Add to configured providers
    configuredProviders.push(providerName);
    
    // Add to the container
    const container = document.getElementById('notification_providers');
    container.appendChild(newProvider);
    
    // Update available providers dropdown
    updateAvailableProviders();
    
    // Reset selection
    select.value = '';
}

function addExistingNotificationProvider(config) {
    // Add provider configuration from existing job config
    const template = document.getElementById('notification_template');
    const newProvider = template.cloneNode(true);
    newProvider.id = `notification_${config.provider}_existing`;
    newProvider.classList.remove('hidden');
    
    // Configure the provider
    const providerHeader = newProvider.querySelector('.provider-name');
    providerHeader.textContent = config.provider.charAt(0).toUpperCase() + config.provider.slice(1);
    
    const hiddenField = newProvider.querySelector('.provider-name-hidden');
    hiddenField.value = config.provider;
    
    // Set success notification
    const successCheckbox = newProvider.querySelector('.notify-success-checkbox');
    const successMessageGroup = newProvider.querySelector('.success-message-group');
    const successMessageInput = newProvider.querySelector('.success-message-input');
    
    if (config.notify_on_success) {
        successCheckbox.checked = true;
        successMessageGroup.classList.remove('hidden');
        successMessageInput.value = config.success_message || '';
    }
    
    // Set failure notification
    const failureCheckbox = newProvider.querySelector('.notify-failure-checkbox');
    const failureMessageGroup = newProvider.querySelector('.failure-message-group');
    const failureMessageInput = newProvider.querySelector('.failure-message-input');
    
    if (config.notify_on_failure) {
        failureCheckbox.checked = true;
        failureMessageGroup.classList.remove('hidden');
        failureMessageInput.value = config.failure_message || '';
    }
    
    // Set maintenance failure notification
    const maintenanceFailureCheckbox = newProvider.querySelector('.notify-maintenance-failure-checkbox');
    if (config.notify_on_maintenance_failure) {
        maintenanceFailureCheckbox.checked = true;
    }
    
    // Add to configured providers
    configuredProviders.push(config.provider);
    
    // Add to the container
    const container = document.getElementById('notification_providers');
    container.appendChild(newProvider);
}

function removeNotificationProvider(button) {
    const providerDiv = button.closest('.notification-provider');
    const hiddenField = providerDiv.querySelector('.provider-name-hidden');
    const providerName = hiddenField.value;
    
    // Remove from configured providers
    const index = configuredProviders.indexOf(providerName);
    if (index > -1) {
        configuredProviders.splice(index, 1);
    }
    
    // Remove the provider div
    providerDiv.remove();
    
    // Update available providers dropdown
    updateAvailableProviders();
}

function toggleSuccessMessage(checkbox) {
    const messageGroup = checkbox.closest('.form-group').querySelector('.success-message-group');
    messageGroup.classList.toggle('hidden', !checkbox.checked);
}

function toggleFailureMessage(checkbox) {
    const messageGroup = checkbox.closest('.form-group').querySelector('.failure-message-group');
    messageGroup.classList.toggle('hidden', !checkbox.checked);
}

function updateAvailableProviders() {
    const select = document.getElementById('add_notification_provider');
    const availableOptions = availableProviders.filter(provider => 
        !configuredProviders.includes(provider)
    );
    
    // Clear existing options except the first
    while (select.children.length > 1) {
        select.removeChild(select.lastChild);
    }
    
    // Add available providers
    availableOptions.forEach(provider => {
        const option = document.createElement('option');
        option.value = provider;
        option.textContent = provider.charAt(0).toUpperCase() + provider.slice(1);
        select.appendChild(option);
    });
    
    // Hide dropdown if no providers available
    const addProviderGroup = select.closest('.form-group');
    if (availableOptions.length === 0) {
        addProviderGroup.style.display = 'none';
    } else {
        addProviderGroup.style.display = 'block';
    }
}