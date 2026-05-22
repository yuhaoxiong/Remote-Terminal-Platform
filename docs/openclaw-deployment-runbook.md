# OpenClaw Deployment Runbook

## 1. Deployment Target

Deploy the current remote terminal platform to one Linux server with:

- FastAPI backend managed by `systemd`
- Vue frontend built into static files and served by Nginx
- Nginx reverse proxy for REST API and WebSocket API
- SQLite database stored with the backend runtime data
- `frps` reachable from the backend for device SSH/VNC tunnels

The repository does not currently provide a Dockerfile or Compose stack. Use the
`systemd + Nginx` path below unless the operator explicitly requests a container
deployment design.

## 2. Project Interpretation

This project is a Web remote management platform for Debian edge devices.

Runtime topology:

1. The browser loads the Vue frontend from Nginx.
2. Frontend REST calls use the same-domain `/api` prefix.
3. Frontend SSH/VNC/update-task progress sessions use same-domain `/api/ws/...`
   WebSocket endpoints.
4. Nginx proxies `/api/` and `/api/ws/` to FastAPI on `127.0.0.1:8000`.
5. FastAPI persists platform state in SQLite and opens SSH/SFTP/VNC traffic
   through frp-exposed device ports.
6. APScheduler runs inside the backend process for scheduled tasks.

Default code behavior to keep in mind:

- Backend API prefix is `/api`.
- Backend binds to SQLite at `backend/data/platform.db` when the service working
  directory is `backend/`.
- Startup runs Alembic migration to head, then keeps `create_all` and SQLite
  compatibility guards.
- Default admin credentials and default secrets are development defaults and
  must be replaced before production-like use.
- Device file access defaults to a local mock backend; real device file access
  requires `FILE_BACKEND=sftp`.

## 3. Inputs OpenClaw Must Collect

Do not begin the server mutation steps until these values are known:

| Variable | Meaning | Example |
| --- | --- | --- |
| `REPO_URL` | Git repository URL or source package path | `<repo-url>` |
| `DEPLOY_REF` | Branch, tag, or commit to deploy | `main` |
| `APP_ROOT` | Server checkout path | `/opt/edge-platform` |
| `APP_USER` | Linux service user | `edge-platform` |
| `DOMAIN` | Public frontend/API domain | `edge.example.com` |
| `FRPS_HOST` | Host reachable from backend for frps device ports | `127.0.0.1` |
| `NGINX_SITE` | Nginx site file path | `/etc/nginx/sites-available/edge-platform` |
| `BACKUP_ROOT` | SQLite backup path outside repo | `/var/backups/edge-platform` |

OpenClaw must generate or receive these secret values:

- `JWT_SECRET_KEY`: long random secret, not committed to Git.
- `DEFAULT_ADMIN_PASSWORD`: initial non-default admin password.
- `CREDENTIAL_ENCRYPTION_KEY`: one Fernet key. Preserve it across redeploys.
- Optional stricter SSH host key settings:
  - `SSH_HOST_KEY_POLICY=warning` or `reject`
  - `SSH_KNOWN_HOSTS_FILE=/etc/edge-platform/known_hosts`

## 4. Server Prerequisites

Target server assumptions:

- Linux server with `systemd`
- Nginx installed
- Git installed
- Python 3.12 available as `python3.12`
- Node.js and npm available to build the Vite frontend
- `curl` available for health checks
- Firewall and security group rules reviewed before public exposure

Required network shape:

- Public inbound: `80/tcp` and `443/tcp` after TLS is configured.
- Backend `8000/tcp`: loopback only, do not expose publicly.
- frps control/dashboard/device tunnel ports: expose only what the chosen frps
  topology needs.
- Browser access to API and WebSocket traffic must stay on the same domain.

## 5. Safe Deployment Sequence

### 5.1 Prepare Service User and Directories

Run as a privileged operator:

```bash
sudo useradd --system --create-home --home-dir /opt/edge-platform --shell /usr/sbin/nologin edge-platform || true
sudo mkdir -p /opt/edge-platform
sudo mkdir -p /etc/edge-platform
sudo mkdir -p /var/backups/edge-platform
sudo chown -R edge-platform:edge-platform /opt/edge-platform
sudo chmod 750 /etc/edge-platform
```

If `APP_ROOT`, `APP_USER`, or `BACKUP_ROOT` differ from the examples, substitute
them consistently in every later command.

### 5.2 Fetch Source

Use one of these paths.

Fresh clone:

```bash
sudo -u edge-platform git clone "$REPO_URL" /opt/edge-platform
cd /opt/edge-platform
sudo -u edge-platform git checkout "$DEPLOY_REF"
```

Existing checkout:

```bash
cd /opt/edge-platform
sudo -u edge-platform git fetch --all --tags
sudo -u edge-platform git checkout "$DEPLOY_REF"
```

Record the deployed revision:

```bash
git rev-parse HEAD
```

