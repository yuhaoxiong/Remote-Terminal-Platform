# Wave 18 执行计划：定时任务真实调度与运维自动化闭环

> 阶段：`xl_plan`  
> 状态：已完成，测试通过并进入统一提交推送  
> 冻结需求：`docs/requirements/2026-05-21-wave-18-scheduled-task-executor-and-ops-automation.md`

## 1. 执行目标

Wave 18 将现有“定时任务 API 管理闭环”推进为“后台自动调度闭环”。

完成后应达到：

- 后端引入 `APScheduler`，随应用生命周期启动和停止调度器。
- 支持 `interval:N` 与 5 位 cron 表达式，并计算 `next_run_at`。
- 定时任务可自动触发 dry-run 或真实 SSH 批量任务。
- 自动执行和手动执行都有独立执行记录。
- 前端定时任务页展示调度器状态、下次执行、最近结果和执行记录。
- 系统诊断页展示调度器摘要。
- Alembic 新增定时任务调度字段和执行记录表。
- README、API、部署文档和 Postman Collection 同步更新。
- 测试完成后统一提交并推送到 `origin/main`。

## 2. 冻结决策

1. 允许引入 `APScheduler`，优先使用其后台调度能力。
2. 本轮开放真实 SSH 定时任务自动执行，但必须显式选择 `execution_mode=ssh_command`。
3. 保留现有 `POST /api/scheduled-tasks/{id}/execute`，新增 `POST /api/scheduled-tasks/{id}/run-now` 作为别名。
4. 调度表达式仅支持 `interval:N` 和 5 位 cron，不支持秒级 cron、时区配置和复杂 cron 方言。
5. 需求、计划和实现测试完成后统一提交并推送。

## 3. 总体执行策略

本轮涉及数据库、后台线程、批量任务复用、前端 UI 和部署文档。执行顺序应先固化数据和执行语义，再接入后台调度，最后接前端与文档。

推荐顺序：

1. 审计现有定时任务、批量更新任务、生命周期和测试模式。
2. 新增依赖、配置、枚举和 Alembic 迁移。
3. 扩展模型、Schema、Service 和 API。
4. 实现 `APScheduler` 生命周期与调度器状态。
5. 将自动执行接入现有 `UpdateTaskService`。
6. 扩展前端定时任务页和系统诊断页。
7. 更新文档/Postman，跑完整验证。

任何阶段连续 3 次失败，应停止并报告失败点、根因和替代方案。

## 4. 工作拆分

### Step 1：基线审计与影响面确认

阅读并确认当前模式：

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/migrations.py`
- `backend/app/models/scheduled_task.py`
- `backend/app/models/update_task.py`
- `backend/app/schemas/scheduled_task.py`
- `backend/app/routers/scheduled_tasks.py`
- `backend/app/services/scheduled_task_service.py`
- `backend/app/services/update_task_service.py`
- `backend/app/services/operation_log.py`
- `backend/app/routers/diagnostics.py`
- `backend/tests/conftest.py`
- `backend/tests/test_wave6_scheduled_tasks_api.py`
- `frontend/src/api/platform.ts`
- `frontend/src/components/ScheduledTaskPanel.vue`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`

需要确认：

- 当前手动执行如何写操作日志。
- 当前定时任务是否已经复用批量任务，或只是写摘要日志。
- 当前 `UpdateTaskService.execute` 对真实 SSH 和 dry-run 的入口约束。
- FastAPI 应用生命周期当前是否有 lifespan/startup/shutdown 模式。
- 前端定时任务组件是否适合继续扩展，还是需要拆出执行记录子组件。

产出：

- 不单独生成审计文档。
- 若发现需求与当前模型冲突，在实现前调整计划并说明。

### Step 2：依赖、配置和枚举准备

后端依赖：

- 在 `backend/requirements.txt` 增加 `APScheduler` 固定版本。

配置新增：

