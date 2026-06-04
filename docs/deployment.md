# Deployment Guide

## Backend

1. Copy the repository to the server, for example `/opt/edge-platform`.
2. Run `scripts/deploy/install_backend.ps1` to create the Python environment, install `backend/requirements.txt`, and generate a `systemd` service for `uvicorn`.
3. Configure runtime secrets with environment variables before starting the service:

```bash
export JWT_SECRET_KEY='replace-with-a-long-random-secret'
export CREDENTIAL_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export DEFAULT_ADMIN_PASSWORD='replace-admin-password'
export SSH_HOST_KEY_POLICY='auto_add'
# export SSH_KNOWN_HOSTS_FILE='/etc/edge-platform/known_hosts'
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
- Check `migration.has_pending_migrations=false` in `GET /api/diagnostics/config` after every deploy. The backend runs Alembic `upgrade head` on startup, but a persistent error here means the service should not be used for production-like testing.
- `SSH_HOST_KEY_POLICY` defaults to `auto_add` for compatibility. For stricter environments, set it to `warning` or `reject` and configure `SSH_KNOWN_HOSTS_FILE` with the backend service user's readable known_hosts file.

## Wave 14 远程连接部署检查

远程连接页现在会直接连接 `/api/ws/devices/{id}/ssh` 和 `/api/ws/devices/{id}/vnc`。如果使用单域名 Nginx 反向代理,确认 `/api/ws/` location 包含:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

SSH/VNC 验收顺序:

1. 在平台中确认设备 `ssh_port`、`vnc_port` 非空,且 `ssh_credential_configured=true`。
2. 在后端服务器上确认 frps 主机和端口可达,例如 `nc -vz <frps-ip> <ssh_port>` 和 `nc -vz <frps-ip> <vnc_port>`。
3. 确认后端环境变量 `REMOTE_GATEWAY_HOST`、`VNC_GATEWAY_HOST` 指向 frps 对外可达地址。
4. 浏览器登录后进入"远程连接",选择设备,先测试 SSH,再测试 VNC。
5. 如果 REST 请求返回 502,优先查 Nginx `/api` 到后端的反向代理;如果 REST 成功但画面连接失败,查 `/api/ws` WebSocket 升级、frps 端口、防火墙和设备端 frpc。

## Wave 12 部署后检查

- 登录前端后进入"系统诊断",确认 `security.warnings` 中没有默认 JWT 密钥、默认管理员密码、默认设备 SSH 密码或未配置凭据加密密钥等风险项。
- 进入"操作日志",按 `action`、`target_type`、`status` 做一次筛选,并导出 `operation_logs.csv`,确认 Nginx 对 `/api/logs/export` 没有拦截下载响应头。
- 在"设备管理"中选择一台已导入 frps 的设备,点击"同步配置",确认 `POST /api/devices/{id}/sync-config` 能返回 frpc 配置文本。
- 如需修改管理员密码,使用前端顶栏"修改密码"。修改后会退出登录,下一次 Postman 或浏览器测试需要使用新密码重新登录获取 Token。

## Wave 13 监控指标验证

部署后可以用 Postman 或 `curl` 写入一条示例指标,确认前端仪表盘和系统诊断页已接收到真实监控数据。

1. 登录获取 Token。
2. 确认已有设备并记录 `device_id`。
3. 上报示例指标:

```bash
curl -X POST "$BASE_URL/api/devices/$DEVICE_ID/metrics" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"online","cpu_percent":64,"memory_percent":72,"disk_percent":81}'
```

4. 查询最新指标:

```bash
curl "$BASE_URL/api/devices/$DEVICE_ID/metrics?limit=1" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

5. 刷新前端仪表盘,确认"资源快照"显示 CPU、内存、磁盘真实值;进入"系统诊断",确认"监控可用性"显示有指标设备数和最近指标时间。

如果指标接口返回 502,优先检查 Nginx `/api` 反向代理、后端服务进程和后端日志。指标接口单台失败不会导致前端退出登录。

## Wave 15 文件与定时任务部署检查

