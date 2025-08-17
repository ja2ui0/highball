"""
HTMX Source Path Manager Service
Handles dynamic source path management for multi-path backup configurations
"""

import logging

logger = logging.getLogger(__name__)

class HTMXSourcePathManager:
    """Manages source path operations for HTMX"""
    
    def render_source_paths_container(self, paths_data=None):
        """Render complete source paths container with existing paths"""
        if not paths_data:
            # Default to one empty path
            paths_data = [{'path': '', 'includes': '', 'excludes': ''}]
        
        paths_html = []
        for i, path_data in enumerate(paths_data):
            paths_html.append(self._render_single_path_entry(i, path_data, len(paths_data) > 1))
        
        # Add button for adding more paths
        add_button_html = self._render_add_path_button(len(paths_data))
        
        return ''.join(paths_html) + add_button_html
    
    def add_new_path(self, form_data):
        """Add a new path entry and return updated container"""
        existing_paths = self._extract_paths_from_form(form_data)
        new_path = {'path': '', 'includes': '', 'excludes': ''}
        existing_paths.append(new_path)
        
        return self.render_source_paths_container(existing_paths)
    
    def remove_path(self, form_data, path_index):
        """Remove path at index and return updated container"""
        existing_paths = self._extract_paths_from_form(form_data)
        
        if 0 <= path_index < len(existing_paths) and len(existing_paths) > 1:
            existing_paths.pop(path_index)
        
        # Ensure at least one path exists
        if not existing_paths:
            existing_paths = [{'path': '', 'includes': '', 'excludes': ''}]
        
        return self.render_source_paths_container(existing_paths)
    
    def _render_single_path_entry(self, index, path_data, show_remove_button=True):
        """Render a single path entry"""
        path = self._escape_html(path_data.get('path', ''))
        includes = self._escape_html(path_data.get('includes', ''))
        excludes = self._escape_html(path_data.get('excludes', ''))
        
        remove_button = ''
        if show_remove_button:
            remove_button = f'''
            <button type="button" class="remove-path-btn button button-danger" 
                    hx-post="/htmx/remove-source-path" 
                    hx-vals='{{"path_index": "{index}"}}'
                    hx-target="#source_paths_container"
                    hx-include="#source_paths_container [name]">Remove</button>
            '''
        
        return f'''
        <div class="path-entry" data-path-index="{index}">
            <div class="path-group">
                <h3 class="path-header">
                    <span>Source Path {index + 1}</span>
                    {remove_button}
                </h3>
                
                <div class="form-group">
                    <label for="source_path_{index}">Path:</label>
                    <input type="text" id="source_path_{index}" name="source_paths[]" 
                           value="{path}" placeholder="/path/to/backup">
                    <div class="path-validation-row">
                        <button type="button" class="validate-path-btn button button-secondary" 
                                hx-post="/htmx/validate-single-source-path" 
                                hx-target="#path_validation_{index}"
                                hx-vals='{{"path_index": "{index}"}}'
                                hx-include="#source_path_{index}, [name='source_ssh_hostname'], [name='source_ssh_username']">
                            Validate Path
                        </button>
                        <div id="path_validation_{index}" class="path-validation-result"></div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="source_includes_{index}">Include Patterns (optional):</label>
                    <textarea id="source_includes_{index}" name="source_includes[]" 
                              placeholder="**/*.jpg&#10;documents/**&#10;config.ini">{includes}</textarea>
                    <div class="help-text">
                        Glob patterns for files to include. Leave empty to include all files.
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="source_excludes_{index}">Exclude Patterns (optional):</label>
                    <textarea id="source_excludes_{index}" name="source_excludes[]" 
                              placeholder="**/*.tmp&#10;cache/**&#10;*.log">{excludes}</textarea>
                    <div class="help-text">
                        Glob patterns for files to exclude. Common: temp files, logs, caches.
                    </div>
                </div>
            </div>
        </div>
        '''
    
    def _render_add_path_button(self, current_count):
        """Render the add path button"""
        return f'''
        <div class="add-path-section">
            <button type="button" class="button button-secondary" 
                    hx-post="/htmx/add-source-path" 
                    hx-target="#source_paths_container"
                    hx-include="#source_paths_container [name]">
                Add Another Path
            </button>
        </div>
        '''
    
    def _extract_paths_from_form(self, form_data):
        """Extract existing source paths from form data"""
        paths = form_data.get('source_paths[]', [])
        includes = form_data.get('source_includes[]', [])
        excludes = form_data.get('source_excludes[]', [])
        
        # Handle single values vs lists
        if not isinstance(paths, list):
            paths = [paths] if paths else []
        if not isinstance(includes, list):
            includes = [includes] if includes else []
        if not isinstance(excludes, list):
            excludes = [excludes] if excludes else []
        
        # Build path data structures
        result = []
        max_len = max(len(paths), len(includes), len(excludes)) if any([paths, includes, excludes]) else 1
        
        for i in range(max_len):
            path_data = {
                'path': paths[i] if i < len(paths) else '',
                'includes': includes[i] if i < len(includes) else '',
                'excludes': excludes[i] if i < len(excludes) else ''
            }
            # Only include non-empty paths or the first entry
            if path_data['path'] or i == 0:
                result.append(path_data)
        
        return result if result else [{'path': '', 'includes': '', 'excludes': ''}]
    
    def _escape_html(self, text):
        """Basic HTML escaping for form values"""
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))