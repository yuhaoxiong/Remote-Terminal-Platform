# OpenClaw 部署运行手册

本文档用于指导 OpenClaw 将当前远程终端平台部署到一台 Linux 服务器，并配置“推送到 Git 后自动拉取、构建、重启服务”的自动部署流程。

## 1. 部署目标

在一台服务器上部署：

- FastAPI 后端，由 `systemd` 托管。
- Vue 3 前端，构建为静态文件后由 Nginx 托管。
- Nginx 统一提供前端、REST API 和 WebSocket 入口。
- SQLite 数据库和上传文件存放在代码目录之外。
- Git 推送到指定分支后，服务器自动执行部署脚本。

推荐拓扑：

```text
Browser
  |
  | http/https
  v
Nginx
  |-- /                 -> /opt/edge-platform/frontend/dist
  |-- /api/             -> http://127.0.0.1:8000
  |-- /api/ws/          -> http://127.0.0.1:8000 WebSocket
                              |
                              v
                        FastAPI + SQLite
```

当前仓库没有 Dockerfile 或 Compose 文件。除非明确要求容器化，否则 OpenClaw 应使用本文档的 `systemd + Nginx + Git 自动部署` 方案。

## 2. OpenClaw 执行前需确认的信息

OpenClaw 开始改服务器前，先向操作者确认或填充以下变量。

| 变量 | 含义 | 示例 |
| --- | --- | --- |
| `REPO_URL` | Git 仓库地址 | `git@github.com:org/repo.git` |
| `DEPLOY_BRANCH` | 自动部署分支 | `main` |
| `APP_ROOT` | 服务器代码目录 | `/opt/edge-platform` |
| `APP_USER` | 运行服务的 Linux 用户 | `edge-platform` |
| `DOMAIN` | 访问域名或服务器 IP | `edge.example.com` |
| `BACKEND_PORT` | 后端本地监听端口 | `8000` |
| `FRPS_HOST` | 后端可访问的 frps 地址 | `127.0.0.1` |
| `DATA_ROOT` | 数据目录 | `/var/lib/edge-platform` |
| `BACKUP_ROOT` | SQLite 备份目录 | `/var/backups/edge-platform` |

必须生成或由操作者提供的密钥：

- `JWT_SECRET_KEY`：JWT 签名密钥，必须是长随机字符串。
- `DEFAULT_ADMIN_PASSWORD`：首次管理员密码，不能使用默认值 `admin`。
- `CREDENTIAL_ENCRYPTION_KEY`：Fernet 密钥，用于加密设备 SSH 密码和 Webhook 敏感配置。该密钥丢失后，已加密的数据无法解密。

如果以下信息暂时未知，OpenClaw 可以先完成基础部署，但必须在最终报告中列为待补项：

- 正式域名和 TLS 证书方案。
- frps 真实地址和端口开放策略。
- 是否启用真实设备 SFTP 文件管理。
- 是否需要更严格的 SSH known_hosts 校验。

## 3. 项目部署依据

OpenClaw 应按以下已确认的项目行为部署：

- 后端入口：`backend/app/main.py`，ASGI 对象为 `app.main:app`。
- 后端依赖：`backend/requirements.txt`。
- 后端 API 前缀：`/api`。
- 健康检查：`GET /api/health`。
- 前端构建命令：在 `frontend/` 下执行 `npm ci` 和 `npm run build`。
- 前端静态产物：`frontend/dist`。
- 前端 REST 请求使用同域 `baseURL: "/api"`。
- 前端 WebSocket 使用当前浏览器域名拼接 `/api/ws/...`。
- 后端启动时会执行数据库初始化和 Alembic 迁移。
- 默认 SQLite 路径是相对后端工作目录的 `./data/platform.db`，生产部署应显式改到 `/var/lib/edge-platform/platform.db`。

## 4. 服务器前置条件

目标服务器建议为 Ubuntu/Debian，并具备：

