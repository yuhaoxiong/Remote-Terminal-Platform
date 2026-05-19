# AI 边缘设备远程管理平台

这是一个面向 Debian 边缘设备的 Web 远程管理平台。系统通过 `frp` 暴露 SSH/VNC 隧道,在服务端集中管理设备、端口、状态监控、远程入口、批量更新、文件管理、定时任务和操作日志。

当前项目包含:

- FastAPI 后端服务
- Vue 3 + Element Plus + TypeScript 前端
- SQLite 本地数据库
- 后端/前端自动化测试
- 部署、边缘设备初始化和 SQLite 备份脚本

## 当前能力

- 管理员登录认证,支持 JWT access/refresh token。
- 设备 CRUD,自动分配 SSH/VNC 代理端口。
- 支持从 frps Dashboard 自动发现并导入已有 TCP 代理设备。
- 生成设备 `frpc` 配置片段,并提供配置同步接口。
- 设备分组、标签、项目号、状态筛选。
- 设备状态、指标记录和监控总览。
- 远程 SSH/VNC 会话描述接口、Web SSH WebSocket、内嵌 xterm 终端和 noVNC 画面入口。
- 批量更新任务创建、演练执行、真实 SSH 命令执行、取消、单设备状态追踪和 WebSocket 进度快照。
- 操作日志查询和 CSV 导出。
- 设备文件管理接口:列表、上传、下载、删除,支持本地开发后端与 SFTP 后端。
- 定时任务接口:创建、列表、更新、删除、启停、执行和执行日志。
- 前端操作界面:登录、仪表盘、设备、分组、远程连接、更新任务、日志和系统诊断。
- 部署辅助资产:后端安装、边缘设备引导、SQLite 备份和部署文档。

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

建议在执行中文路径相关命令前设置 UTF-8:

```powershell
[Console]::InputEncoding  = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
chcp 65001 > $null
```

## 后端开发

安装依赖:

```powershell
cd C:\01_work\02_program\远程终端平台\backend
py -3.12 -m pip install -r requirements.txt
```

运行后端测试:

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'
```

启动 API 服务:

```powershell
cd C:\01_work\02_program\远程终端平台\backend
$env:PYTHONPATH=(Get-Location).Path
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认开发账号:

```text
用户名:admin
密码:admin
```

测试环境会通过测试配置使用 `admin-pass`。

## 前端开发

安装依赖:

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd install
```

运行前端测试:

```powershell
npm.cmd test -- --run
```

构建前端:

```powershell
npm.cmd run build
```

启动开发服务器:

```powershell
npm.cmd run dev -- --port 5177 --host 127.0.0.1
```

如需让前端代理到非默认后端端口,可以先设置代理目标:

```powershell
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8010'
npm.cmd run dev -- --port 5177 --host 127.0.0.1
```

访问地址:

```text
http://127.0.0.1:5177/
```

当前前端已接入真实后端 API,登录后会通过 JWT 鉴权加载设备、分组、监控总览、批量更新任务和操作日志。设备创建、批量任务创建和任务执行会调用后端接口;"远程连接"页支持选择设备后打开 SSH xterm 终端或 noVNC 画面,并连接后端 WebSocket。

远程连接相关后端配置:

```powershell
$env:REMOTE_GATEWAY_HOST='127.0.0.1'
$env:VNC_GATEWAY_HOST='127.0.0.1'
$env:SSH_PASSWORD='<测试设备 SSH 密码>'
$env:SSH_KEY_FILENAME='C:\path\to\id_ed25519'
$env:SSH_KEY_PASSPHRASE='<私钥口令>'
$env:FILE_BACKEND='sftp'
$env:CREDENTIAL_ENCRYPTION_KEY='<Fernet 密钥>'
```

`FILE_BACKEND` 默认是 `local`,用于没有真实设备的本地开发;设置为 `sftp` 后,文件列表、上传、下载和删除会通过设备 frp SSH 端口访问真实设备。远程 SSH/VNC 连接依赖设备记录中的代理端口、设备级 SSH 凭据、frpc/frps 可达性和 Nginx WebSocket 代理。

生成 `CREDENTIAL_ENCRYPTION_KEY`:

```powershell
py -3.12 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

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

### frps 导入

- `POST /api/frps/discover`
- `POST /api/frps/import`

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

部署文档:

```text
docs/deployment.md
```

辅助脚本:

```text
scripts/deploy/install_backend.ps1
scripts/deploy/edge_bootstrap.sh
scripts/deploy/backup_sqlite.ps1
```

这些脚本提供后端安装、边缘设备最小 `frpc` 引导和 SQLite 备份的起点。生产环境执行前需要复核安装路径、服务用户、文件权限、JWT 密钥、凭据加密密钥和公网端口策略。