- 若需要访问真实设备文件,后端必须配置 `FILE_BACKEND=sftp`,并保证设备记录已有 `ssh_port` 和可用 SSH 凭据;否则文件接口会使用本地存储后端,只适合开发测试。
- 文件上传使用 `multipart/form-data`,Nginx 默认允许 1 MB 请求体。若需要上传更大的文件,在 `server` 或 `location /api/` 中增加 `client_max_body_size`,例如 `client_max_body_size 100m;`。
- 文件下载走 `/api/devices/{id}/files/download`,请确认 Nginx 没有拦截 `Content-Disposition` 响应头,浏览器应直接下载文件。
- 定时任务前端页面仍可用于创建、编辑、启停和手动执行任务;Wave 18 之后后台调度器也会自动扫描到期任务并生成执行记录。
- Web SSH 主动断开会发送 `{ "type": "close" }`,后端关闭 shell 后返回 `status=closed`;如果浏览器显示已断开但后端仍有长连接,优先检查 `/api/ws/` 的 WebSocket 升级和超时配置。

## Wave 16 批量任务部署检查

- 在前端"批量更新"页新建任务前,先点击"预览目标",确认 `POST /api/update-tasks/preview-targets` 能返回命中设备数量,且真实 SSH 模式下没有缺少端口或凭据的 warning。
- 若预览接口或模板接口返回 502,先用 `curl -i http://127.0.0.1:8000/api/update-tasks/preview-targets` 验证后端是否可达;若后端可达但 Nginx 失败,检查 `/api/` 的 `proxy_pass`。
- 执行任务时前端会连接 `/api/ws/update-tasks/{id}?token=<access_token>` 读取快照。若任务可执行但前端进度不刷新,优先检查 Nginx `/api/ws/` WebSocket 升级头和超时配置。
- 结果导出走 `GET /api/update-tasks/{id}/export`,返回 `text/csv` 和 `Content-Disposition`。如果浏览器没有下载文件,检查 Nginx 是否拦截下载响应头。
- 命令模板表 `update_task_templates` 会由后端启动时自动创建。若旧 SQLite 数据库升级后模板接口报表不存在,重启后端服务并确认 `Base.metadata.create_all` 已执行。

## Wave 17 治理与认证刷新检查

- 重启后端后先访问 `GET /api/diagnostics/config`,确认 `migration.current_revision` 等于 `migration.head_revision`,且 `migration.has_pending_migrations=false`。
- 如果要从 `auto_add` 切到更严格的 SSH 主机密钥策略,先在后端服务器准备 known_hosts 文件,再设置:

```bash
export SSH_HOST_KEY_POLICY='warning'
export SSH_KNOWN_HOSTS_FILE='/etc/edge-platform/known_hosts'
```

- 前端登录态过期时会自动调用 refresh 接口重试一次。若 refresh token 也过期或后端返回 `401`,页面会直接回到登录页;部署验收时可通过缩短 token 有效期或清空 `edge-platform-refresh-token` 验证。
- 若某个接口因为枚举值返回 `422`,检查请求中的 `status`、`ssh_auth_type`、`execution_mode`、`failure_strategy` 或 `task_type` 是否在接口文档列出的允许值内。

## Wave 18 定时任务调度检查

- 后端默认启用调度器。需要暂停自动调度时设置 `SCHEDULER_ENABLED=false`;需要调整扫描间隔时设置 `SCHEDULER_POLL_INTERVAL_SECONDS`,默认值为 `30` 秒。
- 升级旧 SQLite 库后先检查 `GET /api/diagnostics/config` 的 `migration` 摘要,再访问 `GET /api/scheduler/status`,确认调度器 `enabled`、`running` 和最近扫描状态符合预期。
- 表达式只支持 `interval:N` 和 5 位 `cron:`。如果创建或更新任务返回 `422`,先检查表达式格式,再检查 `execution_mode`、`failure_strategy` 和 `concurrency_limit`。
- `dry_run` 定时任务只生成演练链路;真实设备自动执行必须显式选择 `execution_mode=ssh_command`,并提前确认目标设备已有可用 SSH 端口、设备级凭据和 frp 连通性。
- 部署验收建议先在前端创建一个短周期 `dry_run` 任务,确认页面出现 `next_run_at` 和执行记录;再按需创建真实 SSH 任务,并复核 `GET /api/scheduled-tasks/{id}/runs` 中的输出摘要、失败原因和关联批量任务 ID。
- Nginx 无需为调度器增加独立转发规则。调度状态、执行记录和立即执行仍走 `/api/`,前端按现有单域名反向代理访问。

