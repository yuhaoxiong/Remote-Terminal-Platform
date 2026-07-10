# AI 边缘设备远程管理平台

这是一个面向 Debian 边缘设备的 Web 远程管理平台。系统通过 `frp` 暴露 SSH/VNC 隧道,在服务端集中管理设备、端口、状态监控、远程入口、批量更新、文件管理、定时任务和操作日志。

当前项目包含:

- FastAPI 后端服务
- Vue 3 + Element Plus + TypeScript 前端
- SQLite 本地数据库
- 后端/前端自动化测试
- 部署、边缘设备初始化和 SQLite 备份脚本

## 当前能力

- 管理员和运维人员登录认证,支持 JWT access/refresh token、角色权限和认证审计。
- 设备 CRUD,自动分配 SSH/VNC 代理端口。
- 支持从 frps Dashboard 自动发现并导入已有 TCP 代理设备。
- 生成设备 `frpc` 配置片段,并提供配置同步接口。
- 设备分组、标签、项目号、状态筛选。
- 设备状态、指标记录、监控总览和告警中心。
- 远程 SSH/VNC 会话描述接口、Web SSH WebSocket、内嵌 xterm 终端和 noVNC 画面入口。
- 批量更新任务创建、目标设备预览、命令模板、演练执行、真实 SSH 命令执行、取消、单设备状态追踪、失败设备重试入口、结果 CSV 导出和 WebSocket 进度快照。
- 操作日志查询和 CSV 导出。
- 设备文件管理接口:列表、上传、下载、删除,支持本地开发后端与 SFTP 后端。
- 定时任务接口:创建、列表、更新、删除、启停、手动执行、自动调度、执行记录和执行日志。
- 告警中心:设备离线/未知、CPU/内存/磁盘阈值、指标冻结、定时任务失败和批量更新失败告警,支持确认、恢复、规则启停和阈值编辑。
- 告警外部通知:支持 Webhook 通道、通知策略、投递记录、失败重试和诊断摘要。
- 前端操作界面:登录、仪表盘、设备、分组、远程连接、更新任务、定时任务、告警中心、用户管理、日志和系统诊断。
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

用户角色说明:

- `admin`:可管理用户、删除设备/分组、创建和执行真实 SSH 批量/定时任务、编辑告警规则和通知配置。
- `operator`:可查看主要运维数据、创建和编辑设备、执行演练任务;无权进入用户管理或执行高风险真实 SSH 操作。

远程连接相关后端配置:

```powershell
$env:REMOTE_GATEWAY_HOST='127.0.0.1'
$env:VNC_GATEWAY_HOST='127.0.0.1'
$env:DEFAULT_VNC_PASSWORD='<默认 VNC 密码>'
$env:SSH_PASSWORD='<测试设备 SSH 密码>'
$env:SSH_KEY_FILENAME='C:\path\to\id_ed25519'
$env:SSH_KEY_PASSPHRASE='<私钥口令>'
$env:FILE_BACKEND='sftp'
$env:CREDENTIAL_ENCRYPTION_KEY='<Fernet 密钥>'
$env:SCHEDULER_ENABLED='true'
$env:SCHEDULER_POLL_INTERVAL_SECONDS='30'
```

`FILE_BACKEND` 默认是 `sftp`,文件列表、上传、下载和删除会通过设备 frp SSH 端口访问真实设备。没有真实设备的本地开发可显式设置为 `local`。远程 SSH/VNC 连接依赖设备记录中的代理端口、设备级 SSH 凭据、frpc/frps 可达性和 Nginx WebSocket 代理。

告警 Webhook 通道的 URL 和请求头会作为敏感配置保存。创建或更新 Webhook 地址、请求头前必须配置 `CREDENTIAL_ENCRYPTION_KEY`;未配置时后端会拒绝保存敏感通知配置。

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

### 用户

- `GET /api/users`
- `POST /api/users`
- `GET /api/users/{id}`
- `PUT /api/users/{id}`
- `POST /api/users/{id}/reset-password`
- `POST /api/users/{id}/toggle`
- `DELETE /api/users/{id}`

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
- `POST /api/update-tasks/preview-targets`
- `GET /api/update-tasks/{id}`
- `POST /api/update-tasks/{id}/execute`
- `POST /api/update-tasks/{id}/cancel`
- `GET /api/update-tasks/{id}/export`
- `GET /api/update-task-templates`
- `POST /api/update-task-templates`
- `PUT /api/update-task-templates/{id}`
- `DELETE /api/update-task-templates/{id}`
- `WS /api/ws/update-tasks/{id}?token=<access-token>`