## 当前实现说明

- 默认数据库是 SQLite。
- frps 导入会读取 Dashboard `/api/proxy/tcp`,按端口范围识别已有设备。当前默认规则是 SSH `12001-17000`,VNC `17001-22000`,VNC 端口与 SSH 端口一一对应且偏移 5000。
- 设备文件管理默认使用本地存储后端,配置 `FILE_BACKEND=sftp` 后会通过 `paramiko` SFTP 访问真实设备。
- 远程 SSH/VNC 已提供产品化入口:SSH 使用 xterm 和 JSON WebSocket 转发终端输入输出、resize 和断开;VNC 使用 noVNC 连接二进制 WebSocket-to-TCP 代理,支持内嵌连接、断开和全屏。
- 批量更新任务默认使用演练模式;选择"真实 SSH 执行"后会通过设备级 SSH 凭据连接 frp SSH 端口并执行命令,记录退出码、标准输出摘要、错误输出摘要和失败原因。
- 前端开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8000`,可以用 `VITE_API_PROXY_TARGET` 覆盖代理目标。
- 前端构建会出现 Vite 大 chunk 警告,原因是 Element Plus 被打进主 chunk;当前不影响构建产物。
- 当前工作区是 Git 仓库;提交或推送前请确认没有暂存无关本地文档。

## 最近验证记录

最近一次已验证命令:

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

最近结果:

- 后端:51 个测试通过。
- 前端:17 个测试通过。
- 前端构建:成功,仍有已知 Vite chunk size 警告。
- Wave 7 联调:后端 `127.0.0.1:8010`、前端 `127.0.0.1:5179`,通过前端代理完成登录、更新任务列表、监控总览、设备创建、设备列表和设备删除验收。
- Wave 8 自动化:通过 SSH/VNC WebSocket 鉴权与转发、SFTP 后端、远程页面会话入口测试;真实设备 SSH/VNC/SFTP 手工联调仍需要提供可访问的测试设备和凭据。
- frps 导入:通过 Dashboard TCP 代理预览、导入、重复导入跳过、端口池预留和前端导入入口测试。
## Wave 9 补充说明

- 新增 `GET /api/diagnostics/config`,用于查看非敏感运行配置摘要。该接口需要登录鉴权,不返回密码、Token 或私钥内容。
- `GET /api/health` 现在包含数据库连接状态,可用于服务器 502 排查。
- 设备级 SSH 凭据支持默认用户 `ztl` 和默认密码 `123456`。本轮按需求直接保存到数据库,后续应改为加密保存;API 响应不会返回明文密码。
- frps 导入支持重复同步、端口冲突诊断、缺失 VNC 标记和离线代理标记;只有勾选"覆盖项目号和位置"时才更新已有设备的项目号和部署位置。
- 服务器正式测试建议使用 Nginx 单域名反向代理:前端静态文件、`/api`、`/api/ws` 均走同一个域名。

## Postman 验收

仓库内提供 Postman Collection:

```text
docs/postman/edge-platform.postman_collection.json
```

导入后先运行"登录"请求,Tests 脚本会自动保存 `access_token` 和 `refresh_token`;其他接口继承集合级 Bearer Token `{{access_token}}`。

常见错误:如果出现 `Cannot read property 'json' of undefined`,说明脚本被放到了 Pre-request Script。保存 Token 的脚本必须放在登录请求的 Tests 中。

集合中的"批量 SSH 任务"文件夹提供演练任务、真实 SSH 任务、执行任务和查询任务详情请求。运行真实 SSH 任务前先确认 `project_id` 命中的设备已导入并能通过 frp SSH 端口访问。

## Wave 10 补充说明

- 批量更新任务新增 `execution_mode` 字段:`dry_run` 表示演练模式,`ssh_command` 表示真实 SSH 执行。
- 演练模式不会连接设备,单设备结果会标记为"已跳过",用于确认筛选范围和命令内容。
- 真实 SSH 执行会按任务目标设备逐台执行命令,并在任务详情中返回 `exit_code`、`stdout_summary`、`stderr_summary` 和 `error_message`。
- `failure_strategy=continue` 会继续执行后续设备;`pause` 和 `rollback` 会在首个失败后跳过后续待执行设备。本轮暂不自动执行回滚命令,只会在结果中记录提示。
- 真实执行依赖设备记录中的 SSH 用户和密码。Wave 9 导入设备默认使用 `ztl` / `123456`,后续生产环境应改为加密保存凭据。

## Wave 11 补充说明

- 新增设备 SSH 凭据加密配置 `CREDENTIAL_ENCRYPTION_KEY`。配置后,新建、更新和 frps 导入写入的设备 SSH 密码会以 Fernet 密文保存。
- 旧数据库中的明文凭据仍可兼容读取,避免升级后已有设备无法 SSH;设备下次更新密码时会按新配置写入密文。
- `GET /api/diagnostics/config` 新增 `security` 摘要,用于提示默认 JWT 密钥、默认管理员密码、默认设备 SSH 密码和未配置凭据加密等风险;接口不返回密钥、Token、私钥或明文密码。
- 前端设备管理补齐编辑、删除和单设备状态刷新。编辑设备时,SSH 密码留空表示不修改已有凭据。
- 批量更新真实 SSH 任务在创建和执行前会显示确认提示;任务列表支持取消待执行或执行中的任务。

## Wave 12 补充说明

- 前端顶栏新增"修改密码",调用 `PUT /api/auth/password`;修改成功后会清理本地 Token 并回到登录页。
- 分组管理页支持创建、编辑、删除分组;设备表支持按分组筛选,设备创建和编辑会提交 `group_id`。
- 操作日志页支持按 `action`、`target_type`、`status` 筛选,接入分页,并可下载 `operation_logs.csv`。
- 日志 CSV 导出新增下载响应头和 CSV 注入防护:以 `=`、`+`、`-`、`@`、制表符或换行开头的字符串会在导出时加前导制表符。
- 设备管理表新增"同步配置",可生成并查看 `POST /api/devices/{id}/sync-config` 返回的 frpc 配置。
- 新增"系统诊断"前端页,展示 `GET /api/diagnostics/config` 的非敏感运行摘要和安全提醒。

## Wave 13 监控可观测性补充

- 前端仪表盘的"资源快照"现在读取真实设备指标,不再把无指标设备显示为 `0%`。
- 最新指标来自 `GET /api/devices/{id}/metrics?limit=1`,每台设备独立加载;单台指标失败只显示"指标加载失败",不会退出登录。
- 指标超过 10 分钟未更新时显示"指标过期",高 CPU、高内存、高磁盘和离线/未知设备会进入"异常设备"摘要。
- 仪表盘新增 ECharts 监控分布图,同时保留文字统计,便于在图表不可用时继续验收。
- 系统诊断页新增"监控可用性",展示有指标设备数、无指标设备数和最近指标时间。
- Postman Collection 新增"Wave 13 监控指标"分组,可直接上报示例指标、查询最新指标和监控总览。

## Wave 14 远程连接体验补充

- "远程连接"页改为左侧设备列表、右侧操作区。设备可按名称、序列号、项目号和位置搜索;缺少 SSH/VNC 端口或 SSH 凭据时会在页面中显示中文原因并禁用对应连接。
- SSH 连接流程为:调用 `POST /api/devices/{id}/remote/ssh` 获取会话描述,前端拼接 `?token=<access_token>` 后连接 `/api/ws/devices/{id}/ssh`,终端输入发送 `{ "type": "input", "data": "..." }`,窗口变化发送 `{ "type": "resize", "columns": N, "rows": M }`。
- VNC 连接流程为:调用 `POST /api/devices/{id}/remote/vnc` 获取会话描述,前端用 noVNC 连接 `/api/ws/devices/{id}/vnc?token=<access_token>`,支持连接、断开和浏览器全屏。
- 远程连接失败只显示在远程连接区域;只有 REST 接口返回 401/403 时才会清理 Token 并回到登录页。
- SSH 终端依赖已使用 `@xterm/xterm` 和 `@xterm/addon-fit`,避免继续使用已废弃的旧 `xterm` 包。

## Wave 15 文件与定时任务前端闭环补充

- 设备管理表新增"文件"入口,点击后在设备操作区打开文件管理面板,支持目录浏览、返回上级、任意文件类型上传、下载和删除。
- 文件上传前端使用 `multipart/form-data`,字段为 `remote_path` 和 `file`;后端仍兼容旧 JSON 文本上传格式,便于已有脚本平滑迁移。
- 文件下载接口现在返回二进制响应,并带 `Content-Disposition` 下载头;`Content-Type` 会按文件名推断,无法推断时使用 `application/octet-stream`。
- 新增"定时任务"前端页面,覆盖任务创建、编辑、删除、启停、手动执行和执行日志查看。本轮仍只做 API 管理闭环,不接入真实后台调度器。
- 前端开始拆分独立组件,当前已拆出 `DeviceFilePanel.vue` 和 `ScheduledTaskPanel.vue`,降低主应用文件继续膨胀的风险。
- Web SSH 收到 `{ "type": "close" }` 后会先关闭后端 shell,再返回 `{ "type": "status", "status": "closed" }`,方便客户端和测试确认资源已释放。
