# Notification Subsystem Documentation

Comprehensive notification system for Highball Backup Manager with per-job customization and spam-prevention queuing.

## Architecture Overview

### Core Components
- **`services/notification_service.py`** - Central notification service with `notifiers` library backend
- **`handlers/notification_test_handler.py`** - Test notification endpoints with detailed error handling
- **`handlers/config_handler.py`** - Global provider configuration management
- **`static/config-notifications.js`** - Test notification functionality with real-time feedback

### Provider System
- **Telegram** - Instant messaging with markdown support
- **Email** - SMTP-based notifications with TLS/SSL support
- **Extensible** - Ready for Slack, Discord, SMS via `notifiers` library (25+ providers available)

## Current Implementation Status

### ✅ Completed (2025-08-13)

#### Global Provider Configuration
- **Provider setup** - Configure Telegram bot tokens, email SMTP settings
- **Test notifications** - Real-time testing with comprehensive error handling
- **Modular UI** - Split configuration forms with provider-specific validation
- **Error handling** - User-friendly messages for common issues (auth failures, connection problems)

#### Per-Job Notification Foundation  
- **Dynamic provider selection** - Expandable dropdown system for multiple providers per job
- **Custom messages** - Success and failure messages with template variable support
- **Form integration** - New "Notifications" section between Source Options and Actions
- **Config schema** - Job-level notification arrays with provider-specific settings

#### Technical Infrastructure
- **Result validation** - Proper checking of `notifiers` library response objects  
- **Modular JavaScript** - Separated core config management from notification testing
- **Template system** - Support for `{job_name}`, `{duration}`, `{error_message}` variables
- **Comprehensive testing** - Both valid and invalid credential testing with appropriate feedback

## Configuration Schema

### Global Provider Settings
```yaml
global_settings:
  notification:
    telegram:
      enabled: true
      token: "bot_token_from_botfather"
      chat_id: "chat_or_group_id"
      queue_enabled: true           # Spam prevention
      queue_interval_minutes: 5     # Minimum time between messages
    email:
      enabled: true
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      use_tls: true
      from_email: "backup@company.com"
      to_email: "admin@company.com"
      username: "smtp_username"
      password: "smtp_password"
      queue_enabled: true
      queue_interval_minutes: 15    # Longer interval for email
```

### Per-Job Notification Settings
```yaml
backup_jobs:
  my-backup-job:
    # ... existing job configuration ...
    notifications:
      - provider: "telegram"
        notify_on_success: true
        success_message: "Backup '{job_name}' completed successfully in {duration}"
        notify_on_failure: true
        failure_message: "URGENT: Backup '{job_name}' failed - {error_message}"
      - provider: "email"
        notify_on_success: false    # Only failures via email
        notify_on_failure: true
        failure_message: "Backup Failure Report: {job_name} encountered an error: {error_message}"
```

## UI/UX Design

### Global Configuration Interface
- **Provider sections** - Expandable configuration for each provider
- **Test buttons** - "Send Test Notification" with immediate feedback
- **Clear labeling** - "Configure <provider>..." instead of generic "Enable" language
- **No spam controls at global level** - Moved to per-job for better UX

### Per-Job Notification Interface
- **Provider dropdowns** - Dynamic "Add Provider" selection
- **Progressive disclosure** - Options appear as providers are selected  
- **Custom messages** - Inline text fields with sensible defaults
- **Visual feedback** - Clear indication of configured vs available providers

## Message Queue System (Planned Implementation)

### Queue Architecture
- **Event-driven approach** - In-memory timers + file persistence for durability
- **Transient files** - Queue files only exist when needed, self-cleaning
- **Per-provider queues** - Independent spam prevention per notification method

### Queue File Structure
```yaml
# /var/log/highball/notification_queues/telegram_state.yaml
last_sent_timestamp: 1692123456
pending_messages:
  - timestamp: 1692123400
    title: "Job Failed: backup-job-1"
    message: "Error details..."
    type: "error"
    job_name: "backup-job-1"
```

### Queue Logic Flow
1. **Message arrives** → Check last_sent_timestamp vs queue_interval_minutes
2. **If interval elapsed** → Send immediately, update timestamp  
3. **If within interval** → Add to queue, set timer for batch send
4. **Batch processing** → Combine queued messages with summary formatting
5. **File cleanup** → Remove empty queue files, maintain active timers

### Batch Message Formats
- **Summary mode**: "3 failures, 1 delay in the last 15 minutes: backup-job-1 (failed), backup-job-2 (failed), backup-job-3 (delayed)"
- **Individual mode**: Full details for each message in chronological order
- **Custom batch messages**: User-configurable templates for queued sends

## Default Message Templates

### Success Messages
- **Default**: `"Job '{job_name}' completed successfully in {duration}"`
- **Variables**: `{job_name}`, `{duration}`, `{timestamp}`, `{source_paths}`

### Failure Messages  
- **Default**: `"Job '{job_name}' failed: {error_message}"`
- **Variables**: `{job_name}`, `{error_message}`, `{timestamp}`, `{source_paths}`, `{destination}`