### 定时任务

- `GET /api/scheduled-tasks`
- `POST /api/scheduled-tasks`
- `PUT /api/scheduled-tasks/{id}`
- `DELETE /api/scheduled-tasks/{id}`
- `POST /api/scheduled-tasks/{id}/toggle`
- `POST /api/scheduled-tasks/{id}/execute`
- `POST /api/scheduled-tasks/{id}/run-now`
- `GET /api/scheduled-tasks/{id}/runs`
- `GET /api/scheduled-tasks/{id}/logs`
- `GET /api/scheduler/status`

### 告警中心

- `GET /api/alerts`
- `GET /api/alerts/summary`
- `POST /api/alerts/{id}/acknowledge`
- `POST /api/alerts/{id}/resolve`
- `GET /api/alert-rules`
- `PUT /api/alert-rules/{id}`
- `GET /api/alert-notification-channels`
- `POST /api/alert-notification-channels`
- `PUT /api/alert-notification-channels/{id}`
- `DELETE /api/alert-notification-channels/{id}`
- `POST /api/alert-notification-channels/{id}/test`
- `GET /api/alert-notification-policies`
- `POST /api/alert-notification-policies`
- `PUT /api/alert-notification-policies/{id}`
- `DELETE /api/alert-notification-policies/{id}`
- `GET /api/alert-notification-deliveries`
- `POST /api/alert-notification-deliveries/{id}/retry`
- `GET /api/alert-notification-summary`

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
scripts/deploy/deploy.sh
```

这些脚本提供后端安装、边缘设备最小 `frpc` 引导和 SQLite 备份的起点。生产环境执行前需要复核安装路径、服务用户、文件权限、JWT 密钥、凭据加密密钥和公网端口策略。

## 当前实现说明

- 默认数据库是 SQLite。
- frps 导入会读取 Dashboard `/api/proxy/tcp`,按端口范围识别已有设备。当前默认规则是 SSH `12001-17000`,VNC `17001-22000`,VNC 端口与 SSH 端口一一对应且偏移 5000。
- 设备文件管理默认使用 `sftp` 后端,通过 `paramiko` SFTP 访问真实设备;本地开发可显式配置 `FILE_BACKEND=local`。
- 远程 SSH/VNC 已提供产品化入口:SSH 使用 xterm 和 JSON WebSocket 转发终端输入输出、resize 和断开;VNC 使用 noVNC 连接二进制 WebSocket-to-TCP 代理,支持内嵌连接、断开和全屏。
- 批量更新任务默认使用演练模式;选择"真实 SSH 执行"后会通过设备级 SSH 凭据连接 frp SSH 端口并执行命令,记录退出码、标准输出摘要、错误输出摘要和失败原因。任务创建区支持目标预览、手动选择设备和命令模板,执行结果支持失败设备新建重试任务和 CSV 导出。
- 定时任务支持 `interval:N` 和 5 位 `cron:` 表达式。后台调度器默认启用,会计算 `next_run_at`,到期后复用批量任务执行链路生成独立执行记录;真实 SSH 调度必须显式选择 `execution_mode=ssh_command`。
- 告警规则启动时会自动初始化。指标阈值默认 CPU/内存 85%、磁盘 90%、指标冻结 10 分钟;设备恢复在线或指标回落后会自动恢复对应活跃告警。
- 告警外部通知目前优先支持 Webhook。默认策略建议只订阅 `critical` 且事件为 `triggered`;确认、手动恢复和自动恢复事件也可按策略开启。删除通道前需要先删除引用该通道的通知策略。
- 用户管理采用 `admin` / `operator` 两类角色。用户删除为停用账号,不会硬删除历史记录;后端会阻止停用或降级最后一个启用管理员。登录、刷新、修改密码、权限拒绝和用户管理操作会写入操作日志。
- 前端开发服务器默认把 `/api` 代理到 `http://127.0.0.1:8000`,可以用 `VITE_API_PROXY_TARGET` 覆盖代理目标。
- 前端已按路由和依赖拆分 chunk;较大的 Element Plus/ECharts vendor chunk 保持延迟加载,当前构建无 Vite 大 chunk 警告。
- 当前工作区是 Git 仓库;提交或推送前请确认没有暂存无关本地文档。

