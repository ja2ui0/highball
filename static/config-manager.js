// Configuration manager form interactions
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