# Wave 10 执行计划：真实批量 SSH 命令执行与任务结果追踪

## 运行时信息

- Vibe run id: `20260514T074832Z-bf1cad81`
- 阶段: `xl_plan`
- 需求文档: `docs/requirements/2026-05-14-wave-10-requirement-document-for-remote-terminal-platform-after.md`
- 计划收据: `outputs/runtime/vibe-sessions/20260514T074832Z-bf1cad81/execution-plan-receipt.json`
- 计划状态: 待审批

## 冻结实现决策

为减少服务器测试风险，Wave 10 采用以下实现决策：

1. 批量 SSH 本轮采用顺序执行，不做并发。保留 `concurrency_limit` 字段但暂不用于真实并发。
2. 全部设备失败时，任务总状态沿用现有 `partial_failed`，不新增 `failed`，避免扩大状态迁移范围。
3. `dry_run` 单设备状态使用 `skipped`，摘要写入“演练模式，未连接设备”。
4. `execution_mode` 默认值为 `dry_run`，只有用户显式选择 `ssh_command` 才真实连接设备。
5. 真实 SSH 执行优先使用设备级密码；设备缺少密码时回退到环境变量 `SSH_PASSWORD`。
6. `rollback` 策略本轮不执行真实回滚，失败时只记录“回滚命令暂未自动执行”。

## 执行波次

### Wave 10.0：基线复核与测试入口确认

目标：在改代码前确认现有批量任务、SSH 服务和前端任务 UI 的接入点。

执行项：

- 复核 `backend/app/services/update_task_service.py` 的创建、执行、取消和目标筛选逻辑。
- 复核 `backend/app/models/update_task.py` 与 `backend/app/schemas/update_task.py` 的字段和响应结构。
- 复核 `backend/app/services/ssh_service.py` 的 `execute` 和 `_connect`，确认凭据来源改造点。
- 复核 `backend/app/websockets/update_tasks.py` 的快照返回逻辑。
- 复核 `frontend/src/App.vue` 和 `frontend/src/api/platform.ts` 的批量任务表单、列表、执行入口。

验证：

- 不修改业务逻辑，只记录影响范围。

### Wave 10.1：后端模型、Schema 与旧库迁移

目标：为真实执行结果补齐数据结构。

后端改动：

- `UpdateTask` 新增 `execution_mode`，默认 `dry_run`。
- `UpdateTaskDevice` 新增：
  - `exit_code`
  - `stdout_summary`
  - `stderr_summary`
  - `error_message`
- `UpdateTaskCreate` 新增 `execution_mode` 校验：`dry_run|ssh_command`。
- `UpdateTaskDeviceRead` 和 `UpdateTaskRead` 返回新增字段。
- SQLite 自动迁移新增列，并为旧任务补默认 `execution_mode='dry_run'`。

测试：

- 旧 SQLite 表迁移后包含新增列。
- 旧任务读取时 `execution_mode` 为 `dry_run`。
- API 响应包含执行结果字段，但不包含敏感凭据。

### Wave 10.2：SSH 服务凭据优先级改造

目标：让真实执行使用 Wave 9 的设备级凭据。

后端改动：

- `SshService._connect` 优先读取：
  - `device.ssh_user`
  - `device.ssh_password_encrypted`
- 当设备级密码为空时，回退 `settings.ssh_password`。
- 保留现有私钥环境变量回退能力。
- 缺少 SSH 端口、缺少可用凭据、认证失败、连接失败均返回中文错误。
- 错误消息中不得出现密码、Token、私钥内容或 passphrase。

测试：

- fake/mock paramiko 校验设备级密码优先。
- 设备无密码时回退环境变量密码。
- 认证失败返回 `RemoteAuthenticationError` 中文原因。
- 缺少 SSH 端口返回中文错误。

### Wave 10.3：批量任务执行器从模拟升级为 dry-run / SSH 执行

目标：替换现有模拟执行逻辑，保留安全默认模式。

后端改动：

- `UpdateTaskService.execute` 根据 `execution_mode` 分流：
  - `dry_run`: 不调用 SSH，设备行标记 `skipped`，写入演练摘要。
  - `ssh_command`: 顺序调用 `SshService.execute`。
- 真实执行时逐设备记录：
  - `running`
  - `started_at`
  - `finished_at`
  - `exit_code`
  - `stdout_summary`
  - `stderr_summary`
  - `error_message`
  - `output_summary`
- stdout/stderr 截断保存，建议每类最多 4000 字符。
- exit_code 为 0 标记 `success`，非 0 标记 `failed`。
- 捕获认证失败、连接失败和未知异常，统一写入中文 `error_message`。
- `continue` 策略：失败后继续。
- `pause` 策略：首个失败后，剩余 pending 设备标记 `skipped`。
- `rollback` 策略：保留创建校验，不执行真实回滚，失败时记录说明。
- 任务最终状态：
  - 全部真实成功：`completed`
  - dry-run：`completed`
  - 任意失败或 pause 跳过：`partial_failed`

测试：

- dry-run 不调用 SSH 服务。
- SSH 成功执行记录 stdout 和 exit_code 0。
- SSH 非 0 退出记录 stderr 和失败状态。
- 认证失败记录中文错误且不泄露密码。
- continue 策略继续执行后续设备。
- pause 策略跳过后续设备。
- 任务不会长期停留在 `running`。