```text
SCHEDULER_ENABLED=true
SCHEDULER_POLL_INTERVAL_SECONDS=30
```

枚举建议新增或扩展：

- `ScheduledTaskRunTriggerType`
- `ScheduledTaskRunStatus`

要求：

- 默认启用调度器。
- 测试环境可显式关闭调度器，避免后台线程影响 API 单元测试。
- 配置出现在系统诊断摘要中，但不暴露敏感内容。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_health.py tests/test_diagnostics_api.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave18-config'
```

### Step 3：Alembic 迁移与模型扩展

新增迁移脚本：

- `backend/alembic/versions/<revision>_wave18_scheduled_task_runs.py`

迁移内容：

- `scheduled_tasks` 新增字段：
  - `execution_mode`
  - `failure_strategy`
  - `concurrency_limit`
  - `last_run_at`
  - `last_status`
  - `last_error`
  - `next_run_at`
  - `running`
- 新增表 `scheduled_task_runs`：
  - `id`
  - `scheduled_task_id`
  - `trigger_type`
  - `status`
  - `started_at`
  - `finished_at`
  - `duration_ms`
  - `output_summary`
  - `error_message`
  - `created_update_task_id`
  - `created_at`

模型更新：

- `backend/app/models/scheduled_task.py`
- 必要时更新 Alembic env 的 metadata import。
- 保留 SQLite 兼容路径；若当前 `_ensure_sqlite_schema` 仍负责历史补列，本轮只补必要兜底，不用扩大。

要求：

- 空库 `alembic upgrade head` 可创建新表和新列。
- 旧库升级后旧定时任务默认：
  - `execution_mode=dry_run`
  - `failure_strategy=continue`
  - `concurrency_limit=5`
  - `running=false`
- 不丢失已有定时任务。

阶段测试：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_migrations.py tests/test_database_migrations.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave18-migrations'
```

### Step 4：调度表达式解析

新增轻量解析模块，建议：

- `backend/app/services/schedule_parser.py`

支持：

- `interval:N`
  - `N` 必须为正整数。
  - 建议最小值 10 或 30 秒，避免误配置导致高频执行；若采用最小值，需要文档说明。
- 5 位 cron：
  - minute
  - hour
  - day
  - month
  - day_of_week

实现方式：

- 使用 `APScheduler.triggers.interval.IntervalTrigger`
- 使用 `APScheduler.triggers.cron.CronTrigger`
- 不支持秒级 cron。
- 不支持 timezone 参数，本轮使用后端本地时区或默认时区。

要求：

- 创建/更新定时任务时校验表达式。
- 非法表达式返回 `422`。
- Service 层可计算下一次执行时间。
- 测试覆盖合法 `interval`、合法 cron、非法表达式。

### Step 5：Service 层执行记录和手动执行改造

扩展：

- `backend/app/services/scheduled_task_service.py`

新增能力：

- `list_runs(session, task_id, offset, limit)`
- `run_now(session, task_id, user_id, trigger_type)`
- `mark_running`
- `finish_run_success`
- `finish_run_failed`
- `skip_run`
- `calculate_next_run_at`

手动执行改造：

- 现有 `execute` 接口必须写入 `scheduled_task_runs`。
- 新增 `run-now` 调用同一 service 方法。
- 操作日志继续记录，action 区分：
  - `scheduled_task.run.manual`
  - `scheduled_task.run.scheduled`
  - `scheduled_task.run.failed`

与批量任务复用：

- 对 `task_type=command` 的定时任务，创建一次 `UpdateTaskCreate`，字段来自定时任务：
  - `name`
  - `command`
  - `target_filter`
  - `execution_mode`
  - `failure_strategy`
  - `concurrency_limit`
- 调用 `UpdateTaskService.create` 后执行。
- 记录 `created_update_task_id`。
- dry-run 和真实 SSH 都走现有 `UpdateTaskService.execute`，避免重复 SSH 逻辑。

要求：

