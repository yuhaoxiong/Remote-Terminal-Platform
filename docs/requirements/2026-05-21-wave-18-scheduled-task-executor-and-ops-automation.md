# Wave 18 需求文档：定时任务真实调度与运维自动化闭环

> 阶段：`requirement_doc`  
> 状态：已确认，下一步进入执行计划  
> 基线：Wave 17 已完成后端治理、安全边界、Alembic 迁移、Router 收敛、枚举约束、known_hosts 策略、诊断扩展和前端 token 自动刷新。平台核心功能已经具备生产测试基础，下一步应优先把“定时任务 API 管理闭环”升级为可真实运行的后台调度能力。

## 1. 背景

截至 Wave 17，平台已经具备：

- 管理员登录、JWT access/refresh token、修改密码和前端自动 refresh。
- 设备 CRUD、分组、标签、frps Dashboard 导入、设备级 SSH 凭据、凭据加密和 known_hosts 策略。
- Web SSH、VNC、设备文件管理、设备指标、监控总览、系统诊断和操作日志。
- 批量更新任务：目标预览、命令模板、dry-run、真实 SSH 执行、失败设备重试、结果 CSV 导出和 WebSocket 快照。
- 定时任务 API 和前端页面：创建、编辑、删除、启停、手动执行和执行日志查看。
- Alembic 迁移入口、后端枚举约束、统一测试 fixture、部署文档和 Postman Collection。

当前定时任务仍是“管理闭环”而非“调度闭环”：任务可以被创建和手动执行，但不会由后台调度器按计划自动触发。对于真实测试环境，管理员仍需要手动巡检设备状态、手动执行健康检查命令、手动确认周期性任务是否失败。

Wave 18 的目标是补齐轻量后台调度能力，让平台可以自动执行计划任务，并把执行结果纳入现有日志、诊断和前端可观测入口。

## 2. 目标

Wave 18 完成后，系统应达到以下状态：

1. 启用的定时任务可以由后端后台调度器按计划自动触发。
2. 定时任务支持 `interval:` 和基础 `cron:` 表达式的稳定解析、校验和下次执行时间展示。
3. 自动执行复用现有批量更新/SSH 执行能力，不重复实现远程命令逻辑。
4. 每次自动触发都有执行记录、操作日志和失败原因，便于追溯。
5. 前端定时任务页面展示调度状态、下次执行时间、最近执行结果和最近错误。
6. 系统诊断页展示调度器运行状态，便于部署后确认后台自动化是否生效。
7. 后端测试覆盖调度触发、禁用任务不触发、失败记录和表达式校验。
8. 文档和 Postman 补充自动调度验收路径。

## 3. 非目标

本轮不实现以下内容：

- 不实现多节点分布式调度、leader election 或外部任务队列。
- 不引入复杂工作流编排、任务依赖 DAG、审批流或回滚编排。
- 不实现多用户 RBAC 和项目级权限。
- 不实现邮件、Webhook、短信等外部告警通知。
- 不实现完整报表中心或趋势分析。
- 不把数据库切换到 PostgreSQL；仍以 SQLite 单实例部署为主。
- 不要求后台任务在后端进程停止期间补偿执行所有错过的历史触发。
- 不改写现有批量更新任务模型，只做必要的轻量关联。

## 4. 功能需求

### 4.1 后台调度器

后端需要新增一个轻量后台调度器，在应用启动时随 FastAPI 生命周期启动，在应用关闭时停止。

要求：

- 调度器只在后端主进程中运行。
- 默认启用，但可通过环境变量关闭：

```text
SCHEDULER_ENABLED=true|false
SCHEDULER_POLL_INTERVAL_SECONDS=30
```

- 调度器按固定间隔扫描启用的定时任务。
- 到期任务自动执行，并更新任务的最近执行信息。
- 禁用任务不得自动触发。
- 同一个任务在上一次执行尚未完成时不得重复并发触发。
- 调度器异常不得导致 API 服务崩溃，但必须记录错误并能在诊断接口看到。

### 4.2 调度表达式

现有 `schedule` 字段已经要求以 `cron:` 或 `interval:` 开头。Wave 18 需要让它具备真实语义。

最低支持：

- `interval:60`：每 60 秒执行一次。
- `interval:300`：每 300 秒执行一次。
- `cron:*/5 * * * *`：每 5 分钟执行一次。
- `cron:0 2 * * *`：每天 02:00 执行一次。

