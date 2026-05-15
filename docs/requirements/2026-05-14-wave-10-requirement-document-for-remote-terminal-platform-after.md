# Wave 10 开发需求：真实批量 SSH 命令执行与任务结果追踪

## 运行时信息

- Vibe run id: `20260514T074832Z-bf1cad81`
- 当前阶段: `requirement_doc`
- 下一阶段: 用户批准需求后进入 `xl_plan`
- 需求状态: 待审批
- 基线提交: `3a2f992 Implement Wave 9 diagnostics and frps sync`

## 背景

平台已完成设备管理、分组、监控、操作日志、批量更新任务模型、定时任务、真实 Web SSH/VNC WebSocket 基础能力、SFTP 文件后端、frps Dashboard 导入与可重复同步、设备级 SSH 凭据、Postman 验收集合和 Nginx 单域名部署文档。

Wave 9 明确把“真实批量 SSH 命令执行”顺延到后续 Wave，并已经补齐执行所需的基础数据：

- 设备已有 `ssh_user`、`ssh_auth_type`、凭据配置状态和默认密码写入能力。
- frps 导入的新设备默认具备 SSH 端口和默认凭据。
- 后端已有 `SshService.execute(device, command, timeout)` 可复用。
- 批量任务已有 `update_tasks`、`update_task_devices`、执行入口、取消入口和 WebSocket 快照。
- 当前批量任务执行仍是模拟逻辑，会把目标设备直接标记为 `success`。

Wave 10 的目标是把批量任务从“模拟执行”升级为“可选择 dry-run 或真实 SSH 命令执行”，让管理员可以对已导入的 frps 设备执行安全的只读测试命令，并看到每台设备的真实执行结果。

## 目标

Wave 10 交付后，管理员应能：

1. 创建批量任务时选择执行模式：`dry_run` 或 `ssh_command`。
2. 使用设备级 SSH 凭据对目标设备逐台执行真实 SSH 命令。
3. 查看每台设备的执行状态、开始/结束时间、退出码、stdout/stderr 摘要和失败原因。
4. 通过任务详情和 WebSocket 快照看到真实执行进度，而不是模拟完成结果。
5. 在命令为空、设备缺少 SSH 端口、缺少凭据、认证失败、连接超时、命令非 0 退出等场景看到中文错误。
6. 通过 Postman 和中文文档完成服务器上的批量 SSH 验收。

## 范围

### 1. 执行模式

批量任务必须支持执行模式字段，建议命名为 `execution_mode`：

- `dry_run`: 只冻结目标设备和执行计划，不连接设备，不执行命令。
- `ssh_command`: 对每台目标设备通过 SSH 执行任务命令。

兼容要求：

- 旧任务如果没有 `execution_mode` 字段，应按 `dry_run` 或现有兼容策略安全迁移，不能在旧数据库启动时自动执行真实命令。
- API 创建任务时未传 `execution_mode` 时，默认应为 `dry_run`，避免误执行真实命令。
- 前端必须显式展示执行模式，真实执行需要用户明确选择。

### 2. 任务设备结果字段

`update_task_devices` 需要补齐真实执行结果字段，至少包括：

- `exit_code`: 命令退出码，未执行或连接失败时为空。
- `stdout_summary`: stdout 摘要，限制长度，避免大输出撑爆数据库和前端。
- `stderr_summary`: stderr 摘要，限制长度。
- `error_message`: 中文失败原因，不能包含密码、Token、私钥内容。
- `started_at`: 单设备开始时间。
- `finished_at`: 单设备结束时间。

现有 `output_summary` 可以保留用于列表摘要，但不得替代结构化 stdout/stderr/exit_code。

状态约定：

- `pending`: 等待执行。
- `running`: 正在执行。
- `success`: SSH 命令退出码为 0。
- `failed`: 连接、认证、执行异常或退出码非 0。
- `skipped`: 因失败策略或 dry-run 跳过真实执行。
- `canceled`: 被取消。

### 3. SSH 凭据解析