- 目标设备为空时写 `skipped`。
- 执行异常写 `failed` 和 `error_message`。
- 同一任务 `running=true` 时再次触发应 `skipped` 或返回明确冲突，自动调度不得并发执行。
- API 响应不包含明文凭据。

阶段测试：

- 手动执行产生 run 记录。
- `run-now` 与旧 `execute` 行为一致。
- 失败时 run 记录有错误原因。
- 正在运行时不重复触发。

### Step 6：API 扩展

更新 router：

- `backend/app/routers/scheduled_tasks.py`
- 新增 `backend/app/routers/scheduler.py` 或在现有 router 下新增状态接口。

新增接口：

```http
GET /api/scheduled-tasks/{id}/runs
POST /api/scheduled-tasks/{id}/run-now
GET /api/scheduler/status
```

Schema 更新：

- `ScheduledTaskRead` 增加调度字段。
- 新增 `ScheduledTaskRunRead`
- 新增 `ScheduledTaskRunListResponse`
- 新增 `SchedulerStatusResponse`

要求：

- 旧 `POST /api/scheduled-tasks/{id}/execute` 保持。
- 所有接口使用现有认证。
- 状态码与已有风格一致。
- `GET /api/scheduler/status` 返回：
  - `enabled`
  - `running`
  - `poll_interval_seconds`
  - `last_scan_at`
  - `last_error`
  - `job_count`

阶段测试：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave6_scheduled_tasks_api.py tests/test_wave18_scheduler.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave18-api'
```

### Step 7：APScheduler 生命周期与自动触发

新增调度器服务，建议：

- `backend/app/services/scheduler_service.py`

职责：

- 创建 `BackgroundScheduler`。
- 按 `SCHEDULER_POLL_INTERVAL_SECONDS` 注册扫描任务。
- 启动/停止调度器。
- 提供状态快照。
- 捕获扫描异常并记录 `last_error`。

接入位置：

- `backend/app/main.py`
- 若当前 `create_app` 无 lifespan，可使用 FastAPI startup/shutdown event 或 lifespan。

扫描逻辑：

1. 打开独立数据库 session。
2. 查询 `enabled=true` 且 `next_run_at <= now` 的任务。
3. 跳过 `running=true` 的任务。
4. 对到期任务调用 `ScheduledTaskService.run_now(..., trigger_type="scheduled")`。
5. 执行后计算并更新下一次 `next_run_at`。

要求：

- 测试环境默认可关闭调度器。
- 调度器错误不影响 REST API。
- 多 worker 风险只在文档说明，本轮不做分布式锁。
- 自动真实 SSH 执行复用已有 fake SSH 测试模式。

阶段测试：

- 直接测试 scheduler service 的扫描函数，不依赖真实等待 60 秒。
- 启用任务到期后产生 run 记录。
- 禁用任务不触发。
- 异常被记录到 scheduler status。

### Step 8：诊断接口扩展

后端：

- `backend/app/schemas/diagnostics.py`
- `backend/app/routers/diagnostics.py`

新增 `scheduler` 摘要：

- `enabled`
- `running`
- `poll_interval_seconds`
- `last_scan_at`
- `last_error`
- `enabled_task_count`
- `failed_run_count`

前端系统诊断页：

- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`

展示：

- 调度器状态卡片。
- 最近错误 warning。
- 启用任务数和失败执行数。

要求：

- 不展示命令正文。
- 不展示凭据或 token。
- 调度器关闭时显示中文提示。

### Step 9：前端定时任务页面增强

更新：

- `frontend/src/api/platform.ts`
- `frontend/src/components/ScheduledTaskPanel.vue`
- 必要时新增 `frontend/src/components/ScheduledTaskRunPanel.vue`
- `frontend/src/__tests__/app.spec.ts`

API 封装：

- `getSchedulerStatus`
- `listScheduledTaskRuns`
- `runScheduledTaskNow`

UI 增强：

