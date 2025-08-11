// Network scanning functionality for rsync servers
document.addEventListener('DOMContentLoaded', function() {
    const scanButton = document.getElementById('scanNetwork');
    if (!scanButton) return; // Only run if the scan button exists on the page
    
    scanButton.addEventListener('click', function() {
        const button = this;
        const networkRange = document.getElementById('networkRange').value || '192.168.1.0/24';
        const resultsDiv = document.getElementById('scanResults');
        const outputDiv = document.getElementById('scanOutput');
        
        // Disable button and show loading
        button.disabled = true;
        button.textContent = 'Scanning...';
        resultsDiv.style.display = 'block';
        outputDiv.textContent = 'Scanning network for rsync daemons...\n';
        
        // Start scan
        fetch(`/scan-network?range=${encodeURIComponent(networkRange)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    outputDiv.textContent = `Error: ${data.error}`;
                } else {
                    let output = `Scanned ${data.total_checked} addresses in ${data.network_range}\n`;
                    output += `Found ${data.found_servers} rsync servers:\n\n`;
                    
                    if (data.servers.length > 0) {
                        data.servers.forEach(server => {
                            output += `Server: ${server.ip}\n`;
                            server.modules.forEach(module => {
                                output += `  ${module.path}`;
                                if (module.description) {
                                    output += ` - ${module.description}`;
                                }
                                output += '\n';
                            });
                            output += '\n';
                        });
                    } else {
                        output += 'No rsync servers found.\n';
                    }
                    
                    outputDiv.textContent = output;
                }
            })
            .catch(error => {
                outputDiv.textContent = `Error: ${error.message}`;
            })
            .finally(() => {
                button.disabled = false;
                button.textContent = 'Scan Network for Rsync Servers';
            });
    });
});