真实执行必须优先使用设备级凭据：

1. `device.ssh_user`
2. `device.ssh_password_encrypted` 本轮仍按 Wave 9 约定视为明文密码。
3. 后续加密存储未纳入本轮。

回退规则：

- 如果设备没有密码，允许回退到服务端环境变量 `SSH_PASSWORD`。
- 私钥执行可保留现有环境变量 `SSH_KEY_FILENAME` / `SSH_KEY_PASSPHRASE` 作为兼容能力，但本轮验收以密码模式为主。
- API 响应、日志、错误消息不得泄露明文密码、私钥路径内容、passphrase 或完整 Token。

### 4. 批量执行行为

`POST /api/update-tasks/{task_id}/execute` 应按任务模式执行：

- `dry_run`: 不连接设备，目标设备标记为 `skipped` 或等效计划状态，摘要说明“演练模式，未连接设备”。
- `ssh_command`: 按目标设备顺序执行 SSH 命令。

失败策略：

- 兼容现有 `continue`、`pause`、`rollback` 字段。
- `continue`: 单设备失败后继续执行后续设备。
- `pause`: 首个失败后，后续未执行设备标记为 `skipped`，任务最终为 `partial_failed`。
- `rollback`: 本轮不实现真实回滚；如果选择 `rollback`，应保留现有创建校验，并在真实执行失败时记录“回滚命令暂未自动执行”或将真实回滚顺延到后续 Wave。

任务最终状态：

- 全部成功: `completed`。
- 部分成功或部分失败: `partial_failed`。
- 全部失败: `failed` 或 `partial_failed`，需在计划阶段确认沿用现有状态枚举还是新增 `failed`。
- 被取消: `canceled`。

### 5. 并发与资源控制

本轮可以先采用顺序执行，或者按现有 `concurrency_limit` 做有限并发；计划阶段需明确选择。

最低要求：

- 不得无限并发连接设备。
- 每个 SSH 执行必须设置超时。
- 每次连接必须关闭 SSH client。
- stdout/stderr 必须截断保存，建议默认每类最多 4000 字符。
- 后端异常不得导致任务长期停留在 `running`。

### 6. 前端交互

前端批量任务区域必须补齐真实执行可见性：

- 创建任务表单新增执行模式选择，默认 `dry_run`。
- 选择 `ssh_command` 时显示中文风险提示，建议默认命令使用只读命令，如 `hostname`、`whoami`、`uptime`。
- 任务详情或列表中展示每台设备的状态、退出码、输出摘要和错误原因。
- 点击执行后刷新任务详情，并通过现有 WebSocket 快照展示最新状态。
- 所有新增文案必须为中文。

前端不得：

- 默认执行破坏性命令。
- 在页面中显示 SSH 密码。
- 把 502/503/504 当作登录失效处理。

### 7. API 与 Postman

需要更新 API 文档和 Postman 集合：

- `POST /api/update-tasks` 示例新增 `execution_mode`。
- `GET /api/update-tasks/{id}` 响应示例新增设备级执行结果字段。
- Postman 集合新增或更新批量任务分组，至少覆盖：
  - 创建 dry-run 任务。
  - 创建真实 SSH 命令任务，命令建议 `hostname`。
  - 执行任务。
  - 查询任务详情。
  - 查看任务 WebSocket 的手工说明。

Postman 中不得内置真实服务器密码。继续使用变量和登录后的 `access_token`。

### 8. 操作日志

每次执行任务必须记录操作日志：

- `update_task.execute`
- 任务 ID
- 执行模式
- 目标设备数量
- 成功数量
- 失败数量
- 跳过数量

日志 detail 不得包含完整命令输出和敏感凭据。

## 非目标

Wave 10 不实现以下内容：

- 不实现真正的回滚编排。
- 不实现脚本文件上传后执行。
- 不实现命令模板市场、审批流、多用户 RBAC。
- 不实现后台调度器自动定时触发批量任务。
- 不实现凭据加密存储；仍沿用 Wave 9 的临时明文存储约定。
- 不实现复杂危险命令策略引擎；本轮只做基础非空、长度和中文提示。
- 不实现跨进程任务队列或持久后台 worker；如果执行保持同步请求模型，必须在文档中说明限制。