## Wave 19 告警中心部署检查

- 升级后端后先检查 Alembic 是否已创建 `alerts` 和 `alert_rules` 表。`GET /api/diagnostics/config` 中 `migration.has_pending_migrations` 应为 `false`。
- 登录前端后进入"告警中心",确认告警摘要、告警列表和告警规则能正常加载;若页面空白,先用 `GET /api/alerts/summary` 和 `GET /api/alert-rules` 验证后端接口。
- 规则表会在后端启动时自动初始化。默认阈值为 CPU/内存 85%、磁盘 90%、指标冻结 10 分钟;前端可直接启停规则或编辑阈值。
- 部署验收建议先用 Postman 或 `curl` 上报一条超过阈值的设备指标,确认告警出现;再上报低于阈值的指标,确认同一告警自动恢复。
- 若调度器停用,指标冻结告警不会按后台扫描自动触发。需要验证冻结告警时保持 `SCHEDULER_ENABLED=true`,并等待一次调度扫描。
- Nginx 不需要新增 location。告警 REST API 均走既有 `/api/` 反向代理,没有独立 WebSocket。

## Wave 20 告警外部通知部署检查

- 升级后端后先确认 Alembic 已创建 `alert_notification_channels`、`alert_notification_policies` 和 `alert_notification_deliveries` 三张表,并确认 `GET /api/diagnostics/config` 中 `migration.has_pending_migrations=false`。
- 创建或更新 Webhook 通道前必须配置 `CREDENTIAL_ENCRYPTION_KEY`。该密钥用于加密 Webhook URL 和请求头;丢失后已保存的通知敏感配置无法解密,需要重新配置通道。
- Nginx 不需要新增 location。Webhook 配置、策略、投递记录和重试接口均走现有 `/api/` 反向代理。
- 后端发起 Webhook 出站请求时,服务器必须能访问目标通知地址。若投递失败,先在后端服务器上用 `curl -i <webhook-url>` 验证网络、DNS、防火墙和目标服务状态。
- 推荐先在前端"告警中心 -> 外部通知"创建一个测试 Webhook 通道,点击"测试",确认目标服务收到测试 payload,再创建通知策略。
- 生产-like 测试建议先使用默认策略:最低级别 `critical`,事件只选"触发"。确认无噪声后再按需开放确认、手动恢复或自动恢复通知。
- 删除 Webhook 通道前需要先删除引用该通道的通知策略。若直接删除通道返回 `409`,属于预期保护。
- 系统诊断页会展示启用通道、启用策略、失败投递和待重试投递计数。存在失败投递时,优先进入告警中心查看最近投递错误原因并手动重试。

## Wave 21 用户角色与会话审计部署检查

- 升级后端后先确认 Alembic 已执行到 Wave 21 用户角色迁移。`GET /api/diagnostics/config` 中 `migration.has_pending_migrations` 应为 `false`,并且 `users.admin_count` 至少为 `1`。
- 旧 SQLite 数据库中的默认 `admin` 用户会被迁移为 `role=admin`;后续新建用户默认角色为 `operator`。
- 首次部署后使用管理员账号登录,进入"用户管理"创建一个运维测试账号。运维账号登录后不应看到"用户管理"入口。
- 角色权限验收建议:
  - 运维账号可以进入设备管理并创建/编辑设备。
  - 运维账号执行 `dry_run` 批量任务应成功。
  - 运维账号执行 `ssh_command` 批量任务、删除设备、编辑告警通知配置应返回 `403`。
  - 管理员账号可执行上述高风险操作。
- 删除用户在当前实现中等价于停用账号,不会硬删除历史记录。后端会阻止停用或降级最后一个启用管理员。
- 前端收到 `401` 才会回登录页;收到 `403` 会留在当前页面并提示无权限。如果浏览器出现无权限提示,优先确认账号角色,不要先排查 token 过期。
- 操作日志中应能看到 `auth.login`、`auth.refresh`、`auth.password_change`、`auth.forbidden` 和 `user.*` 动作;日志不会记录明文密码、Token 或设备凭据。
