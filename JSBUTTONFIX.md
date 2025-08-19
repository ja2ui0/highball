# JavaScript Button Fix for Add Source Path

## Problem
The "Add Another Path" button in the source options section would not respond to HTMX, despite other HTMX buttons on the same page working correctly.

## Root Cause
HTMX was not properly binding to this specific button, likely due to how it's rendered via template includes after initial page load.

## Working JavaScript Solution

Replace the HTMX button attributes with a simple onclick handler:

```html
<button type="button" class="button button-secondary" 
        onclick="addSourcePath()">
    <span class="button-icon">+</span> Add Another Path
</button>
```

Add this inline JavaScript to the template:

```javascript
<script>
function addSourcePath() {
    console.log('addSourcePath called');
    
    // Collect form data
    const formData = new FormData();
    const pathFields = document.querySelectorAll('[name="source_path[]"]');
    const includeFields = document.querySelectorAll('[name="source_includes[]"]');
    const excludeFields = document.querySelectorAll('[name="source_excludes[]"]');
    
    pathFields.forEach(field => formData.append('source_path[]', field.value));
    includeFields.forEach(field => formData.append('source_includes[]', field.value));
    excludeFields.forEach(field => formData.append('source_excludes[]', field.value));
    
    // Make AJAX request
    fetch('/htmx/add-source-path', {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(html => {
        console.log('Got response, updating container');
        document.getElementById('source_paths_container').innerHTML = html;
    })
    .catch(error => {
        console.error('Error:', error);
    });
}
</script>
```

## What This Does
1. Manually collects all source field data using querySelector
2. Uses vanilla JavaScript fetch() to POST to the same HTMX endpoint
3. Updates the DOM by replacing the innerHTML of the target container
4. Bypasses HTMX entirely but achieves the same result

## File Location
`templates/partials/source_paths_container_content.html`

## Note
This is a fallback solution. The preferred approach is to fix the HTMX binding issue.