```bash
sudo apt update
sudo apt install -y git nginx curl python3.12 python3.12-venv nodejs npm
```

如果系统没有 `python3.12`，OpenClaw 应停止并提示操作者选择：

- 安装 Python 3.12。
- 使用 pyenv 安装 Python 3.12。
- 明确授权改用服务器已有 Python 版本。

网络要求：

- `80/tcp` 和后续 `443/tcp` 对浏览器开放。
- `8000/tcp` 只监听 `127.0.0.1`，不要直接暴露公网。
- frps 相关端口按实际设备接入方案开放。
- `/api/ws/` 必须支持 WebSocket upgrade。

## 5. 首次部署步骤

### 5.1 创建用户和目录

```bash
sudo useradd --system --create-home --home-dir /opt/edge-platform --shell /usr/sbin/nologin edge-platform || true
sudo mkdir -p /opt/edge-platform
sudo mkdir -p /etc/edge-platform
sudo mkdir -p /var/lib/edge-platform/uploads
sudo mkdir -p /var/backups/edge-platform
sudo chown -R edge-platform:edge-platform /opt/edge-platform
sudo chown -R edge-platform:edge-platform /var/lib/edge-platform
sudo chmod 750 /etc/edge-platform
```

### 5.2 拉取代码

首次部署：

```bash
sudo -u edge-platform git clone "$REPO_URL" /opt/edge-platform
cd /opt/edge-platform
sudo -u edge-platform git checkout "$DEPLOY_BRANCH"
git rev-parse HEAD
```

如果目录已经存在：

```bash
cd /opt/edge-platform
sudo -u edge-platform git fetch --all --tags
sudo -u edge-platform git checkout "$DEPLOY_BRANCH"
sudo -u edge-platform git pull --ff-only origin "$DEPLOY_BRANCH"
git rev-parse HEAD
```

### 5.3 安装后端依赖

```bash
cd /opt/edge-platform
sudo -u edge-platform python3.12 -m venv .venv
sudo -u edge-platform /opt/edge-platform/.venv/bin/python -m pip install --upgrade pip
sudo -u edge-platform /opt/edge-platform/.venv/bin/python -m pip install -r backend/requirements.txt
```

### 5.4 创建环境变量文件

生成密钥：

```bash
python3.12 -c 'import secrets; print(secrets.token_urlsafe(64))'
/opt/edge-platform/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

创建 `/etc/edge-platform/edge-platform.env`：

```dotenv
PYTHONPATH=/opt/edge-platform/backend
DATABASE_URL=sqlite:////var/lib/edge-platform/platform.db
FILE_STORAGE_DIR=/var/lib/edge-platform/uploads

JWT_SECRET_KEY=<generated-long-secret>
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<non-default-admin-password>
CREDENTIAL_ENCRYPTION_KEY=<generated-fernet-key>

REMOTE_GATEWAY_HOST=<frps-host>
VNC_GATEWAY_HOST=<frps-host>

SCHEDULER_ENABLED=true
SCHEDULER_POLL_INTERVAL_SECONDS=30

# 生产环境访问实际设备文件必须使用 sftp；local 仅用于本地模拟测试。
FILE_BACKEND=sftp

# 兼容优先。更严格部署可改为 warning 或 reject，并配置 SSH_KNOWN_HOSTS_FILE。
SSH_HOST_KEY_POLICY=auto_add
# SSH_KNOWN_HOSTS_FILE=/etc/edge-platform/known_hosts

