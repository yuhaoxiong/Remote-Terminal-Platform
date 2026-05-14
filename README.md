# AI 边缘设备远程管理平台

这是一个面向 Debian 边缘设备的 Web 远程管理平台。系统通过 `frp` 暴露 SSH/VNC 隧道，在服务端集中管理设备、端口、状态监控、远程入口、批量更新、文件管理、定时任务和操作日志。

当前项目包含：

- FastAPI 后端服务
- Vue 3 + Element Plus + TypeScript 前端
- SQLite 本地数据库
- 后端/前端自动化测试
- 部署、边缘设备初始化和 SQLite 备份脚本

## 当前能力

- 管理员登录认证，支持 JWT access/refresh token。
- 设备 CRUD，自动分配 SSH/VNC 代理端口。
- 生成设备 `frpc` 配置片段，并提供配置同步接口。
- 设备分组、标签、项目号、状态筛选。
- 设备状态、指标记录和监控总览。
- 远程 SSH/VNC 会话描述接口、Web SSH WebSocket 和 VNC WebSocket-to-TCP 代理。
- 批量更新任务创建、执行、取消、单设备状态追踪和 WebSocket 进度快照。
- 操作日志查询和 CSV 导出。
- 设备文件管理接口：列表、上传、下载、删除，支持本地开发后端与 SFTP 后端。
- 定时任务接口：创建、列表、更新、删除、启停、执行和执行日志。
- 前端操作界面：登录、仪表盘、设备、分组、远程入口、更新任务和日志。
- 部署辅助资产：后端安装、边缘设备引导、SQLite 备份和部署文档。

## 项目结构

```text
backend/                 FastAPI 后端、SQLAlchemy 模型、pytest 测试
frontend/                Vue 3 前端、Vitest 测试、Vite 构建配置
scripts/deploy/          部署、边缘设备初始化和备份脚本
docs/                    需求、执行计划和部署文档
outputs/runtime/         Vibe 执行证据和验收产物
data/                    本地运行数据
logs/                    本地开发日志
```

## 环境要求

- Python 3.12。当前固定依赖中的 SQLAlchemy 版本不适合使用 Python 3.14 运行测试。
- Node.js 与 npm。
- Windows PowerShell。本 README 的本地命令以 PowerShell 为准。

建议在执行中文路径相关命令前设置 UTF-8：

```powershell
[Console]::InputEncoding  = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null
```

## 后端开发

安装依赖：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
py -3.12 -m pip install -r requirements.txt
```

运行后端测试：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'
```

启动 API 服务：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
$env:PYTHONPATH=(Get-Location).Path
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认开发账号：

```text
用户名：admin
密码：admin
```

测试环境会通过测试配置使用 `admin-pass`。

## 前端开发

安装依赖：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd install
```

运行前端测试：

```powershell
npm.cmd test -- --run
```

构建前端：

```powershell
npm.cmd run build
```

启动开发服务器：

```powershell
npm.cmd run dev -- --port 5177 --host 127.0.0.1
```

如需让前端代理到非默认后端端口，可以先设置代理目标：

```powershell
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8010'
npm.cmd run dev -- --port 5177 --host 127.0.0.1
```

访问地址：

```text
http://127.0.0.1:5177/
```

当前前端已接入真实后端 API，登录后会通过 JWT 鉴权加载设备、分组、监控总览、批量更新任务和操作日志。设备创建、批量任务创建和任务执行会调用后端接口；远程 SSH/VNC 入口会请求真实会话描述，并可连接后端 WebSocket。

远程连接相关后端配置：

```powershell
$env:REMOTE_GATEWAY_HOST='127.0.0.1'
$env:VNC_GATEWAY_HOST='127.0.0.1'
$env:SSH_PASSWORD='<测试设备 SSH 密码>'
$env:SSH_KEY_FILENAME='C:\path\to\id_ed25519'
$env:SSH_KEY_PASSPHRASE='<私钥口令>'
$env:FILE_BACKEND='sftp'
```

`FILE_BACKEND` 默认是 `local`，用于没有真实设备的本地开发；设置为 `sftp` 后，文件列表、上传、下载和删除会通过设备 frp SSH 端口访问真实设备。

## API 概览

所有已认证 REST API 默认使用 `/api` 前缀。

### 系统

- `GET /api/health`

### 认证

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`
- `PUT /api/auth/password`

