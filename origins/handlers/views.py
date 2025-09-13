"""
Origins View Handlers (GET operations)
SSH origins management pages and read-only operations
"""

import logging
import time
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio

from shared.handlers.templating import TemplateService
from shared.handlers.errors import handle_page_errors
from shared.handlers.base import BaseHandler
from shared.services.config import ConfigReader
from origins.services.config import OriginConfigService
from origins.services.ssh import OriginSSHService

logger = logging.getLogger(__name__)


class OriginsViewHandler(BaseHandler):
    """Handle SSH origins read-only operations and page rendering"""
    
    def __init__(self):
        self.origin_config = OriginConfigService()
        self.config_reader = ConfigReader()
        self._init_template_service()
        self.ssh_service = OriginSSHService()
    
    @handle_page_errors("Show SSH origins")
    def show_ssh_origins(self) -> HTMLResponse:
        """Show SSH origins management page"""
        origins = self.config_reader.get_ssh_origins()
        # TODO: Remove global_settings dependency or get from admin config service
        global_settings = {}
        
        # Build origin display list
        origin_list = []
        for origin_name, origin_config in origins.items():
            # Determine authentication method display
            auth_method = "Highball SSH Key" if origin_config.get('ssh_highball', True) else "User SSH Key"
            
            # Connection info display
            connection_info = f"{origin_config.get('ssh_username')}@{origin_config.get('ssh_hostname')}:{origin_config.get('ssh_port', 22)}"
            
            # Capabilities display
            capabilities = []
            if origin_config.get('rsync_available'):
                capabilities.append("rsync")
            if origin_config.get('container_runtime'):
                capabilities.append(origin_config['container_runtime'])
            capabilities_display = ", ".join(capabilities) if capabilities else "Not detected"
            
            origin_display = {
                'name': origin_name,
                'friendly_name': origin_config.get('friendly_name', origin_name),
                'connection_info': connection_info,
                'auth_method': auth_method,
                'capabilities': capabilities_display,
                'config': origin_config
            }
            origin_list.append(origin_display)
        
        # Sort by friendly name for consistent display
        origin_list.sort(key=lambda x: x['friendly_name'].lower())
        
        template_data = {
            'origins': origin_list,
            'global_settings': global_settings,
            'theme_css_path': '',
            'page_title': 'SSH Origins'
        }
        
        return self._render_html('pages/ssh_config.html', template_data)

    @handle_page_errors("Edit SSH origin")
    def edit_ssh_origin(self, origin_name: str) -> HTMLResponse:
        """Load SSH origin for editing"""
        origin_config = self.config_reader.get_ssh_origin(origin_name)
        
        if not origin_config:
            # Return empty form if origin not found
            return self._render_html('partials/ssh_origin_form.html', {})
        
        # Create edit form with populated values including existing capabilities
        form_data = {
            'origin_name': origin_name,
            'friendly_name': origin_config.get('friendly_name', ''),
            'ssh_hostname': origin_config.get('ssh_hostname', ''),
            'ssh_username': origin_config.get('ssh_username', ''),
            'ssh_port': origin_config.get('ssh_port', 22),
            'ssh_timeout': origin_config.get('ssh_timeout', 5),
            'ssh_highball': origin_config.get('ssh_highball', True),
            'rsync_available': origin_config.get('rsync_available', False),
            'container_runtime': origin_config.get('container_runtime', None),
            'edit_mode': True  # Flag to indicate this is edit mode
        }
        
        return self._render_html('partials/ssh_origin_form.html', form_data)
    
    @handle_page_errors("SSH progress polling")
    def get_ssh_progress(self, session_id: str) -> HTMLResponse:
        """Get current SSH validation progress for a session using persistent storage"""
        # Get session progress from service
        session_data = self.ssh_service.read_session_progress(session_id)
        
        if not session_data['exists']:
            return self._render_html('partials/ssh_validation_expired.html', {
                'success': False,
                'validation_message': "Session not found or expired"
            })
        
        progress_text = '\n'.join(session_data['progress'])
        
        if not session_data['completed']:
            # Still in progress - return progress template with polling
            return self._render_html('partials/ssh_validation_progress.html', {
                'session_id': session_id,
                'initial_message': progress_text
            })
        else:
            # Completed - return final result and schedule cleanup
            result = session_data['result']
            result['edit_mode'] = session_data['edit_mode']
            # DISABLE session cleanup - known HTMX polling issue
            # Sessions accumulate but validation completes without console spam
            pass
            return self._render_html('partials/ssh_validation_result.html', result)
    
    @handle_page_errors("SSH progress streaming")
    async def stream_ssh_progress(self, session_id: str, request: Request) -> StreamingResponse:
        """Stream SSH validation progress using Server-Sent Events"""
        async def event_generator():
            last_progress_count = 0
            max_wait_time = 60  # Maximum wait time in seconds
            start_time = time.time()
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                    
                # Check for timeout
                if time.time() - start_time > max_wait_time:
                    error_result = {
                        'success': False, 
                        'validation_message': 'Validation timeout. Please try again.',
                        'edit_mode': False
                    }
                    inner_error_html = self.template_service.render_template('partials/ssh_validation_result.html', **error_result)
                    final_html = self.template_service.render_template('partials/ssh_validation_final_result.html', 
                                                                     result_html=inner_error_html)
                    # Remove newlines and extra whitespace from HTML for SSE
                    final_html = ' '.join(final_html.split())
                    yield f"event: error\ndata: {final_html}\n\n"
                    break
                
                # Get session progress from service
                session_data = self.ssh_service.read_session_progress(session_id)
                
                # Wait for session to be created (don't immediately error)
                if not session_data['exists']:
                    await asyncio.sleep(0.5)
                    continue
                
                # Send new progress messages  
                current_progress = session_data['progress']
                if len(current_progress) > last_progress_count:
                    progress_content = "<br>".join(current_progress)
                    progress_html = self.template_service.render_template('partials/ssh_validation_progress_update.html', 
                                                                       progress_content=progress_content)
                    progress_html = ' '.join(progress_html.split())
                    yield f"event: progress\ndata: {progress_html}\n\n"
                    last_progress_count = len(current_progress)
                
                # Check if completed
                if session_data['completed']:
                    result = session_data['result']
                    result['edit_mode'] = session_data['edit_mode']
                    
                    # Render the final result template
                    inner_result_html = self.template_service.render_template('partials/ssh_validation_result.html', **result)
                    final_html = self.template_service.render_template('partials/ssh_validation_final_result.html', 
                                                                     result_html=inner_result_html)
                    # Remove newlines and extra whitespace from HTML for SSE
                    final_html = ' '.join(final_html.split())
                    event_type = "success" if result['success'] else "error"
                    yield f"event: {event_type}\ndata: {final_html}\n\n"
                    
                    # Clean up session after successful completion
                    self.ssh_service.cleanup_session(session_id)
                    break
                
                await asyncio.sleep(0.5)  # Poll every 500ms
        
        return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })


# Global handler instance
origins_view_handler = OriginsViewHandler()