要求：

- 表达式在创建和更新时校验。
- 非法表达式返回 `422`，错误信息应说明是调度表达式非法。
- 后端可计算 `next_run_at`。
- 前端展示 `next_run_at`，为空时显示“未计划”或“已禁用”。
- 文档列出支持范围，不承诺完整 cron 方言。

### 4.3 定时任务执行记录

需要新增定时任务执行记录，避免只依赖操作日志。

建议新增表：`scheduled_task_runs`

字段建议：

- `id`
- `scheduled_task_id`
- `trigger_type`：`manual` / `scheduled`
- `status`：`running` / `success` / `failed` / `skipped`
- `started_at`
- `finished_at`
- `duration_ms`
- `output_summary`
- `error_message`
- `created_update_task_id`：如果本次触发创建了批量更新任务，则记录其 ID。

要求：

- 手动执行也应写入执行记录。
- 自动执行失败时应保存失败原因。
- 执行记录列表按时间倒序返回。
- API 响应不包含明文凭据、Token 或私钥。
- 新表必须通过 Alembic 迁移创建。

### 4.4 自动执行语义

当前定时任务已有 `task_type`、`command`、`target_filter`、`enabled` 字段。

Wave 18 自动执行应遵循：

- `task_type=command`：根据 `target_filter` 创建或复用一次批量更新任务，并执行。
- 默认执行模式建议为 `dry_run`，除非定时任务显式配置真实 SSH 模式。
- 如果支持真实 SSH 自动执行，必须有明确字段控制，不能隐式把所有定时任务当成真实命令执行。
- 自动触发应记录操作日志，action 建议：
  - `scheduled_task.run.scheduled`
  - `scheduled_task.run.manual`
  - `scheduled_task.run.failed`
- 若目标设备为空，应记录 `skipped`，不视为系统异常。
- 若设备缺少端口或凭据，应记录 warning 或 failed，不能静默跳过。

### 4.5 定时任务 Schema 扩展

建议为定时任务增加以下字段：

- `execution_mode`：`dry_run` / `ssh_command`
- `failure_strategy`：`continue` / `pause` / `rollback`
- `concurrency_limit`
- `last_run_at`
- `last_status`
- `last_error`
- `next_run_at`
- `running`

要求：

- 现有前端和 API 兼容，不破坏已有创建请求。
- 新字段提供默认值。
- 旧数据库通过 Alembic 迁移补齐列。
- 响应字段命名保持 snake_case。

### 4.6 API 扩展

建议新增或扩展接口：

```http
GET /api/scheduled-tasks/{id}/runs
POST /api/scheduled-tasks/{id}/run-now
GET /api/scheduler/status
```

说明：

- `GET /api/scheduled-tasks/{id}/runs`：查看定时任务执行记录。
- `POST /api/scheduled-tasks/{id}/run-now`：可以作为现有 `execute` 的语义化别名；如果保留旧接口，旧接口继续可用。
- `GET /api/scheduler/status`：返回调度器是否启用、是否运行、最近扫描时间、最近错误和 poll interval。

要求：

- 所有接口需要登录鉴权。
- `GET /api/diagnostics/config` 可复用或嵌入调度器摘要。
- Postman Collection 增加对应验收请求。

### 4.7 前端定时任务页面增强

前端现有“定时任务”页面需要展示自动调度状态。

要求：

- 列表展示：
  - 是否启用
  - 调度表达式
  - 下次执行时间
  - 最近执行时间
  - 最近状态
  - 最近错误摘要
- 详情或日志区展示执行记录。
- 手动执行按钮继续可用，并明确显示“立即执行”产生一条 `manual` 记录。
- 支持刷新调度器状态。
- 调度器未启用时，页面显示中文提醒。
- 所有文案继续使用中文。

### 4.8 系统诊断增强

系统诊断页需要增加调度器摘要：

- 调度器是否启用。
- 调度器是否运行。
- 扫描间隔。
- 最近扫描时间。
- 最近错误。
- 启用任务数。
- 到期但未执行任务数或失败任务数。

要求：

- 不返回敏感信息。
- 若调度器关闭，应给出清晰提示。
- 若调度器有最近错误，应在诊断页显示 warning。

### 4.9 测试要求

后端测试：