- 列表展示：
  - `next_run_at`
  - `last_run_at`
  - `last_status`
  - `last_error`
  - `execution_mode`
- 创建/编辑表单新增：
  - 执行模式
  - 失败策略
  - 并发数
- 真实 SSH 模式二次确认。
- 执行记录区展示：
  - 触发方式
  - 状态
  - 开始/结束时间
  - 输出摘要
  - 错误原因
  - 创建的批量任务 ID
- 调度器关闭时显示提醒。

测试：

- 展示 next/last 状态。
- 真实 SSH 模式创建时出现确认。
- 手动执行后刷新 runs。
- 调度器关闭提示。

### Step 10：文档和 Postman 更新

更新：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/postman/edge-platform.postman_collection.json`

内容：

- APScheduler 依赖和调度器默认启用。
- `SCHEDULER_ENABLED` 和 `SCHEDULER_POLL_INTERVAL_SECONDS`。
- 支持的表达式：
  - `interval:N`
  - 5 位 cron
- 单 worker 部署建议。
- 自动真实 SSH 定时任务风险。
- 新 API：
  - runs
  - run-now
  - scheduler status
- Postman 增加 Wave 18 分组。

验证：

```powershell
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman-json-ok')"
```

### Step 11：最终验证、清理、提交推送

最终命令：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave18'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build

cd C:\01_work\02_program\远程终端平台
git diff --check
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman-json-ok')"
```

清理：

- 删除 `.pytest-tmp-wave18*` 临时目录。
- 确认无无关文件。

提交：

- 在所有测试通过后一次性提交。
- 推送到 `origin/main`。

建议提交信息：

```text
Implement Wave 18 scheduled task automation
```

## 5. 风险与控制

### 风险 1：APScheduler 后台线程影响测试稳定性

控制：

- 测试 settings 默认关闭调度器。
- 调度器扫描逻辑可直接单元测试，不依赖真实等待。

### 风险 2：多 worker 部署重复调度

控制：

- 文档明确本轮仅支持单 worker。
- 运行中任务用 `running` 标记避免同进程内重复。
- 不承诺多节点互斥。

### 风险 3：真实 SSH 自动任务误执行

控制：

- 默认 `execution_mode=dry_run`。
- 真实 SSH 必须显式选择。
- 前端创建/编辑真实 SSH 定时任务时二次确认。
- 文档和诊断说明风险。

### 风险 4：SQLite 时间和并发边界

控制：

- 扫描任务短事务。
- 同一任务运行中不重复触发。
- 执行记录先写 running，再更新 success/failed。

### 风险 5：执行记录和操作日志重复或语义混乱

控制：

- 执行记录负责任务运行事实。
- 操作日志负责用户/系统操作审计。
- action 命名区分 manual/scheduled/failed。

## 6. 验收清单

- [x] `APScheduler` 依赖加入并可安装。
- [x] Alembic 新迁移可创建新列和 `scheduled_task_runs`。
- [x] `interval:N` 和 5 位 cron 校验通过。
- [x] 非法 schedule 返回 `422`。
- [x] 手动执行写 run 记录。
- [x] `run-now` 别名可用。
- [x] 自动调度可触发到期任务。
- [x] 禁用任务不触发。
- [x] `running=true` 任务不重复触发。
- [x] dry-run 自动任务能创建/执行批量任务。
- [x] `ssh_command` 自动任务必须显式配置。
- [x] `GET /api/scheduler/status` 可用。
- [x] `GET /api/scheduled-tasks/{id}/runs` 可用。
- [x] 诊断接口展示调度器摘要。
- [x] 前端定时任务页展示 next/last/runs。
- [x] 前端系统诊断页展示调度器状态。
- [x] Postman JSON 可解析。
- [x] 后端全量 pytest 通过。
- [x] 前端 Vitest 通过。
- [x] 前端 build 通过。
- [x] `git diff --check` 通过。
- [x] 测试完成后提交并推送。
