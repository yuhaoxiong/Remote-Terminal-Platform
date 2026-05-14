# AI边缘设备远程管理平台实际执行计划

## 1. 目标与依据

本计划依据 `docs/01-需求与架构设计文档.md`，目标是实现一个 Web 端远程管理平台，用于统一管理基于 Debian 11、通过 frp 暴露 SSH/VNC 的 AI 边缘设备。

本轮执行只规划实现，不直接修改业务代码。后续进入实现阶段时，所有行为变更必须按 TDD 执行：先写失败测试，再实现，再跑绿，再重构。

## 2. 默认决策与待确认项

默认决策：

- MVP 先交付 P0：认证、设备管理、端口池、frpc 配置同步、在线检测、Web SSH、Web VNC、批量更新基础能力。
- P1/P2 作为后续增量：分组标签、资源监控、操作日志、仪表盘、文件传输、定时任务、部署脚本。
- 项目采用单仓结构：`backend/`、`frontend/`、`scripts/`、`docs/`。
- 后端使用 FastAPI + SQLAlchemy + SQLite + Alembic；即使 SQLite 是单文件，也从首版启用迁移，避免后续表结构失控。
- 前端使用 Vue 3 + TypeScript + Element Plus + Pinia + Vue Router + Axios。
- 认证采用单用户 JWT；密码存数据库 bcrypt hash，支持 refresh token；所有 REST API 和 WebSocket 握手都校验 token。
- SSH 密码和私钥使用后端统一加密服务封装，密钥从环境变量读取；本地开发允许 `.env`，生产禁止提交密钥。
- 新设备首次注册采用需求文档推荐的方案 A：设备预装最小 frpc 注册通道；平台也保留手动填写已有 SSH 可达地址的注册入口。
- 端口池固定初始化为 SSH `10000-10499`、VNC `10500-10999`，删除设备后释放端口复用。
- Web VNC 首版实现后端 WebSocket-to-TCP 代理和前端 noVNC 连接；高级剪贴板同步可后置到稳定化阶段。

待确认项：

- frps 管理方式：平台是否需要自动修改云服务器 frps 配置，还是只生成/同步设备端 frpc 配置。
- 设备注册脚本与平台 API 的鉴权方式：预共享注册 token、一次性邀请码，或管理员手动创建设备后下发 token。
- 批量更新的回滚定义：仅记录失败并提示人工处理，还是每类任务都必须有可执行 rollback command。
- VNC 密码来源：平台保存、设备固定配置、还是注册时由管理员输入。

## 3. 实施波次

### Wave 0：项目骨架与质量门

- 建立 `backend/`、`frontend/`、`scripts/` 目录；配置 Python 3.11、FastAPI、SQLAlchemy、Alembic、pytest、ruff 或等价 lint。
- 建立 Vue 3 + Vite + TypeScript + Element Plus 项目；配置 Vitest、Playwright smoke 测试、ESLint/Prettier。
- 定义后端配置模型：数据库路径、JWT 密钥、凭据加密密钥、frps 主机、端口范围、SSH/VNC 超时、调度频率。
- 验收：后端健康检查测试通过，前端能构建，CI/本地命令文档可运行。

### Wave 1：后端核心域模型与认证

- 实现数据库模型与迁移：`devices`、`groups`、`device_metrics`、`operation_logs`、`update_tasks`、`update_task_devices`、`scheduled_tasks`、`port_pool`。
- 实现端口池服务：初始化端口、按类型分配、释放、冲突检测、事务保护。
- 实现凭据加密服务、单用户认证、JWT 登录/刷新/当前用户/修改密码接口。
- 实现操作日志基础服务，后续远程操作统一写入。
- TDD 场景：端口分配复用、重复设备序列号、认证失败、token 过期、凭据加密解密、日志写入失败降级。
- 验收：`/api/auth/*` 可用，端口池行为可测，数据库迁移可从空库建立完整 schema。

### Wave 2：设备管理与 frpc 配置同步

- 实现设备 CRUD、分页筛选搜索、项目号/状态/分组/标签过滤。
- 实现 frpc 配置生成服务，按设备分配的 SSH/VNC 端口生成配置片段。
- 实现 SSH 执行服务封装：连接、命令执行、SFTP 写文件、备份、重启服务、错误归一化。
- 实现 `/api/devices/{id}/sync-config`：生成配置、备份旧配置、写入新配置、重启 frpc、验证端口连通。
- TDD 场景：注册设备自动分配两个端口、删除设备释放端口、frpc 模板输出稳定、SSH 同步失败保留旧状态、同步成功写日志。
- 验收：管理员可完成设备注册、编辑、删除、同步 frpc 配置，失败有可读错误和日志。

### Wave 3：在线检测、资源采集与远程连接

- 实现在线检测：TCP 端口探测、SSH `echo ok` 检测、连续失败阈值、`online/offline/degraded/unknown` 状态更新。
- 实现 APScheduler 内置任务：健康检查 60 秒一次，资源采集按需求频率执行。
- 实现资源解析器：CPU、内存、磁盘、温度、load、uptime、GPU 可选指标，并写入 `device_metrics`。
- 实现 Web SSH：`/ws/ssh/{device_id}`，xterm.js 双向转发，resize 支持，空闲超时。
- 实现 Web VNC：`/ws/vnc/{device_id}`，后端 WebSocket-to-TCP relay，前端 noVNC 页面连接。
- TDD 场景：状态机阈值、指标解析边界、WebSocket token 拒绝、SSH channel 关闭传播、VNC TCP 连接失败提示。
- 验收：设备列表可显示状态，设备详情可查看最新指标，浏览器可打开 SSH/VNC 会话。