### 5.3 Install Backend Runtime

The repository has `scripts/deploy/install_backend.ps1`, but the production
Linux path should use explicit Linux commands below. The current script mixes a
PowerShell virtualenv executable path with a Linux `systemd` service template.

```bash
cd /opt/edge-platform
sudo -u edge-platform python3.12 -m venv .venv
sudo -u edge-platform /opt/edge-platform/.venv/bin/python -m pip install --upgrade pip
sudo -u edge-platform /opt/edge-platform/.venv/bin/python -m pip install -r backend/requirements.txt
```

### 5.4 Create Runtime Environment File

Generate secrets first:

```bash
python3.12 -c 'import secrets; print(secrets.token_urlsafe(64))'
/opt/edge-platform/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Create `/etc/edge-platform/edge-platform.env`:

```dotenv
JWT_SECRET_KEY=<generated-long-secret>
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<non-default-initial-password>
CREDENTIAL_ENCRYPTION_KEY=<generated-fernet-key>

REMOTE_GATEWAY_HOST=<frps-host-reachable-from-backend>
VNC_GATEWAY_HOST=<frps-host-reachable-from-backend>
FILE_BACKEND=sftp

SCHEDULER_ENABLED=true
SCHEDULER_POLL_INTERVAL_SECONDS=30

DEFAULT_DEVICE_SSH_USER=<deployment-default-device-user>
DEFAULT_DEVICE_SSH_PASSWORD=<deployment-default-device-password-if-needed>

# Compatibility-first default. Tighten after known_hosts is ready.
SSH_HOST_KEY_POLICY=auto_add
# SSH_KNOWN_HOSTS_FILE=/etc/edge-platform/known_hosts
```

Protect the file:

```bash
sudo chown root:edge-platform /etc/edge-platform/edge-platform.env
sudo chmod 640 /etc/edge-platform/edge-platform.env
```

Notes:

- Do not rotate `CREDENTIAL_ENCRYPTION_KEY` without a migration plan for stored
  device credentials.
- If real device SFTP is not ready yet, set `FILE_BACKEND=local` for a smoke
  deploy and switch to `sftp` only after tunnel and credential validation.
- `DEFAULT_DEVICE_SSH_PASSWORD` is only a default for device records. Prefer
  per-device credentials and remove default-password reliance after onboarding.

### 5.5 Create systemd Service

Create `/etc/systemd/system/edge-platform.service`:

```ini
[Unit]
Description=AI Edge Platform FastAPI backend
After=network.target

[Service]
User=edge-platform
Group=edge-platform
WorkingDirectory=/opt/edge-platform/backend
Environment=PYTHONPATH=/opt/edge-platform/backend
EnvironmentFile=/etc/edge-platform/edge-platform.env
ExecStart=/opt/edge-platform/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable edge-platform
sudo systemctl restart edge-platform
sudo systemctl status edge-platform --no-pager
```

### 5.6 Build Frontend

```bash
cd /opt/edge-platform/frontend
sudo -u edge-platform npm install
sudo -u edge-platform npm run build
```

Expected build output:

```text
/opt/edge-platform/frontend/dist
```

The frontend already uses `baseURL: "/api"` and builds WebSocket URLs from the
current browser host. Do not split the frontend, REST API, and WebSocket API
across unrelated public origins unless the code and proxy strategy are changed.

### 5.7 Configure Nginx

Create the site file selected by `NGINX_SITE`:

```nginx
server {
    listen 80;
    server_name edge.example.com;

    root /opt/edge-platform/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 100m;
    }
}
```

Enable and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/edge-platform /etc/nginx/sites-enabled/edge-platform
sudo nginx -t
sudo systemctl reload nginx
```

Add TLS with the operator's approved certificate process after the HTTP health
check is clean. Keep the `/api/ws/` WebSocket upgrade headers after the TLS
change.

## 6. First Health Check and Acceptance

### 6.1 Backend and Proxy Health

Run in order:

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1/api/health
curl -i http://edge.example.com/api/health
sudo journalctl -u edge-platform -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

Accept only when:

- Backend health returns HTTP `200`.
- Health response shows `database: "ok"`.
- Nginx same-domain proxy health returns HTTP `200`.
- Backend logs do not show startup migration failures.

### 6.2 Login and Diagnostics

Use the frontend or API login with the configured initial admin password.

After login, open the diagnostics view or call:

```text
GET /api/diagnostics/config
```

Required diagnostics checks:

- `security.warnings` has no default JWT secret warning.
- `security.warnings` has no default admin password warning.
- `security.credential_encryption_configured` is `true` before storing real
  device credentials.
- `migration.has_pending_migrations` is `false`.
- Scheduler status matches the deployment choice.
- SSH host key warnings are understood before real SSH command execution.

### 6.3 Functional Smoke Checks

Run these after login:

1. Load device list and group list.
2. Create one test device or import one known frps-backed device.
3. Generate one device sync config and inspect the returned frpc text.
4. Run an update task first in `dry_run` mode with a harmless command such as
   `hostname`.
