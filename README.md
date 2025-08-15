# ![Highball logo](favicon.ico "Highball logo") Highball

Web-based backup orchestrator that actually knows if your backups will work before they run.

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](#quick-start)
[![License](https://img.shields.io/badge/License-GPLv3-blue)](#license)

Highball orchestrates rsync and Restic backups across multiple hosts with conflict-aware scheduling, real-time validation, and unified browsing. If you've been cobbling together cron jobs and shell scripts hoping your backups work, this replaces all of that with one container.

## What Makes This Different

**Pre-flight Everything** – Every SSH connection, repository, and binary gets validated before jobs run. No more discovering auth failures at 3 AM.

**Conflict-Aware Scheduling** – Won't launch jobs that step on each other. Queues them automatically instead of silent failures.

**Provider-Agnostic UI** – Browse Restic snapshots and rsync directories with the same interface. No context switching between tools.

**Multi-Path Jobs** – Backup multiple related directories to the same destination with per-path include/exclude rules. One job, multiple sources.

**Container Execution** – Uses official `restic/restic` containers on remote hosts for version consistency. No binary management headaches.

**Smart Restore System** – Restore to source locations or safe container directories with intelligent overwrite protection and dry-run previews.

**Spam-Prevention Notifications** – Telegram and email alerts with queue batching so success notifications don't become a machine gun.

As far as we know, no other self-hosted backup frontend combines this level of multi-provider orchestration, validation, and conflict management in one place.

## Quick Start

Container-only. Don't open issues if you're not running containerized.

```yaml
# This will work at beta release.
#
# docker-compose.yml
services:
  highball:
    image: ghcr.io/ja2ui0/highball:latest
    container_name: highball
    ports:
      - "8087:8087"
    volumes:
      - ./config:/config
      - ./logs:/var/log/highball
      - ~/.ssh:/root/.ssh:ro  # for SSH key access
    restart: unless-stopped
```

```bash
docker compose up -d
```

Browse to http://localhost:8087 and start building jobs.

## Requirements

You bring:
- SSH key access to your hosts
- rsync on source/destination systems
- docker/podman on hosts for Restic jobs (auto-detected)

Highball handles the rest.

## Architecture

Pure orchestration layer – Highball SSH's to your hosts and runs binaries there. Never acts as a data intermediary. This enables any host → any destination with just coordination overhead.

**Sources**: SSH hosts, local filesystem  
**Destinations**: SSH hosts, local filesystem, rsync daemons, Restic repositories  
**Providers**: rsync (mature), Restic (complete), Kopia (planned)

## Development

```bash
git clone https://github.com/ja2ui0/highball.git
cd highball
./rr  # rebuild and restart
```

See `CLAUDE.md` for architecture details and development guidelines.

## License

GPLv3
