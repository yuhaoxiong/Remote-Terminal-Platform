# Deployment Guide

## Backend

1. Copy the repository to the server, for example `/opt/edge-platform`.
2. Run `scripts/deploy/install_backend.ps1` to create the Python environment, install `backend/requirements.txt`, and generate a `systemd` service for `uvicorn`.
3. Place the generated service at `/etc/systemd/system/edge-platform.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable edge-platform
sudo systemctl restart edge-platform
```

## Frontend and Nginx

Build the frontend with:

```bash
cd frontend
npm install
npm run build
```

Serve `frontend/dist` with Nginx and proxy `/api` plus `/api/ws` to the backend on `127.0.0.1:8000`.

## SQLite Backup

The production database is SQLite at `backend/data/platform.db` by default. Run:

```powershell
scripts/deploy/backup_sqlite.ps1 -DatabasePath backend/data/platform.db -BackupRoot backups
```

Schedule this command with cron, Windows Task Scheduler, or a systemd timer. Keep backup files outside the application deploy directory.

## Edge Device Bootstrap

On Debian 11 edge devices, run `scripts/deploy/edge_bootstrap.sh` to check `ssh`, check `vnc`, and create a minimal `frpc` registration tunnel. After the device is registered in the platform, use the generated frpc config from the device sync endpoint.

## Operational Notes

- Restrict file permissions for SQLite and uploaded file storage to the backend service user.
- Keep JWT and credential encryption secrets outside source control.
- Verify `frps`, SSH, and VNC ports before opening remote sessions.
