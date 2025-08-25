/**
 * Clipboard utility functions for Highball
 */

function copyToClipboard(text, button) {
    if (!navigator.clipboard) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showCopyFeedback(button, true);
        } catch (err) {
            showCopyFeedback(button, false);
        }
        document.body.removeChild(textArea);
        return;
    }

    navigator.clipboard.writeText(text).then(function() {
        showCopyFeedback(button, true);
    }).catch(function() {
        showCopyFeedback(button, false);
    });
}

function showCopyFeedback(button, success) {
    if (!button) return;
    
    const originalText = button.textContent;
    const originalBg = button.style.backgroundColor;
    
    if (success) {
        button.textContent = 'Copied!';
        button.style.backgroundColor = '#28a745';
    } else {
        button.textContent = 'Copy failed';
        button.style.backgroundColor = '#dc3545';
    }
    
    setTimeout(function() {
        button.textContent = originalText;
        button.style.backgroundColor = originalBg;
    }, 2000);
}