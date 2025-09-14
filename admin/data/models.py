"""
Admin Domain Data Models
Pydantic models for admin service operations and responses
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


# =============================================================================
# CONFIG OPERATION MODELS
# =============================================================================

class ConfigSaveResult(BaseModel):
    """Result from saving configuration changes"""
    success: bool
    error: Optional[str] = None
    yaml_content: Optional[str] = None
    preview_config: Optional[Dict[str, Any]] = None


class ConfigPreviewResult(BaseModel):
    """Result from previewing configuration changes"""
    success: bool
    preview_content: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# PROVIDER OPERATION MODELS
# =============================================================================

class ProviderOperationResult(BaseModel):
    """Result from adding or removing notification providers"""
    success: bool
    provider: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# THEME MODELS
# =============================================================================

class ThemeListResult(BaseModel):
    """Result from listing available themes"""
    themes: List[str] = Field(default_factory=list)


class RawConfigSaveResult(BaseModel):
    """Result from saving raw YAML configuration"""
    success: bool
    error: Optional[str] = None


# =============================================================================
# NOTIFICATION PROVIDER CONFIG MODELS
# =============================================================================

class TelegramConfig(BaseModel):
    """Telegram notification provider configuration"""
    enabled: bool = False
    token: str = Field(..., min_length=1, description="Bot token from @BotFather")
    chat_id: str = Field(..., min_length=1, description="Chat or group ID for notifications")
    queue_enabled: bool = False
    queue_interval_minutes: int = Field(default=5, ge=1, le=1440, description="Minimum minutes between batched messages")


class EmailConfig(BaseModel):
    """Email notification provider configuration"""
    enabled: bool = False
    smtp_server: str = Field(..., min_length=1, description="SMTP server hostname")
    smtp_port: int = Field(..., ge=1, le=65535, description="SMTP server port")
    encryption: str = Field(default="tls", pattern="^(tls|ssl|none)$", description="Encryption method")
    from_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="From email address")
    to_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="To email address")
    username: Optional[str] = Field(default=None, description="SMTP username (usually email)")
    password: Optional[str] = Field(default=None, description="SMTP password")
    queue_enabled: bool = False
    queue_interval_minutes: int = Field(default=15, ge=1, le=1440, description="Minimum minutes between batched messages")


# =============================================================================
# GLOBAL SETTINGS CONFIG MODELS
# =============================================================================

class DefaultScheduleTimes(BaseModel):
    """Default schedule time patterns"""
    hourly: str = Field(default="0 * * * *", description="Hourly cron pattern")
    daily: str = Field(default="0 3 * * *", description="Daily cron pattern")
    weekly: str = Field(default="0 3 * * 0", description="Weekly cron pattern")
    monthly: str = Field(default="0 3 1 * *", description="Monthly cron pattern")


class NotificationSettings(BaseModel):
    """Complete notification configuration"""
    telegram: Optional[TelegramConfig] = None
    email: Optional[EmailConfig] = None


class GlobalSettings(BaseModel):
    """Global system configuration settings"""
    scheduler_timezone: str = Field(default="UTC", description="Timezone for job scheduling")
    theme: str = Field(default="dark", description="UI theme name")
    enable_conflict_avoidance: bool = Field(default=True, description="Enable job conflict detection")
    conflict_check_interval: int = Field(default=300, ge=1, description="Conflict check interval in seconds")
    delay_notification_threshold: int = Field(default=300, ge=1, description="Delay before sending notifications")
    default_schedule_times: DefaultScheduleTimes = Field(default_factory=DefaultScheduleTimes)
    notification: NotificationSettings = Field(default_factory=NotificationSettings)