## 数据与接口约束

- 优先复用 `UpdateTask`、`UpdateTaskDevice`、`Device`、`SshService` 和现有 `update_tasks` 路由。
- SQLite 旧库必须自动兼容迁移新增列。
- `UpdateTaskCreate.failure_strategy` 现有取值为 `continue|pause|rollback`，不得破坏已有测试。
- WebSocket 路径继续使用 `/api/ws/update-tasks/{task_id}?token=<access_token>`。
- WebSocket 本轮可以继续发送快照，但快照内容必须包含真实执行后的设备结果字段。
- `SshService` 需要优先读取设备级密码，并保留环境变量凭据回退。

## 测试与验证要求

后端自动化测试至少覆盖：

- `dry_run` 任务不会调用 SSH 服务，设备行记录为跳过或演练状态。
- `ssh_command` 成功执行：fake SSH 返回 exit_code 0、stdout，设备状态为 `success`。
- `ssh_command` 认证失败：设备状态为 `failed`，错误为中文且不泄露密码。
- `ssh_command` 非 0 退出：设备状态为 `failed`，记录 exit_code 和 stderr 摘要。
- `continue` 策略下，一台失败后继续执行后续设备。
- `pause` 策略下，首台失败后跳过后续设备。
- 旧 SQLite 自动迁移新增列。
- WebSocket 快照包含新增设备结果字段。
- API 响应不包含 `ssh_password` 或敏感字段。

前端自动化测试至少覆盖：

- 创建任务时默认执行模式为 `dry_run`。
- 选择 `ssh_command` 后提交 payload 包含 `execution_mode: "ssh_command"`。
- 任务设备结果表展示状态、退出码、stdout/stderr 摘要和中文错误。
- 执行失败或 502 提示为中文，并不清空登录状态。

手工验收至少覆盖：

- 使用已导入 frps 设备和默认用户 `ztl`，执行只读命令 `hostname`。
- 对一台不可达设备执行任务，看到中文失败原因。
- 混合成功和失败设备时，`continue` 策略继续执行后续设备。
- Postman 按“登录 -> 创建设备或选择已有设备 -> 创建任务 -> 执行任务 -> 查询详情”完成验收。

建议验证命令：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
py -3.12 -m pytest tests --basetemp C:\01_work\02_program\远程终端平台\.pytest-tmp

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

## 交付物

- Wave 10 执行计划文档。
- 后端真实 SSH 批量执行实现。
- 数据库兼容迁移。
- 前端中文执行模式与任务结果展示。
- Postman Collection 更新。
- README / API / 部署文档更新。
- 自动化测试与手工验收记录。
- Vibe phase cleanup receipt。

## 已确认决策

1. Wave 10 主线聚焦真实批量 SSH 命令执行。
2. 设备来源优先使用已导入的 frps 设备。
3. SSH 用户默认沿用 Wave 9：`ztl`。
4. 本轮密码仍按 Wave 9 约定使用数据库中保存的默认值 `123456`，后续再做加密。
5. 真实执行的默认安全命令建议使用 `hostname`、`whoami`、`uptime` 等只读命令。
6. Postman、README、API 文档继续入库维护。
7. 前端和错误提示继续使用中文。

## 待确认问题

执行计划前暂无阻塞性问题。计划阶段需要在不改变需求目标的前提下明确以下实现选择：

1. 本轮采用顺序执行，还是按 `concurrency_limit` 做有限并发。
2. 全部设备失败时任务总状态使用现有 `partial_failed`，还是新增 `failed`。
3. `dry_run` 的单设备状态使用 `skipped`，还是新增更明确的 `planned`。

## 审批条件

批准本需求后，下一阶段应生成 Wave 10 执行计划，并把以上需求拆解为可验证的实现步骤。未批准前不进入实现阶段。