### Wave 10.4：WebSocket 快照与操作日志增强

目标：任务执行结果可以被前端和 Postman 查询闭环消费。

后端改动：

- `GET /api/update-tasks/{id}` 和列表接口返回新增字段。
- `/api/ws/update-tasks/{id}` 快照包含 `execution_mode` 和每设备执行结果字段。
- 执行接口记录 `update_task.execute` 日志 detail：
  - execution_mode
  - total
  - success
  - failed
  - skipped
- 日志 detail 不记录完整 stdout/stderr，不记录敏感凭据。

测试：

- WebSocket 快照包含新增字段。
- 操作日志包含统计信息。
- 日志不包含 SSH 密码。

### Wave 10.5：前端中文 UI 与任务结果展示

目标：管理员可以安全创建真实执行任务并查看结果。

前端改动：

- `frontend/src/api/platform.ts` 补齐类型：
  - `execution_mode`
  - `exit_code`
  - `stdout_summary`
  - `stderr_summary`
  - `error_message`
- 批量任务创建表单新增执行模式控件：
  - 默认 `演练模式`
  - 可选 `真实 SSH 执行`
- 选择真实 SSH 执行时显示中文风险提示。
- 默认示例命令使用只读命令，优先 `hostname`。
- 任务列表或任务详情中展示每设备：
  - 状态
  - 退出码
  - stdout 摘要
  - stderr 摘要
  - 错误原因
- 执行后刷新任务并读取 WebSocket 快照。
- 502/503/504 继续显示中文代理错误，不清空登录状态。

测试：

- 默认创建 payload 包含 `execution_mode: "dry_run"`。
- 选择真实执行后 payload 包含 `execution_mode: "ssh_command"`。
- 设备结果表展示 stdout/stderr/exit_code/error_message。
- 502 场景不触发退出登录。

### Wave 10.6：Postman、README 与 API 文档

目标：服务器验收路径可复制。

文档和资产：

- 更新 `docs/postman/edge-platform.postman_collection.json`：
  - 创建 dry-run 批量任务。
  - 创建 `hostname` SSH 命令任务。
  - 执行任务。
  - 查询任务详情。
  - 保留登录后自动 token 注入。
- 更新 `docs/api.md`：
  - `UpdateTaskCreate.execution_mode`
  - `UpdateTaskDeviceRead` 新字段。
  - 执行结果示例。
  - WebSocket 快照字段。
- 更新 `README.md`：
  - Wave 10 能力说明。
  - 真实 SSH 批量执行验收步骤。
  - 默认凭据仍是临时明文存储的安全提醒。
- 必要时更新 `docs/deployment.md`：
  - 真实 SSH 执行前的服务器检查项。

验证：

- Postman JSON 可解析。
- 文档中的接口路径和字段与代码一致。

### Wave 10.7：回归、验收与收口

目标：完成自动化验证和可执行交付。

后端验证：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
py -3.12 -m pytest tests --basetemp C:\01_work\02_program\远程终端平台\.pytest-tmp
```

前端验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

静态检查：

```powershell
git diff --check
```

手工验收清单：

- 登录平台。
- 确认已有 frps 导入设备，SSH 用户为 `ztl`。
- 创建 dry-run 批量任务，确认不会连接设备。
- 创建 `ssh_command` 任务，命令为 `hostname`。
- 对一台可达设备执行成功，看到 exit_code 0 和 stdout。
- 对一台不可达设备执行失败，看到中文失败原因。
- 混合成功和失败设备时，`continue` 策略继续执行后续设备。
- Postman 按登录、创建任务、执行任务、查询详情流程通过。

## 文件影响范围

预计修改：

- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/models/update_task.py`
- `backend/app/schemas/update_task.py`
- `backend/app/services/ssh_service.py`
- `backend/app/services/update_task_service.py`
- `backend/app/routers/update_tasks.py`
- `backend/app/websockets/update_tasks.py`
- `backend/tests/test_database_migrations.py`
- `backend/tests/test_wave4_update_tasks_api.py`
- `backend/tests/test_wave8_remote_websockets.py`
- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`
- `docs/api.md`
- `docs/deployment.md`
- `README.md`
- `docs/postman/edge-platform.postman_collection.json`

预计新增：

- 可选：`backend/tests/test_wave10_update_task_ssh_execution.py`

## 风险与控制

- 真实 SSH 命令有副作用风险：默认 `dry_run`，真实执行必须显式选择。
- 同步请求执行可能阻塞较久：本轮顺序执行并设置 SSH 超时，文档说明限制。
- 输出过大风险：stdout/stderr 截断保存。
- 凭据泄露风险：响应、日志和错误消息均不得包含密码。
- 旧库兼容风险：先写迁移测试，再改模型。
- 前端误操作风险：真实执行模式显示中文风险提示，示例只使用只读命令。

## 审批条件

批准本计划后，进入 Wave 10 实现阶段。实现阶段必须按上述波次推进，先完成后端迁移与测试，再接入前端和文档，最后运行后端全量测试、前端测试、前端构建和 `git diff --check`。
