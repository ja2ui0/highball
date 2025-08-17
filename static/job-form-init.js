/**
 * Job Form Initialization JavaScript
 * Handles form initialization, cron field display, and source paths population
 */

// Initialize form display based on current values
document.addEventListener('DOMContentLoaded', function() {
    showSourceFields();
    showDestFields();
    showCronField();
    initializeSourcePaths();
    initializeNotificationProviders();
});

function showCronField() {
    const schedule = document.getElementById('schedule').value;
    const cronField = document.getElementById('cron_field');
    if (schedule === 'cron') {
        cronField.classList.remove('hidden');
    } else {
        cronField.classList.add('hidden');
    }
}

function initializeSourcePaths() {
    // Initialize source paths from server data for edit forms
    try {
        const container = document.getElementById('source_paths_container');
        if (!container) {
            console.log('No source_paths_container found');
            return;
        }
        
        const sourcePathsJson = container.dataset.sourcePaths;
        console.log('SOURCE_PATHS_JSON:', sourcePathsJson);
        
        if (sourcePathsJson && sourcePathsJson !== '') {
            const sourcePaths = JSON.parse(sourcePathsJson);
            console.log('Parsed source paths:', sourcePaths);
            
            // Check if addPath function exists
            if (typeof addPath !== 'function') {
                console.log('addPath function not found');
                return;
            }
            
            // Get existing path entries (should include the default first path)
            let pathEntries = container.querySelectorAll('.path-entry:not(#path_entry_template)');
            
            // Populate each path from the configuration
            sourcePaths.forEach((pathData, index) => {
                console.log('Processing path:', pathData);
                
                // If we need more path entries than we have, add them
                if (index >= pathEntries.length) {
                    addPath();
                    pathEntries = container.querySelectorAll('.path-entry:not(#path_entry_template)');
                }
                
                // Get the path entry for this index
                const pathEntry = pathEntries[index];
                
                if (pathEntry) {
                    // Populate the fields
                    const pathInput = pathEntry.querySelector('input[name="source_paths[]"]');
                    const includesInput = pathEntry.querySelector('textarea[name="source_includes[]"]');
                    const excludesInput = pathEntry.querySelector('textarea[name="source_excludes[]"]');
                    
                    if (pathInput) pathInput.value = pathData.path || '';
                    if (includesInput) includesInput.value = pathData.includes ? pathData.includes.join('\n') : '';
                    if (excludesInput) excludesInput.value = pathData.excludes ? pathData.excludes.join('\n') : '';
                    
                    console.log('Populated path entry', index + 1, ':', pathData.path);
                } else {
                    console.log('Could not find path entry', index + 1);
                }
            });
        } else {
            console.log('No SOURCE_PATHS_JSON data');
        }
    } catch (error) {
        console.log('Could not initialize source paths:', error);
        // Fallback: ensure at least one path exists
        if (typeof addPath === 'function') {
            const existingPaths = document.querySelectorAll('.path-entry:not(#path_entry_template)');
            if (existingPaths.length === 0) {
                addPath();
            }
        }
    }
}