### Wave 4：批量更新、分组标签与审计

- 实现分组树与标签接口，设备列表支持组合筛选。
- 实现更新任务模型与接口：创建、查询、执行、取消、按设备状态跟踪。
- 实现更新执行器：按目标过滤设备，按并发数批量执行，支持 program/system/script/config 四类任务。
- 实现失败策略：`continue` 继续剩余设备，`pause` 停止后续设备，`rollback` 首版要求提供 rollback command，否则拒绝创建。
- 实现 `/ws/update-tasks/{id}` 推送进度和设备输出摘要。
- 完善操作日志查询与 CSV 导出。
- TDD 场景：目标筛选、并发限制、取消任务、部分失败状态、rollback 缺失校验、WebSocket 进度事件。
- 验收：可按项目/分组/标签执行批量脚本或更新，任务详情能追踪每台设备结果。

### Wave 5：前端完整操作面

- 实现登录、主布局、路由守卫、token 刷新、Axios 错误处理。
- 实现设备列表、设备创建、设备详情、分组管理、标签编辑、SSH 页面、VNC 页面。
- 实现更新任务列表、创建、详情、进度推送。
- 实现资源图表、操作日志查询、仪表盘概览。
- P2 页面在核心闭环稳定后补齐：文件管理、定时任务、系统设置。
- TDD/验证：关键组件单测、API mock 测试、Playwright 覆盖登录、设备注册、SSH/VNC 入口、更新任务创建。
- 验收：管理员能通过 UI 完成 P0 全流程，不需要直接调用 API。

### Wave 6：文件传输、定时任务、部署与文档

- 实现 SFTP 文件浏览、上传、下载、删除；大文件用流式传输和进度提示。
- 实现定时任务 CRUD、启停、执行历史；内置健康检查与资源采集任务可配置。
- 编写部署脚本：后端虚拟环境、前端构建、Nginx 配置、systemd service、SQLite 文件权限。
- 编写边缘设备初始化脚本：最小 frpc 注册通道、SSH/VNC 服务检查、注册 token 配置。
- 编写备份方案：SQLite 定时备份、上传目录清理、配置导出。
- 验收：全量部署到一台 Linux 测试机后，按文档可从零启动平台。

## 4. 公共接口与数据契约

必须实现的 REST API：

- 认证：`POST /api/auth/login`、`POST /api/auth/refresh`、`GET /api/auth/me`、`PUT /api/auth/password`
- 设备：`GET/POST /api/devices`、`GET/PUT/DELETE /api/devices/{id}`、`POST /api/devices/{id}/sync-config`、`GET /api/devices/{id}/status`
- 分组标签：`GET/POST /api/groups`、`PUT/DELETE /api/groups/{id}`、`POST /api/devices/{id}/tags`、`DELETE /api/devices/{id}/tags/{tag}`
- 指标：`GET /api/devices/{id}/metrics`、`/latest`、`/history`
- 更新任务：`GET/POST /api/update-tasks`、`GET /api/update-tasks/{id}`、`POST /api/update-tasks/{id}/execute`、`POST /api/update-tasks/{id}/cancel`
- 文件：`GET /api/devices/{id}/files`、`POST /api/devices/{id}/files/upload`、`GET /api/devices/{id}/files/download`、`DELETE /api/devices/{id}/files`
- 定时任务：`GET/POST /api/scheduled-tasks`、`PUT/DELETE /api/scheduled-tasks/{id}`、`POST /api/scheduled-tasks/{id}/toggle`、`GET /api/scheduled-tasks/{id}/logs`
- 日志与仪表盘：`GET /api/logs`、`GET /api/logs/export`、`GET /api/dashboard/summary`、`GET /api/dashboard/device-stats`、`GET /api/dashboard/recent-logs`、`GET /api/dashboard/recent-alerts`

必须实现的 WebSocket：

- `/ws/ssh/{device_id}`：xterm.js SSH 终端流
- `/ws/vnc/{device_id}`：noVNC 代理流
- `/ws/update-tasks/{id}`：批量更新进度推送

## 5. 验证计划

- 后端：pytest + FastAPI TestClient；SQLite 使用临时库；paramiko、TCP socket、APScheduler 用 mock/fake。
- 前端：Vitest 覆盖 store、API wrapper、关键表单和状态展示；Playwright 覆盖核心用户路径。
- 集成：提供 docker 或本地脚本启动后端、前端、测试数据库；用假设备服务模拟 SSH/VNC/TCP 成功与失败。
- 安全：认证绕过、WebSocket 无 token、凭据明文落库、危险批量命令二次确认全部设为阻断测试。
- 性能边界：端口池 500 台设备、批量更新默认并发 5、设备列表分页、指标历史查询索引。

## 6. 交付验收

MVP 完成条件：

- 从空库迁移后能登录平台。
- 能注册设备并自动分配 SSH/VNC 端口。
- 能生成并通过 SSH 同步 frpc 配置，失败时不吞错。
- 能检测设备在线状态并展示。
- 能在浏览器打开 SSH 和 VNC。
- 能创建并执行批量更新任务，实时展示每台设备进度。
- 关键远程操作都有操作日志。
- 后端和前端测试通过，核心路径有 Playwright smoke 证据。

非 MVP 完成条件：

- 文件传输、定时任务、仪表盘、部署脚本和边缘初始化脚本按 Wave 6 验收。
- 所有密钥、数据库文件和上传目录权限符合安全设计。
- 部署文档能支持在云服务器上复现安装。