## 最近验证记录

最近一次已验证命令:

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests -q --basetemp .tmp/pytest-all -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

最近结果:

- 后端:116 个测试通过。
- 前端:39 个测试通过。
- 前端 lint:通过。
- 前端类型检查:通过。
- 前端构建:成功,无 Vite chunk size 警告。
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

集合中的"Wave 18 定时任务调度"文件夹提供调度器状态、立即执行、执行记录和非法 cron 校验请求。

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
- 新增"定时任务"前端页面,覆盖任务创建、编辑、删除、启停、手动执行和执行日志查看。Wave 18 已在该页面继续补齐调度器状态、最近执行结果和执行记录。
- 前端开始拆分独立组件,当前已拆出 `DeviceFilePanel.vue` 和 `ScheduledTaskPanel.vue`,降低主应用文件继续膨胀的风险。
- Web SSH 收到 `{ "type": "close" }` 后会先关闭后端 shell,再返回 `{ "type": "status", "status": "closed" }`,方便客户端和测试确认资源已释放。

## Wave 16 批量任务安全增强补充

- 批量更新创建表单新增"目标设备"选择器,支持按项目号、分组、状态、标签筛选,也支持手动勾选设备。手动勾选会生成 `target_filter.device_ids`。
- 新增 `POST /api/update-tasks/preview-targets`,用于在创建真实 SSH 任务前预览命中设备,并提示缺少 SSH 端口或凭据的风险。该接口不返回明文凭据。
- 新增命令模板接口和前端模板面板:`GET/POST/PUT/DELETE /api/update-task-templates`。模板只保存命令、说明、任务类型和默认执行模式,不保存设备凭据。
- 批量任务执行会在前端接入 `/api/ws/update-tasks/{id}?token=<access_token>` 快照,收到 `task.snapshot` 后刷新任务状态和单设备结果。
- 设备结果区域拆为独立表格,可展开查看标准输出、错误输出和失败原因;失败设备可一键带入新任务作为重试范围。
- 新增 `GET /api/update-tasks/{id}/export`,导出任务摘要和错误原因 CSV。导出内容带 CSV 注入防护,不会包含设备 SSH 明文密码。

## Wave 17 后端治理、安全与维护补充

- 后端启动时会先执行 Alembic `upgrade head`,再保留 `create_all` 兼容兜底;`GET /api/diagnostics/config` 会返回 `migration` 摘要,用于确认当前 revision 是否等于 head。
- 设备状态、SSH 凭据类型、批量任务执行模式、失败策略和定时任务类型已收敛为后端枚举校验,未知值会返回 `422`。
- SSH 主机密钥策略新增 `SSH_HOST_KEY_POLICY`,默认保持 `auto_add`;可设置为 `warning` 或 `reject`,并通过 `SSH_KNOWN_HOSTS_FILE` 指定 known_hosts 文件。
- Router 层统一使用共享请求会话和 404/409 错误 helper,减少接口间重复会话处理。
- 前端 access token 过期后会自动使用 refresh token 重试一次;refresh 失败或缺失时会清理本地登录态并直接回到登录页。
- 系统诊断页新增数据库迁移、SSH 主机密钥策略、认证有效期和数据库备份建议展示,仍只显示非敏感摘要。

## Wave 18 定时任务真实调度补充

- 后端新增 APScheduler 调度服务,通过 `SCHEDULER_ENABLED` 控制是否启用,通过 `SCHEDULER_POLL_INTERVAL_SECONDS` 控制到期任务扫描间隔。
- 定时任务表达式仅支持 `interval:N` 和 5 位 `cron:`;创建、更新、启停后会同步刷新 `next_run_at`。
- `POST /api/scheduled-tasks/{id}/execute` 继续保留,并新增 `POST /api/scheduled-tasks/{id}/run-now`;两者都会写入执行记录,可通过 `GET /api/scheduled-tasks/{id}/runs` 查看。
- `task_type=command` 的任务会复用批量更新任务执行链路。`execution_mode=dry_run` 只做演练,`execution_mode=ssh_command` 才会连接设备执行真实 SSH 命令。
- 新增 `GET /api/scheduler/status`,系统诊断页也会展示调度器启停状态、扫描间隔、最近扫描、失败执行数量和告警摘要。

## Wave 19 告警中心与设备健康闭环补充

