#!/usr/bin/env python3
"""
Test script for notification system
Tests Telegram and email notification functionality
"""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BackupConfig
from services.notification_service import NotificationService, NotificationManager


def test_notification_config():
    """Test notification configuration loading"""
    print("🔧 Testing Notification Configuration")
    print("=" * 50)
    
    # Load config
    backup_config = BackupConfig()
    notifier = NotificationService(backup_config)
    
    print(f"Notifications enabled: {notifier.is_notifications_enabled()}")
    print(f"Telegram enabled: {notifier.is_telegram_enabled()}")
    print(f"Email enabled: {notifier.is_email_enabled()}")
    
    # Show configuration template
    print("\n📋 Configuration Template:")
    print("Add this to your config.yaml global_settings:")
    template = NotificationManager.get_notification_config_template()
    
    import yaml
    print(yaml.dump(template, default_flow_style=False, indent=2))
    
    return notifier


def test_telegram_notification(notifier):
    """Test Telegram notification if configured"""
    print("\n📱 Testing Telegram Notifications")
    print("=" * 50)
    
    if not notifier.is_telegram_enabled():
        print("❌ Telegram not configured - skipping test")
        print("Configure telegram_token and telegram_chat_id in your config")
        return False
    
    try:
        success = notifier._send_telegram(
            "🧪 Highball Test",
            "This is a test notification from the Highball backup system.",
            "info"
        )
        
        if success:
            print("✅ Telegram notification sent successfully!")
            return True
        else:
            print("❌ Telegram notification failed to send")
            return False
            
    except Exception as e:
        print(f"❌ Telegram notification error: {str(e)}")
        return False


def test_email_notification(notifier):
    """Test email notification if configured"""
    print("\n📧 Testing Email Notifications")
    print("=" * 50)
    
    if not notifier.is_email_enabled():
        print("❌ Email not configured - skipping test")
        print("Configure email settings in your config notification.email section")
        return False
    
    try:
        success = notifier._send_email(
            "🧪 Highball Test",
            "This is a test notification from the Highball backup system.",
            "info"
        )
        
        if success:
            print("✅ Email notification sent successfully!")
            return True
        else:
            print("❌ Email notification failed to send")
            return False
            
    except Exception as e:
        print(f"❌ Email notification error: {str(e)}")
        return False


def test_delay_notification(notifier):
    """Test job delay notification"""
    print("\n🕐 Testing Job Delay Notification")
    print("=" * 50)
    
    if not notifier.is_notifications_enabled():
        print("❌ No notification providers configured - skipping test")
        return False
    
    try:
        notifier.send_job_delay_notification(
            job_name="test_job",
            delay_minutes=7.5,
            conflicting_jobs=["backup_job_1", "backup_job_2"], 
            source="scheduler"
        )
        
        print("✅ Job delay notification sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Job delay notification error: {str(e)}")
        return False


def test_success_notification(notifier):
    """Test job success notification"""
    print("\n✅ Testing Job Success Notification")
    print("=" * 50)
    
    if not notifier.is_notifications_enabled():
        print("❌ No notification providers configured - skipping test")
        return False
    
    try:
        # First test with notify_on_success disabled (should not send)
        notifier.send_job_success_notification(
            job_name="test_job",
            duration_seconds=125.5,
            dry_run=True
        )
        
        print("ℹ️  Success notification test completed (may not have sent - check notify_on_success setting)")
        return True
        
    except Exception as e:
        print(f"❌ Job success notification error: {str(e)}")
        return False


def test_failure_notification(notifier):
    """Test job failure notification"""
    print("\n❌ Testing Job Failure Notification") 
    print("=" * 50)
    
    if not notifier.is_notifications_enabled():
        print("❌ No notification providers configured - skipping test")
        return False
    
    try:
        notifier.send_job_failure_notification(
            job_name="test_job",
            error_message="Connection timeout to backup server",
            dry_run=False
        )
        
        print("✅ Job failure notification sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Job failure notification error: {str(e)}")
        return False


def main():
    """Run all notification tests"""
    print("🚀 Highball Notification System Test")
    print("=" * 60)
    
    try:
        # Test configuration
        notifier = test_notification_config()
        
        # Test individual providers
        telegram_success = test_telegram_notification(notifier)
        email_success = test_email_notification(notifier)
        
        # Test notification types if any provider is working
        if notifier.is_notifications_enabled():
            delay_success = test_delay_notification(notifier)
            success_success = test_success_notification(notifier)
            failure_success = test_failure_notification(notifier)
        else:
            print("\n⚠️  No notification providers configured - skipping notification type tests")
            delay_success = success_success = failure_success = False
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        if notifier.is_telegram_enabled():
            total_tests += 1
            if telegram_success:
                passed_tests += 1
            print(f"{'✅' if telegram_success else '❌'} Telegram notifications")
        
        if notifier.is_email_enabled():
            total_tests += 1
            if email_success:
                passed_tests += 1
            print(f"{'✅' if email_success else '❌'} Email notifications")
        
        if notifier.is_notifications_enabled():
            for test_name, success in [
                ("Delay notifications", delay_success),
                ("Success notifications", success_success), 
                ("Failure notifications", failure_success)
            ]:
                total_tests += 1
                if success:
                    passed_tests += 1
                print(f"{'✅' if success else '❌'} {test_name}")
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests and total_tests > 0:
            print("\n🎉 All notification tests passed!")
            print("Your notification system is working correctly.")
        elif total_tests == 0:
            print("\n🔧 No notification providers configured.")
            print("Configure Telegram or email settings to enable notifications.")
        else:
            print("\n⚠️  Some notification tests failed.")
            print("Check your configuration and network connectivity.")
        
        return passed_tests == total_tests and total_tests > 0
        
    except Exception as e:
        print(f"\n❌ Test suite error: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)