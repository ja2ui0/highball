# =============================================================================
# JOB NOTIFICATION SCHEMA
# =============================================================================

# Job-level notification configuration schema (per provider)
JOB_NOTIFICATION_SCHEMA = {
    'display_name': 'Notification Configuration',
    'description': 'Configure when and how to receive notifications for this job',
    'fields': [
        {
            'name': 'notify_on_success',
            'type': 'checkbox',
            'label': 'Notify on Success',
            'help': 'Send notification when backup completes successfully',
            'default': False
        },
        {
            'name': 'success_message',
            'type': 'text',
            'label': 'Custom Success Message (optional)',
            'help': 'Custom message template. Variables: {job_name}, {duration}',
            'placeholder': "Job '{job_name}' completed successfully in {duration}",
            'required': False,
            'conditional': {
                'show_when': 'notify_on_success',
                'value': True
            }
        },
        {
            'name': 'notify_on_failure',
            'type': 'checkbox',
            'label': 'Notify on Failure',
            'help': 'Send notification when backup fails',
            'default': True
        },
        {
            'name': 'failure_message',
            'type': 'text',
            'label': 'Custom Failure Message (optional)',
            'help': 'Custom message template. Variables: {job_name}, {error_message}',
            'placeholder': "Job '{job_name}' failed: {error_message}",
            'required': False,
            'conditional': {
                'show_when': 'notify_on_failure',
                'value': True
            }
        },
        {
            'name': 'notify_on_maintenance_failure',
            'type': 'checkbox',
            'label': 'Notify on Maintenance Failure',
            'help': 'Send notification when repository maintenance operations fail',
            'default': False
        }
    ]
}

# =============================================================================
# JOB SCHEDULE SCHEMA
# =============================================================================

# Job schedule configuration schema
JOB_SCHEDULE_SCHEMA = {
    'display_name': 'Schedule Configuration',
    'description': 'Configure when the backup job should run',
    'schedule_options': [
        {
            'value': 'manual',
            'label': 'Manual Only',
            'description': 'Job will only run when manually triggered'
        },
        {
            'value': 'hourly',
            'label': 'Hourly',
            'description': 'Run every hour at the top of the hour',
            'cron_pattern': '0 * * * *'
        },
        {
            'value': 'daily',
            'label': 'Daily',
            'description': 'Run once per day at 3:00 AM',
            'cron_pattern': '0 3 * * *'
        },
        {
            'value': 'weekly',
            'label': 'Weekly',
            'description': 'Run once per week on Sunday at 3:00 AM',
            'cron_pattern': '0 3 * * 0'
        },
        {
            'value': 'monthly',
            'label': 'Monthly',
            'description': 'Run on the first day of each month at 3:00 AM',
            'cron_pattern': '0 3 1 * *'
        },
        {
            'value': 'custom',
            'label': 'Custom Cron Pattern',
            'description': 'Define a custom schedule using cron syntax'
        }
    ],
    'fields': [
        {
            'name': 'schedule',
            'type': 'select',
            'label': 'Schedule',
            'help': 'When should this backup job run?',
            'required': True,
            'default': 'manual'
        },
        {
            'name': 'cron_pattern',
            'type': 'text',
            'label': 'Cron Pattern',
            'help': 'Custom cron schedule (minute hour day month weekday)',
            'placeholder': '0 3 * * *',
            'conditional': {
                'show_when': 'schedule',
                'value': 'custom'
            }
        },
        {
            'name': 'enabled',
            'type': 'checkbox',
            'label': 'Enabled',
            'help': 'When enabled, this job will run according to its schedule',
            'default': True
        },
        {
            'name': 'respect_conflicts',
            'type': 'checkbox',
            'label': 'Wait for conflicting jobs (recommended)',
            'help': 'When enabled, this job will wait for other jobs using the same source or destination to finish',
            'default': True
        }
    ]
}