### Delay Messages
- **Default**: `"Job '{job_name}' delayed {delay_minutes} minutes due to conflicts with: {conflicting_jobs}"`
- **Variables**: `{job_name}`, `{delay_minutes}`, `{conflicting_jobs}`, `{conflict_reason}`

## Error Handling and User Feedback

### Telegram-Specific Errors
- **Invalid token**: "Invalid bot token. Check your token from @BotFather"
- **Invalid chat ID**: "Invalid chat ID. Make sure the bot has been added to the chat"  
- **Permission issues**: "Bot is blocked or doesn't have permission to send messages"

### Email-Specific Errors
- **Authentication**: "Authentication failed. Check your username and password"
- **Connection**: "Connection refused. Check your SMTP server and port"
- **TLS/SSL**: "TLS/SSL error. Check your encryption settings"
- **Server resolution**: "SMTP server not found. Check your server address"

### General Error Patterns
- **Network issues**: Clear timeout and connection error messages
- **Configuration validation**: Field-specific requirement messages
- **Success confirmation**: Provider-specific success messages with next steps

## Testing and Validation

### Test Notification Endpoints
- **`/test-telegram-notification`** - POST endpoint with token/chat_id validation
- **`/test-email-notification`** - POST endpoint with SMTP configuration testing
- **Result checking** - Proper validation of `notifiers` library response objects
- **Error formatting** - Provider-specific error message formatting

### Integration Testing
- **Provider configuration** - Test all provider setup flows
- **Message delivery** - Verify actual notification delivery  
- **Error scenarios** - Test invalid credentials, network failures, server issues
- **Form validation** - Test required field validation, dropdown behavior

## Development Guidelines

### Adding New Providers
1. **Update `NotificationProviderFactory`** - Add provider creation method
2. **Update configuration templates** - Add provider-specific form fields
3. **Add JavaScript handling** - Provider-specific form validation and testing
4. **Update test handler** - Provider-specific error formatting
5. **Add to documentation** - Configuration examples and error messages

### Template Variable System
- **Built-in variables** - Job name, duration, error messages, timestamps
- **Context-specific** - Different variables available for success/failure/delay
- **Extensible** - Easy to add new variables for specific use cases
- **Validation** - Template syntax validation in form processing

### Queue System Extension Points
- **Custom batch formatters** - User-configurable message combining logic
- **Priority levels** - Different queue intervals for different message types
- **Provider-specific logic** - Custom handling per notification provider
- **Monitoring hooks** - Queue size, delivery rates, failure tracking

## Next Implementation Steps

### 1. Queue System Implementation
**Priority**: High - Core spam prevention functionality

**Components to build**:
- Queue state management with file persistence
- In-memory timer system for batch processing  
- Message batching with configurable formats
- Queue file cleanup and maintenance

**Integration points**:
- Hook into existing `NotificationService._send_via_provider`
- Add queue configuration to global settings UI
- Implement queue status monitoring and debugging

### 2. Advanced Template System
**Priority**: Medium - Enhanced customization

**Features to add**:
- Template syntax validation in forms
- Preview functionality for message templates
- More template variables (backup size, file counts, etc.)
- Conditional logic in templates

### 3. Provider Expansion
**Priority**: Low - Additional notification methods

**Candidates for implementation**:
- Slack webhook notifications
- Discord webhook notifications
- SMS via Twilio or similar service
- Generic webhook destinations

### 4. Monitoring and Analytics
**Priority**: Low - Operational insights

**Features to consider**:
- Notification delivery statistics
- Queue performance metrics
- Provider reliability tracking
- User notification preferences analytics

## Known Issues and Limitations

### Current Limitations
- **Queue system not implemented** - All notifications send immediately
- **No message deduplication** - Same messages may be sent multiple times
- **Limited template variables** - Basic set of job-related variables only
- **No notification history** - No log of sent notifications for review

### Technical Debt
- **Configuration validation** - Need stronger validation of provider settings
- **Error recovery** - Better handling of temporary provider failures
- **Performance optimization** - Queue processing may need optimization for high-volume
- **Testing coverage** - Need more comprehensive integration tests

### Security Considerations
- **Credential storage** - Provider tokens/passwords stored in plain text
- **Message content** - No sanitization of user-provided messages
- **Rate limiting** - No protection against notification spam from misconfiguration
- **Access control** - No user-level notification preferences

## Future Enhancements

### Short Term (Next Release)
- Complete queue system implementation with spam prevention
- Add message template preview functionality  
- Implement basic notification delivery logging
- Add configuration validation improvements

### Medium Term (Future Releases)
- Encrypted credential storage for provider settings
- Advanced template system with conditional logic
- Notification delivery statistics and monitoring
- Provider-specific configuration validation

### Long Term (Wishlist)
- Multi-user notification preferences
- Notification delivery scheduling (quiet hours)
- Integration with external monitoring systems
- Advanced message deduplication and threading

---

**Status**: Foundation Complete - Ready for Queue System Implementation

**Implementation Date**: August 13, 2025

**Next Steps**: Implement message queue system with spam prevention per provider configuration