5. Only after tunnel and credentials are verified, test one real
   `ssh_command` target.
6. If SFTP mode is enabled, list a safe test directory on a test device.
7. Open SSH first, then VNC, and verify `/api/ws/` proxying is healthy.

## 7. frps and Edge Device Requirements

### 7.1 frps Side

The backend must reach the frps-exposed device SSH/VNC ports using
`REMOTE_GATEWAY_HOST` and `VNC_GATEWAY_HOST`.

Default platform-created device port pools are:

- SSH: `10000-10499`
- VNC: `10500-10999`

If importing pre-existing frps tunnels through the dashboard discovery flow,
use discovery ranges that match the actual frps ports already in use.

### 7.2 Edge Device Side

Each real Debian edge device needs:

- OpenSSH server running
- VNC server available for VNC use
- frpc installed and configured to reach frps
- SSH credentials recorded per device in the platform

Repository helper:

```text
scripts/deploy/edge_bootstrap.sh
```

That script is only a minimal bootstrap starting point. It writes a basic SSH
registration tunnel with remote port `10000`; it does not complete final
per-device SSH/VNC config management by itself. After the device exists in the
platform, use the generated sync config from the platform and deploy the final
frpc config on the device.

## 8. SQLite Backup and Upgrade Discipline

The default database path for this deployment layout is:

```text
/opt/edge-platform/backend/data/platform.db
```

Before every upgrade:

```bash
sudo mkdir -p /var/backups/edge-platform
sudo cp /opt/edge-platform/backend/data/platform.db /var/backups/edge-platform/platform-$(date +%Y%m%d-%H%M%S).db
```

After every upgrade:

1. Restart backend.
2. Check `/api/health`.
3. Check diagnostics migration summary.
4. Check one authenticated frontend route.
5. Keep the backup outside the deploy checkout.

The repository also includes `scripts/deploy/backup_sqlite.ps1` for PowerShell
operators. On Linux, the explicit `cp` command above is the simplest approved
baseline.

## 9. Upgrade Procedure

For a normal in-place upgrade:

```bash
cd /opt/edge-platform
sudo cp backend/data/platform.db /var/backups/edge-platform/platform-$(date +%Y%m%d-%H%M%S).db
sudo -u edge-platform git fetch --all --tags
sudo -u edge-platform git checkout "$DEPLOY_REF"
sudo -u edge-platform /opt/edge-platform/.venv/bin/python -m pip install -r backend/requirements.txt
cd /opt/edge-platform/frontend
sudo -u edge-platform npm install
sudo -u edge-platform npm run build
sudo systemctl restart edge-platform
sudo nginx -t
sudo systemctl reload nginx
```

Then rerun the health and diagnostics checks.

## 10. Rollback Rule

Rollback when one of these is true:

- Backend cannot start cleanly after dependency and configuration checks.
- `/api/health` cannot reach `database: "ok"`.
- Diagnostics show migration errors after restart.
- Same-domain `/api/ws/` traffic is broken for required remote access tests.

Minimum rollback steps:

1. Stop backend.
2. Restore the previous Git ref or source package.
3. Restore the pre-upgrade SQLite backup if the failed release changed schema
   or data incompatibly.
4. Reinstall backend dependencies if the previous ref requires it.
5. Rebuild frontend for the previous ref.
6. Start backend and re-run health plus diagnostics.

## 11. Troubleshooting Order

For `502`:

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1/api/health
sudo ss -lntp | grep -E ':80|:8000'
sudo nginx -t
sudo journalctl -u edge-platform -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

For SSH/VNC failure:

1. Confirm the platform device record has SSH/VNC ports.
2. Confirm device SSH credentials are configured.
3. Confirm backend can reach the frps-exposed port.
4. Confirm `REMOTE_GATEWAY_HOST` and `VNC_GATEWAY_HOST`.
5. Confirm `/api/ws/` WebSocket headers and timeout settings.
6. Confirm frpc is connected on the edge device.

For SFTP failure:

1. Confirm `FILE_BACKEND=sftp`.
2. Confirm SSH tunnel reachability and credentials.
3. Confirm the target path is safe and exists on the device.

## 12. OpenClaw Execution Contract

OpenClaw should:

1. Echo the resolved deployment variables before mutating the server.
2. Refuse to commit secrets to the repository.
3. Back up SQLite before upgrades.
4. Keep backend on loopback and expose the app through Nginx.
5. Preserve `/api/ws/` WebSocket proxy handling.
6. Report the deployed Git revision, service status, health results,
   diagnostics summary, and any unresolved warnings.

OpenClaw should stop and ask for operator input when:

- The target server does not have Python 3.12.
- frps host, public domain, or admin secret values are missing.
- Existing Nginx routes conflict with the same-domain `/api` or `/api/ws` plan.
- A migration or backup step fails.
