// Configuration manager notification testing functionality

// Test notification functions for global configuration
function testTelegramNotification() {
    const button = document.getElementById('test_telegram');
    const resultDiv = document.getElementById('telegram_test_result');
    
    if (!button || !resultDiv) return;
    
    // Disable button and show loading
    button.disabled = true;
    button.textContent = 'Sending...';
    resultDiv.textContent = 'Testing notification...';
    resultDiv.className = 'help-text';
    
    // Get form data
    const token = document.getElementById('telegram_token').value;
    const chatId = document.getElementById('telegram_chat_id').value;
    
    if (!token || !chatId) {
        showTestResult('telegram', 'Error: Bot token and chat ID are required', 'error');
        return;
    }
    
    // Send test request using FormData
    const formData = new FormData();
    formData.append('token', token);
    formData.append('chat_id', chatId);
    
    fetch('/test-telegram-notification', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showTestResult('telegram', data.message, data.success ? 'success' : 'error');
    })
    .catch(error => {
        showTestResult('telegram', `Network error: ${error.message}`, 'error');
    });
}

function testEmailNotification() {
    const button = document.getElementById('test_email');
    const resultDiv = document.getElementById('email_test_result');
    
    if (!button || !resultDiv) return;
    
    // Disable button and show loading
    button.disabled = true;
    button.textContent = 'Sending...';
    resultDiv.textContent = 'Testing notification...';
    resultDiv.className = 'help-text';
    
    // Get form data
    const smtpServer = document.getElementById('email_smtp_server').value;
    const smtpPort = document.getElementById('email_smtp_port').value;
    const fromEmail = document.getElementById('email_from').value;
    const toEmail = document.getElementById('email_to').value;
    const username = document.getElementById('email_username').value;
    const password = document.getElementById('email_password').value;
    
    // Get encryption method
    let encryption = 'tls';
    const encryptionRadios = document.getElementsByName('email_encryption');
    for (let radio of encryptionRadios) {
        if (radio.checked) {
            encryption = radio.value;
            break;
        }
    }
    
    // Validate required fields
    if (!smtpServer || !fromEmail || !toEmail) {
        showTestResult('email', 'Error: SMTP server, from email, and to email are required', 'error');
        return;
    }
    
    // Prepare FormData
    const formData = new FormData();
    formData.append('smtp_server', smtpServer);
    formData.append('smtp_port', smtpPort);
    formData.append('from_email', fromEmail);
    formData.append('to_email', toEmail);
    formData.append('username', username);
    formData.append('password', password);
    formData.append('encryption', encryption);
    
    // Send test request
    fetch('/test-email-notification', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showTestResult('email', data.message, data.success ? 'success' : 'error');
    })
    .catch(error => {
        showTestResult('email', `Network error: ${error.message}`, 'error');
    });
}

function showTestResult(provider, message, type) {
    const button = document.getElementById(`test_${provider}`);
    const resultDiv = document.getElementById(`${provider}_test_result`);
    
    // Reset button
    button.disabled = false;
    button.textContent = 'Send Test Notification';
    
    // Show result with styling based on type
    resultDiv.textContent = message;
    
    // Apply appropriate styling
    resultDiv.className = 'help-text';
    if (type === 'success') {
        resultDiv.style.color = 'var(--success-color, #22c55e)';
    } else if (type === 'error') {
        resultDiv.style.color = 'var(--error-color, #ef4444)';
    } else if (type === 'warning') {
        resultDiv.style.color = 'var(--warning-color, #f59e0b)';
    } else {
        resultDiv.style.color = '';
    }
}