# 如需给导入设备设置默认 SSH 凭据，部署时再显式填写。
# DEFAULT_DEVICE_SSH_USER=<device-user>
# DEFAULT_DEVICE_SSH_PASSWORD=<device-password>
```

> 注意：系统设置的读取优先级是“数据库覆盖值 > 环境变量 > 代码默认值”。如果旧部署曾在“系统设置”中保存过 `FILE_BACKEND=local`，仅修改上述环境文件不会生效。更新部署后，请在“系统设置 → 文件与存储”中将文件后端改为 `sftp`，保存并重启服务；也可先恢复该项默认值，再由环境变量接管。

设置权限：

```bash
sudo chown root:edge-platform /etc/edge-platform/edge-platform.env
sudo chmod 640 /etc/edge-platform/edge-platform.env
```

### 5.5 创建 systemd 服务

创建 `/etc/systemd/system/edge-platform.service`：

```ini
[Unit]
Description=Remote Terminal Platform Backend
After=network.target

[Service]
User=edge-platform
Group=edge-platform
WorkingDirectory=/opt/edge-platform/backend
EnvironmentFile=/etc/edge-platform/edge-platform.env
ExecStart=/opt/edge-platform/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable edge-platform
sudo systemctl restart edge-platform
sudo systemctl status edge-platform --no-pager
```

### 5.6 构建前端

```bash
cd /opt/edge-platform/frontend
sudo -u edge-platform npm ci
sudo -u edge-platform npm run build
```

### 5.7 配置 Nginx

创建 `/etc/nginx/sites-available/edge-platform`：

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

把 `edge.example.com` 替换为 `DOMAIN`。如果暂时没有域名，可以先使用服务器公网 IP。

启用站点：

```bash
sudo ln -sf /etc/nginx/sites-available/edge-platform /etc/nginx/sites-enabled/edge-platform
sudo nginx -t
sudo systemctl reload nginx
```

TLS 证书可以在 HTTP 部署验证通过后再配置。配置 HTTPS 后，必须保留 `/api/ws/` 的 WebSocket upgrade 头。

## 6. 自动部署方案

推荐采用：

```text
Git push
  -> CI 测试、类型检查和构建全部通过
  -> 取得该次 main push 的确定 Git SHA
  -> SSH 登录服务器
  -> fast-forward 到该 Git SHA 并核对 revision
  -> 执行服务器现有 /opt/edge-platform/deploy.sh
```

### 6.1 使用服务器兼容部署脚本

当前生产环境回退使用已验证过的服务器脚本：

```text
/opt/edge-platform/deploy.sh
```

确认脚本存在且可执行：

```bash
sudo chmod +x /opt/edge-platform/deploy.sh
```

GitHub workflow 仍只在 CI 成功后运行，并在调用脚本前确认服务器 checkout 与 `workflow_run.head_sha` 一致。仓库内部署脚本因当前服务器 sudoers 不兼容而停用；重新启用前必须先在预发布环境验证备份、回滚和权限边界。

### 6.2 配置 sudo 免密范围

CI 登录服务器的用户建议为普通用户，例如 `deploy`。该用户只允许执行部署所需命令。

创建用户：

```bash
sudo useradd --create-home --shell /bin/bash deploy || true
```

配置 SSH 公钥：

```bash
sudo mkdir -p /home/deploy/.ssh
sudo nano /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

编辑 sudoers：

```bash
sudo visudo
```

先确认服务器上的实际命令路径：

```bash
command -v git
command -v python3.12
command -v npm
```

再加入 sudoers。下面假设系统 Python 位于 `/usr/local/bin/python3.12`；必须替换为上一条命令的实际输出：

```text
deploy ALL=(edge-platform) NOPASSWD: /usr/bin/git, /usr/local/bin/python3.12, /opt/edge-platform/.venv/bin/python, /usr/bin/npm
deploy ALL=(root) NOPASSWD: /usr/bin/chown -R edge-platform\:edge-platform /opt/edge-platform, /usr/bin/systemctl restart edge-platform, /usr/bin/systemctl reload nginx, /usr/sbin/nginx -t, /usr/bin/mkdir -p /var/backups/edge-platform, /usr/bin/cp /var/lib/edge-platform/platform.db /var/backups/edge-platform/*, /usr/bin/tee /var/backups/edge-platform/*
```