- 新增告警模型和默认规则表,后端启动会初始化设备状态、指标阈值、指标冻结、定时任务失败和批量更新失败规则。
- 设备状态变为 `offline`/`unknown`、指标超过阈值、指标超过 10 分钟未更新、定时任务失败或批量任务失败时会创建去重告警;状态恢复、指标回落或后续任务成功时会自动恢复对应告警。
- 新增告警 API:`GET /api/alerts`、`GET /api/alerts/summary`、`POST /api/alerts/{id}/acknowledge`、`POST /api/alerts/{id}/resolve`、`GET /api/alert-rules`、`PUT /api/alert-rules/{id}`。
- 前端新增"告警中心"导航,展示活跃/严重/未确认摘要、告警列表、确认/恢复操作和规则启停/阈值编辑。
- `GET /api/diagnostics/config` 新增 `alerts` 非敏感摘要,系统诊断页会显示活跃告警、严重告警和风险提示。

## Wave 20 告警外部通知补充

- 新增 Webhook 通知通道、通知策略和投递记录表,并纳入 Alembic 迁移和 `init_db` 兼容创建。
- Webhook URL 和请求头使用 `CREDENTIAL_ENCRYPTION_KEY` 加密保存;未配置加密密钥时,后端拒绝创建或更新敏感通知配置。
- 告警触发、确认、手动恢复和自动恢复会按通知策略生成投递记录;失败投递会记录状态码、摘要或错误原因,并支持手动重试。
- 默认通知策略建议为 `min_severity=critical` 且 `event_types=["triggered"]`,减少低价值通知噪声。
- 前端"告警中心"新增"外部通知"区域,支持 Webhook 通道、策略、测试发送、最近投递和失败重试。
- `GET /api/diagnostics/config` 新增 `notifications` 非敏感摘要,系统诊断页会展示启用通道、启用策略、失败投递和风险提示。

## Wave 21 用户角色与会话审计补充

- 用户表新增角色、启停状态、最近登录时间、最近登录 IP 和密码更新时间字段,并通过 Alembic 迁移升级旧 SQLite 数据库。
- 默认 `admin` 账号会被迁移为管理员;新建用户默认角色为 `operator`。
- 新增用户管理 API:`GET/POST /api/users`、`GET/PUT /api/users/{id}`、`POST /api/users/{id}/reset-password`、`POST /api/users/{id}/toggle`、`DELETE /api/users/{id}`。这些接口仅管理员可用。
- 权限边界已收敛:设备/分组删除、真实 SSH 批量任务、真实 SSH 定时任务、告警规则编辑和告警外部通知配置需要管理员;运维人员保留查看、设备创建/编辑和演练任务能力。
- 前端登录页改为用户名和密码;管理员登录后显示"用户管理"导航,运维人员不会显示该入口。接口返回 `403` 时前端提示无权限,不会误判为登录过期。
- `GET /api/diagnostics/config` 新增 `users` 非敏感摘要,系统诊断页会展示启用用户、管理员、运维人员和停用用户数量。

## Wave 23 系统设置补充

- 新增仅管理员可见的"系统设置"页面,用于管理后端注册表白名单内的非敏感运行参数。
- 配置读取顺序为 `数据库覆盖值 > 系统配置/环境变量 > 代码默认值`;后端启动时加载数据库覆盖值到内存,保存可即时生效的配置后会刷新当前进程缓存。
- 系统设置按分组保存,当前覆盖远程连接、设备凭据、文件存储、定时调度、告警通知和认证会话等通用运行参数;远程连接分组支持配置默认 VNC 密码,连接页手动输入值优先于默认值;`DATABASE_URL`、`JWT_SECRET_KEY`、`CREDENTIAL_ENCRYPTION_KEY` 等敏感或启动级配置仅展示脱敏只读状态。
- 需要重启后生效的配置会标记"待重启",保存时前端会弹窗提示;服务重启成功并重新加载配置后会自动清除待重启标记。
- 后端新增系统设置变更历史表,保存、恢复默认和重启动作同时写入现有操作日志。敏感配置历史只记录脱敏快照,不返回明文密码、Token、私钥或加密密钥。
- 系统设置页提供"重启服务"按钮。该功能仅在后端检测到 systemd 托管时允许执行,接口返回 `202` 后延迟退出进程,依赖 systemd `Restart=always` 或等价策略自动拉起。
- `operator` 不显示系统设置入口,直接调用系统设置 API 会返回 `403`;系统诊断页仍向 `operator` 展示有限、脱敏的系统设置摘要。
