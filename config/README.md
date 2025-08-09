# Backup Manager Configuration

This directory contains all user-configurable files for the backup manager.

## Files

### config.yaml
Main configuration file containing:
- Global settings (destination host, paths, notifications)
- Backup job definitions
- Backup logs (automatically updated)

You can edit this file directly or through the web interface.

### Custom Scripts (future)
You can add custom scripts here that will be available to backup jobs:
- pre-backup hooks
- post-backup scripts
- custom notification handlers

## Docker Volume Mount

For production deployments, mount this entire directory as a Docker volume:

```bash
docker run -d \
  -p 80:80 \
  -v /path/to/your/config:/config \
  backup-manager
```

This allows you to:
- Persist configuration across container updates
- Edit config files directly on the host
- Back up your backup configurations!

## Example Telegram Setup

1. Create a Telegram bot by messaging @BotFather
2. Get your chat ID by messaging @userinfobot
3. Update config.yaml with your token and chat ID
4. Test notifications through the web interface
