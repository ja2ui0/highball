"""
HTMX Rsyncd Management Service
Handles rsyncd share discovery and validation for HTMX endpoints
"""
import logging
import html

logger = logging.getLogger(__name__)


class HTMXRsyncdManager:
    """Manages rsyncd operations for HTMX endpoints"""
    
    def __init__(self):
        pass
    
    def render_discovery_result(self, success, message, shares=None, hostname=None, tested_from=None):
        """Render rsync discovery result"""
        if success:
            color = 'var(--success-color, #22c55e)'
            share_options = ''
            if shares:
                for share in shares:
                    share_options += f'<option value="{html.escape(share)}">{html.escape(share)}</option>'
                
                details = [
                    f'<strong>Discovery Results:</strong>',
                    f'- Found {len(shares)} shares on {hostname}',
                ]
                if tested_from:
                    details.append(f'- Tested from: {tested_from}')
                details.append(f'- Available shares: {", ".join(shares)}')
                
                details_content = '<br>'.join(details)
                
                return f'''
                <div style="color: {color}">{html.escape(message)}</div>
                <div class="validation-details mt-10">
                    {details_content}
                </div>
                <div class="form-group mt-10" id="share_selection">
                    <label for="dest_rsyncd_share">Select Share:</label>
                    <select name="dest_rsyncd_share" id="dest_rsyncd_share">
                        <option value="">Choose a share...</option>
                        {share_options}
                    </select>
                    <div class="help-text">Select the rsync module/share to use</div>
                </div>
                '''
            else:
                return f'<div style="color: {color}">{html.escape(message)}</div>'
        else:
            color = 'var(--error-color, #ef4444)'
            error_content = f'<strong>Error:</strong> {html.escape(message)}'
            return f'''
            <div style="color: {color}">{error_content}</div>
            <div class="hidden" id="share_selection"></div>
            '''
    
    def render_loading_state(self):
        """Render loading state for discovery"""
        color = 'var(--warning-color, #f59e0b)'
        return f'<div style="color: {color}">Discovering shares...</div>'
    
    def render_validation_result(self, success, message, details=None):
        """Render rsyncd validation result"""
        if success:
            color = 'var(--success-color, #22c55e)'
        else:
            color = 'var(--error-color, #ef4444)'
        
        result = f'<div style="color: {color}">{html.escape(message)}</div>'
        
        if details:
            details_content = '<br>'.join(f'- {html.escape(detail)}' for detail in details)
            result += f'<div class="validation-details mt-10">{details_content}</div>'
        
        return result