### 设备

- `GET /api/devices`
- `POST /api/devices`
- `GET /api/devices/{id}`
- `PUT /api/devices/{id}`
- `DELETE /api/devices/{id}`
- `GET /api/devices/{id}/status`
- `POST /api/devices/{id}/sync-config`
- `POST /api/devices/{id}/metrics`
- `GET /api/devices/{id}/metrics`
- `POST /api/devices/{id}/remote/ssh`
- `POST /api/devices/{id}/remote/vnc`

### 文件

- `GET /api/devices/{id}/files`
- `POST /api/devices/{id}/files/upload`
- `GET /api/devices/{id}/files/download`
- `DELETE /api/devices/{id}/files`

### 分组

- `GET /api/groups`
- `POST /api/groups`
- `PUT /api/groups/{id}`
- `DELETE /api/groups/{id}`

### 批量更新任务

- `GET /api/update-tasks`
- `POST /api/update-tasks`
- `GET /api/update-tasks/{id}`
- `POST /api/update-tasks/{id}/execute`
- `POST /api/update-tasks/{id}/cancel`
- `WS /api/ws/update-tasks/{id}?token=<access-token>`

### 定时任务

- `GET /api/scheduled-tasks`
- `POST /api/scheduled-tasks`
- `PUT /api/scheduled-tasks/{id}`
- `DELETE /api/scheduled-tasks/{id}`
- `POST /api/scheduled-tasks/{id}/toggle`
- `POST /api/scheduled-tasks/{id}/execute`
- `GET /api/scheduled-tasks/{id}/logs`

### 监控和日志

- `GET /api/monitoring/overview`
- `GET /api/logs`
- `GET /api/logs/export`

## 部署资产

部署文档：

```text
docs/deployment.md
```

辅助脚本：

```text
scripts/deploy/install_backend.ps1
scripts/deploy/edge_bootstrap.sh
scripts/deploy/backup_sqlite.ps1
```

这些脚本提供后端安装、边缘设备最小 `frpc` 引导和 SQLite 备份的起点。生产环境执行前需要复核安装路径、服务用户、文件权限、JWT 密钥、凭据加密密钥和公网端口策略。

## 当前实现说明

- 默认数据库是 SQLite。
- 设备文件管理默认使用本地存储后端，配置 `FILE_BACKEND=sftp` 后会通过 `paramiko` SFTP 访问真实设备。
- 远程 SSH/VNC 已提供 WebSocket 基础能力：SSH 使用 JSON 消息转发终端输入输出，VNC 使用二进制 WebSocket-to-TCP 代理。完整 noVNC 嵌入式体验和高级安全加固仍是后续工作。
- 批量更新任务已经具备任务和进度模型，但真实设备侧命令执行仍需继续接入 SSH 执行器。
- 前端开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8000`，可以用 `VITE_API_PROXY_TARGET` 覆盖代理目标。
- 前端构建会出现 Vite 大 chunk 警告，原因是 Element Plus 被打进主 chunk；当前不影响构建产物。
- 当前工作区不是 Git 仓库，因此本地变更不会在此环境中自动提交。

## 最近验证记录

最近一次已验证命令：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

最近结果：

- 后端：32 个测试通过。
- 前端：6 个测试通过。
- 前端构建：成功，仍有已知 Vite chunk size 警告。
- Wave 7 联调：后端 `127.0.0.1:8010`、前端 `127.0.0.1:5179`，通过前端代理完成登录、更新任务列表、监控总览、设备创建、设备列表和设备删除验收。
- Wave 8 自动化：通过 SSH/VNC WebSocket 鉴权与转发、SFTP 后端、远程页面会话入口测试；真实设备 SSH/VNC/SFTP 手工联调仍需要提供可访问的测试设备和凭据。