如果其他命令路径不同，用 `command -v systemctl nginx cp tee` 确认后替换。

### 6.3 GitHub Actions 示例

在仓库创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy

on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]

jobs:
  deploy:
    if: >-
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.event == 'push' &&
      github.event.workflow_run.head_branch == 'main'
    runs-on: ubuntu-latest
    env:
      TARGET_SHA: ${{ github.event.workflow_run.head_sha }}

    steps:
      - name: Deploy verified revision over SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          envs: TARGET_SHA
          script: <与仓库 .github/workflows/deploy.yml 保持一致>
```

实际 workflow 会 fast-forward `main`，核对 checkout 与 `$TARGET_SHA` 完全一致，再执行 `/opt/edge-platform/deploy.sh`。不要把触发器改回独立的 `push main` 部署，否则 CI 失败的提交仍可能进入生产。

GitHub Secrets：

```text
SERVER_HOST=<server-ip-or-domain>
SERVER_USER=deploy
SERVER_SSH_KEY=<private-key-for-deploy-user>
```

### 6.4 GitLab CI 示例

创建 `.gitlab-ci.yml`：

```yaml
stages:
  - deploy

deploy:
  stage: deploy
  image: alpine:3.20
  needs: [backend, frontend]
  only:
    - main
  before_script:
    - apk add --no-cache openssh-client
    - mkdir -p ~/.ssh
    - echo "$SERVER_SSH_KEY" > ~/.ssh/id_ed25519
    - chmod 600 ~/.ssh/id_ed25519
    - ssh-keyscan -H "$SERVER_HOST" >> ~/.ssh/known_hosts
  script:
    - ssh "$SERVER_USER@$SERVER_HOST" "cd /opt/edge-platform && ./deploy.sh"
```

`backend`、`frontend` 必须是已完成测试/检查的前置 job；不能只保留 deploy job。实际使用时还必须在调用 `./deploy.sh` 前加入与 GitHub workflow 相同的 fetch、fast-forward 和 `$CI_COMMIT_SHA` 一致性校验。

GitLab CI/CD Variables：

```text
SERVER_HOST=<server-ip-or-domain>
SERVER_USER=deploy
SERVER_SSH_KEY=<private-key-for-deploy-user>
```

### 6.5 Gitee 流水线思路

Gitee 流水线同样使用 SSH 方式：

```bash
ssh deploy@<server-host> "cd /opt/edge-platform && ./deploy.sh"
```

调用前同样必须完成目标 revision 的 fast-forward 与 SHA 一致性校验，不能仅依赖服务器脚本内部的 `git pull`。

需要在 Gitee 流水线变量中保存：

```text
SERVER_HOST
SERVER_USER
SERVER_SSH_KEY
```

OpenClaw 如果无法判断 Git 平台，应保留服务器现有 `/opt/edge-platform/deploy.sh`，并在交付报告中提示操作者选择 GitHub、GitLab 或 Gitee 的 CI 成功门控方式。

## 7. 部署验证

### 7.1 本机健康检查

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1/api/health
sudo ss -lntp | grep -E ':80|:8000'
sudo journalctl -u edge-platform -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

验收标准：

- `http://127.0.0.1:8000/api/health` 返回 `200`。
- 响应中 `database` 为 `ok`。
- `http://127.0.0.1/api/health` 返回 `200`。
- `8000` 只监听 `127.0.0.1`。
- Nginx error log 没有持续 502 或 WebSocket upgrade 错误。

### 7.2 前端和登录验证

浏览器访问：

```text
http://<DOMAIN>/
```

使用：

```text
用户名：admin
密码：DEFAULT_ADMIN_PASSWORD 中配置的密码
```

登录后检查：

- 仪表盘可以加载。
- 设备列表可以加载。
- 系统诊断可以加载。
- `security.warnings` 中没有默认 JWT 密钥、默认管理员密码、未配置凭据加密密钥等风险。
- `migration.has_pending_migrations=false`。

