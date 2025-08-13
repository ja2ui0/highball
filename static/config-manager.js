// Configuration manager core functionality
document.addEventListener('DOMContentLoaded', function() {
    // Generic toggle function for notification settings
    const toggleSettings = (checkboxId, settingsId) => {
        const checkbox = document.getElementById(checkboxId);
        const settings = document.getElementById(settingsId);
        if (checkbox && settings) {
            settings.classList.toggle('hidden', !checkbox.checked);
        }
    };
    
    // Initialize Telegram settings toggle
    const telegramCheckbox = document.getElementById('enable_telegram');
    if (telegramCheckbox) {
        telegramCheckbox.addEventListener('change', () => 
            toggleSettings('enable_telegram', 'telegramSettings')
        );
        // Initialize visibility on page load
        toggleSettings('enable_telegram', 'telegramSettings');
    }
    
    // Initialize Email settings toggle  
    const emailCheckbox = document.getElementById('enable_email');
    if (emailCheckbox) {
        emailCheckbox.addEventListener('change', () => 
            toggleSettings('enable_email', 'emailSettings')
        );
        // Initialize visibility on page load
        toggleSettings('enable_email', 'emailSettings');
    }
});

// Legacy function names for backward compatibility with inline handlers
function toggleTelegramSettings() {
    const checkbox = document.getElementById('enable_telegram');
    const settings = document.getElementById('telegramSettings');
    if (checkbox && settings) {
        settings.classList.toggle('hidden', !checkbox.checked);
    }
}

function toggleEmailSettings() {
    const checkbox = document.getElementById('enable_email');
    const settings = document.getElementById('emailSettings');
    if (checkbox && settings) {
        settings.classList.toggle('hidden', !checkbox.checked);
    }
}