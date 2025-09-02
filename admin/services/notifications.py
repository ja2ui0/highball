#!/usr/bin/env python3
"""
Admin Notification Services

Notification testing and administration functionality.
"""
import logging
from typing import Dict, Any
from fastapi.responses import JSONResponse

from jobs.services.notify import create_notification_service

logger = logging.getLogger(__name__)


class NotificationTestService:
    """Service for testing notification providers - moved from handlers/api.py"""
    
    def __init__(self, backup_config):
        self.backup_config = backup_config
        self.notification_service = create_notification_service(backup_config.get_global_settings())
    
    def test_telegram_notification(self, test_message: str = 'Test notification from Highball') -> JSONResponse:
        """Test Telegram notification"""
        result = self.notification_service.test_provider('telegram')
        return JSONResponse(content=result)
    
    def test_email_notification(self, test_message: str = 'Test notification from Highball') -> JSONResponse:
        """Test email notification"""
        result = self.notification_service.test_provider('email')
        return JSONResponse(content=result)