### 7.3 自动部署验证

在本地提交并推送一个非业务破坏性改动后，观察流水线和服务器：

```bash
sudo journalctl -u edge-platform -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/api/health
ls -lah /var/backups/edge-platform
```

验收标准：

- CI 成功通过。
- 服务器代码 revision 已更新。
- 前端重新构建成功。
- 后端重启成功。
- SQLite 备份目录生成新备份，或首次部署时明确跳过。
- `/api/health` 正常。

## 8. 远程设备接入检查

真实 SSH/VNC/SFTP 使用前，按顺序验证：

1. 设备端已安装并启动 OpenSSH。
2. 需要 VNC 时，设备端 VNC 服务可用。
3. 设备端 frpc 已连接 frps。
4. 平台设备记录中有 `ssh_port` 和需要时的 `vnc_port`。
5. 平台设备记录中已配置 SSH 凭据。
6. 后端服务器能访问 frps 暴露的设备端口。
7. Nginx `/api/ws/` WebSocket upgrade 正常。

测试端口：

```bash
nc -vz <frps-host> <ssh-port>
nc -vz <frps-host> <vnc-port>
```

建议先执行 `dry_run` 批量任务，再对单台测试设备执行真实 SSH 命令，例如：

```bash
hostname
whoami
```

## 9. 备份与回滚

### 9.1 手动备份

```bash
sudo mkdir -p /var/backups/edge-platform
sudo cp /var/lib/edge-platform/platform.db /var/backups/edge-platform/platform-$(date +%Y%m%d-%H%M%S).db
```

### 9.2 自动部署前备份

服务器 `/opt/edge-platform/deploy.sh` 应继续执行现有的部署前 SQLite 备份；回退期间由服务器运维配置负责保证该行为。

### 9.3 回滚条件

出现以下任一情况，应回滚：

- 后端无法启动。
- `/api/health` 失败。
- 数据库状态不是 `ok`。
- 诊断接口显示迁移异常。
- 前端核心页面无法加载。
- `/api/ws/` 影响远程 SSH/VNC 使用。

### 9.4 回滚步骤

代码与数据库 revision 兼容时，按服务器现有脚本的回滚流程处理；如果脚本没有回滚参数，先手动检出上一稳定 revision，再运行脚本：

```bash
cd /opt/edge-platform
sudo -u edge-platform git checkout <previous-good-commit-or-tag>
./deploy.sh
```

不得让旧代码直接连接不兼容的新 schema。需要数据库回滚时，先选择匹配备份，停服务后显式恢复数据库，再运行服务器部署脚本并检查健康状态：

```bash
sudo systemctl stop edge-platform
sudo cp /var/backups/edge-platform/<matching-backup.db> /var/lib/edge-platform/platform.db
sudo systemctl start edge-platform
curl -i http://127.0.0.1:8000/api/health
```

## 10. 常见问题排查

### 10.1 502

```bash
curl -i http://127.0.0.1:8000/api/health
curl -i http://127.0.0.1/api/health
sudo ss -lntp | grep -E ':80|:8000'
sudo nginx -t
sudo journalctl -u edge-platform -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/error.log
```

判断：

- 如果 `127.0.0.1:8000` 不通，先修后端。
- 如果 `127.0.0.1:8000` 通但 Nginx 不通，查 Nginx `proxy_pass`、端口和日志。

### 10.2 Web SSH 或 VNC 失败

检查：

- `/api/ws/` 是否配置了 `Upgrade` 和 `Connection`。
- `proxy_read_timeout` 是否足够长。
- 设备 SSH/VNC 端口是否存在。
- 后端服务器是否能访问 frps 暴露端口。
- 设备 SSH 凭据是否已配置。
- `REMOTE_GATEWAY_HOST` 和 `VNC_GATEWAY_HOST` 是否正确。

### 10.3 文件管理失败

检查：

