# Deployment Guide

## Backend

1. Copy the repository to the server, for example `/opt/edge-platform`.
2. Run `scripts/deploy/install_backend.ps1` to create the Python environment, install `backend/requirements.txt`, and generate a `systemd` service for `uvicorn`.
3. Configure runtime secrets with environment variables before starting the service:

```bash
export JWT_SECRET_KEY='replace-with-a-long-random-secret'
export CREDENTIAL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export DEFAULT_ADMIN_PASSWORD='replace-admin-password'
```

4. Place the generated service at `/etc/systemd/system/edge-platform.service`, then run:

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

### Single-domain Nginx example

Use one domain for the frontend, REST API, and WebSocket API:

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    root /home/Remote-Terminal-Platform/frontend/dist;
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
        proxy_read_timeout 3600s;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 502 checklist

Run these checks on the server in order:

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1/api/health
ss -lntp | grep -E ':80|:8000'
sudo nginx -t
sudo journalctl -u edge-platform -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

If `127.0.0.1:8000/api/health` fails, fix the backend process first. If it passes but Nginx `/api/health` returns 502, check `proxy_pass`, backend port, and Nginx error logs.

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
- Keep JWT and credential encryption secrets outside source control. If `CREDENTIAL_ENCRYPTION_KEY` is lost, encrypted device SSH passwords cannot be decrypted.
- Verify `frps`, SSH, and VNC ports before opening remote sessions.
- For real batch SSH tasks, verify imported devices have reachable SSH proxy ports and configured device credentials before switching update tasks from `dry_run` to `ssh_command`.
- Start with a harmless command such as `hostname` or `whoami`, then inspect each task device result for `exit_code`, `stdout_summary`, `stderr_summary`, and `error_message`.
- If the backend runs behind Nginx, keep long-running API calls and WebSocket locations on the same single-domain reverse proxy, and raise `proxy_read_timeout` when commands may take longer than the default timeout.
- Check `GET /api/diagnostics/config` after deployment. Any `security.warnings` should be resolved before testing real SSH tasks against production-like devices.

## Wave 12 部署后检查

- 登录前端后进入“系统诊断”，确认 `security.warnings` 中没有默认 JWT 密钥、默认管理员密码、默认设备 SSH 密码或未配置凭据加密密钥等风险项。
- 进入“操作日志”，按 `action`、`target_type`、`status` 做一次筛选，并导出 `operation_logs.csv`，确认 Nginx 对 `/api/logs/export` 没有拦截下载响应头。
- 在“设备管理”中选择一台已导入 frps 的设备，点击“同步配置”，确认 `POST /api/devices/{id}/sync-config` 能返回 frpc 配置文本。
- 如需修改管理员密码，使用前端顶栏“修改密码”。修改后会退出登录，下一次 Postman 或浏览器测试需要使用新密码重新登录获取 Token。
