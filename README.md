# ![Highball logo](favicon.ico "Highball logo") Highball

Multi-host backup orchestrator for rsync, rclone, restic, and more — all from one dashboard.

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](#quick-start-with-docker)
[![Status](https://img.shields.io/badge/Status-Alpha-orange)](#roadmap)

Highball is a lightweight, self-hosted backup frontend for managing backup jobs across multiple hosts.
- Connect over SSH or rsync daemons, validate endpoints, and schedule jobs from a single web interface.
- Start with rsync-based workflows, then grow into rclone and restic as you need them.

> One place to define, validate, and run backup policies for media libraries and stack persistent storage.

---

## Features

- Multi-host job management over SSH
- Rsync jobs to any reachable host or rsync daemon
- Endpoint validation and preflight checks
- Simple, clear UI (templates and handlers in this repo)
- Log viewing for recent job runs
- Docker Compose deployment

### Planned
- Rclone and Restic job types
- Per-job dry-run and diff previews
- Policy sets and schedules
- Health checks and notifications

---

## Requirements

- Python 3.11+ (if running without Docker, but why would you)
- rsync(d) on source and target hosts
- SSH key-based access for automated runs
- Docker 24+ and Docker Compose v2

## More stuff later