- `FILE_BACKEND` 是 `local` 还是 `sftp`。
- 如果是 `sftp`，设备 SSH 端口和凭据是否可用。
- Nginx 是否设置了足够的 `client_max_body_size`。

### 10.4 自动部署失败

检查：

- CI Secrets 是否正确。
- `deploy` 用户是否能 SSH 登录服务器。
- `/opt/edge-platform/deploy.sh` 是否存在且可执行。
- `deploy` 用户的 sudoers 免密范围是否覆盖脚本需要的命令；脚本优先使用 `/opt/edge-platform/.venv/bin/python`，仅在创建虚拟环境时使用 `command -v python3.12` 解析到的系统 Python 绝对路径。
- `TARGET_SHA` 是否来自成功 CI 的 main push，且目标 revision 属于 `origin/main`。
- 服务器 tracked worktree 是否存在未提交改动；部署脚本会主动拒绝脏工作区。
- 如果日志显示 `mktemp ... /tmp ... Permission denied`，说明服务器全局临时目录不可写。仓库 workflow 已改用 `deploy` 用户 home 下权限为 `0700` 的 `.cache/edge-platform-deploy`；确认 `/home/deploy` 存在、归属 `deploy:deploy` 且可写后重试。
- 如果日志出现 `insufficient permission for adding an object to repository database .git/objects`，说明 `/opt/edge-platform` 或 `.git/objects` 被 root/其他用户写过，执行 `sudo chown -R edge-platform:edge-platform /opt/edge-platform` 后重试，并确认 sudoers 允许 CI 用户执行该命令。
- `npm ci` 是否因为 `package-lock.json` 不一致失败。

## 11. OpenClaw 执行约束

OpenClaw 必须遵守：

1. 改服务器前先回显最终变量：`REPO_URL`、`DEPLOY_BRANCH`、`APP_ROOT`、`APP_USER`、`DOMAIN`、`DATA_ROOT`、`BACKUP_ROOT`。
2. 不把密钥、密码、私钥写入 Git 仓库。
3. 不把 SQLite 数据库放在自动拉取会覆盖的代码目录中。
4. 后端只绑定 `127.0.0.1`。
5. 所有公网访问统一经过 Nginx。
6. 保留 `/api/ws/` WebSocket 代理配置。
7. 每次升级前备份 SQLite。
8. 部署后报告 Git revision、systemd 状态、健康检查结果、Nginx 检查结果和诊断摘要。
9. 如果 Python 3.12、Git 凭据、域名、frps 地址或密钥缺失，应暂停并向操作者确认。

## 12. 可直接给 OpenClaw 的任务描述

```text
请按照仓库 docs/openclaw-deployment-runbook.md 部署当前远程终端平台。

部署变量：
- REPO_URL=<填写仓库地址>
- DEPLOY_BRANCH=main
- APP_ROOT=/opt/edge-platform
- APP_USER=edge-platform
- DOMAIN=<填写域名或服务器IP>
- BACKEND_PORT=8000
- DATA_ROOT=/var/lib/edge-platform
- BACKUP_ROOT=/var/backups/edge-platform
- FRPS_HOST=<填写frps地址，暂不接入真实设备可先用127.0.0.1>

要求：
1. 使用 systemd 托管 FastAPI 后端。
2. 使用 Nginx 托管前端静态文件，并反代 /api/ 和 /api/ws/。
3. SQLite 和上传文件必须放在 DATA_ROOT，不要放在代码目录。
4. 当前使用服务器现有 `/opt/edge-platform/deploy.sh`；调用前必须 fast-forward 并确认 checkout 与 CI 验证的 Git SHA 一致。
5. 只有 main push 的 CI 全部成功后才能通过 SSH 执行 deploy.sh；如果无法判断 Git 平台，输出 GitHub/GitLab/Gitee 的门控配置建议。
6. 部署结束后执行 /api/health、Nginx 检查和 systemd 日志检查，并报告结果。
```