- 调度表达式解析：
  - 合法 `interval`
  - 合法 `cron`
  - 非法表达式返回 `422`
- 调度器扫描：
  - 到期启用任务触发执行
  - 禁用任务不触发
  - 正在运行任务不重复触发
  - 失败任务写入 run 记录和操作日志
- API：
  - `GET /api/scheduled-tasks/{id}/runs`
  - `GET /api/scheduler/status`
  - 手动执行写入 run 记录
- Alembic：
  - 新表和新列迁移可从空库升级到 head。

前端测试：

- 定时任务列表展示 `next_run_at`、`last_status`。
- 调度器关闭时显示提醒。
- 执行记录能加载和展示失败原因。
- 手动执行后刷新执行记录。

验证命令：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave18'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

### 4.10 文档与部署

需要更新：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/postman/edge-platform.postman_collection.json`

文档必须说明：

- 调度器默认是否启用。
- 如何关闭调度器。
- 支持的调度表达式。
- SQLite 单实例部署下的限制。
- 后端多进程部署时的风险：如果用多个 worker，可能重复调度；本轮建议单 worker。
- 自动执行真实 SSH 命令前的风险提示。

## 5. 数据模型建议

### 5.1 scheduled_tasks 扩展字段

建议新增：

```text
execution_mode
failure_strategy
concurrency_limit
last_run_at
last_status
last_error
next_run_at
running
```

### 5.2 scheduled_task_runs 新表

建议新增：

```text
id
scheduled_task_id
trigger_type
status
started_at
finished_at
duration_ms
output_summary
error_message
created_update_task_id
created_at
```

## 6. 安全要求

- 自动调度不得绕过现有认证边界之外的敏感保护。
- 执行记录和日志不得保存明文设备密码、Token、私钥或 passphrase。
- 真实 SSH 自动执行必须显式配置 `execution_mode=ssh_command`。
- 前端必须在创建真实 SSH 定时任务时给出中文风险提示。
- 诊断接口只展示调度器摘要，不展示命令正文中的潜在敏感内容。

## 7. 兼容性要求

- 现有 `POST /api/scheduled-tasks/{id}/execute` 继续可用。
- 已有定时任务旧数据升级后默认：
  - `execution_mode=dry_run`
  - `failure_strategy=continue`
  - `concurrency_limit=5`
  - `running=false`
- 旧前端请求不传新字段时仍可创建任务。
- 旧 Postman 请求仍可运行。

## 8. 验收标准

Wave 18 只有在以下条件全部满足后才算完成：

- 后端启动后调度器状态可通过 API 或诊断页看到。
- 创建 `interval:60` 的启用任务后，调度器能在到期后自动产生执行记录。
- 禁用任务不会自动产生执行记录。
- 手动执行和自动执行都能在执行记录中区分 `manual` / `scheduled`。
- 失败执行能显示失败原因，且不会导致调度器停止。
- 新增 Alembic 迁移可从空库升级到 head。
- 后端全量 pytest 通过。
- 前端 Vitest 通过。
- 前端 build 通过。
- README、API、部署文档和 Postman 同步更新。

## 9. 待确认问题

1. 调度器实现是否允许引入 `APScheduler`，还是优先使用项目内轻量轮询实现？
2. 自动执行真实 SSH 定时任务是否本轮开放，还是本轮仅允许自动 `dry_run`，真实 SSH 仍只允许手动执行？
3. 是否保留现有 `POST /api/scheduled-tasks/{id}/execute` 作为主接口，并新增 `run-now` 作为别名？
4. 调度表达式是否只支持 `interval:N` 和 5 位 cron，暂不支持秒级 cron、时区配置和复杂表达式？
5. 本轮是否继续提交并推送到 `origin/main`，还是只生成需求和执行计划，等实现完成后统一提交？

## 10. 已确认决策

根据用户确认，本轮冻结以下决策：

1. 允许引入 `APScheduler`，优先使用其后台调度能力实现本轮自动调度。
2. 本轮开放真实 SSH 定时任务自动执行，但必须显式选择 `execution_mode=ssh_command` 并在前端二次确认。
3. 保留旧 `execute` 接口，新增 `run-now` 作为更清晰的别名。
4. 仅支持 `interval:N` 和 5 位 cron。
5. 需求确认后生成执行计划，计划批准后实现，测试完成后统一提交并推送到 `origin/main`。
