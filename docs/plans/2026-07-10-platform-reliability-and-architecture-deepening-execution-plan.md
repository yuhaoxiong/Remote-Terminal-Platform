# 后续开发路线执行计划：契约修复、任务可靠性与架构深化

> 阶段：`roadmap_execution_plan`
> 状态：已批准，阶段 A 已完成，阶段 B 未启动
> 审查基线：2026-07-10 项目架构审查
> 当前基线：后端 109 个测试通过；前端 38 个测试、lint、typecheck、build 通过

## 1. 执行目标

本计划承接 2026-07-10 项目审查结论。平台当前功能面已经完整，后续开发不再以增加页面和接口数量为主，而是优先解决真实契约错误、远程任务可靠性、外部投递一致性、生产发布安全和模块深度问题。

全部阶段完成后应达到：

- 设备 SSH/VNC 端口编辑与后端真实行为一致，端口池占用、释放和冲突规则有集成测试保护。
- 生产部署只允许发布已通过 CI 的确定 Git revision，部署脚本、备份、健康检查和回退入口纳入版本控制。
- `concurrency_limit` 对真实 SSH 批量任务生效，任务执行不再在一个长数据库事务中串行完成全部网络 I/O。
- 批量任务具备明确的排队、运行、取消、进程中断和人工重试语义。
- 告警事件持久化与 Webhook 投递解耦，Webhook 故障不阻塞设备、指标和任务业务事务。
- Local/SFTP 文件后端成为同一 seam 上的两个 adapter，前端树形和表格式文件浏览共享同一业务编排。
- 前后端契约漂移可以被自动化检查发现，App 级测试不再承担所有领域细节。
- 生产模式拒绝默认密钥、默认管理员密码、默认设备密码和不安全 SSH 主机密钥策略。
- 当前架构、领域词汇和关键决策有独立文档，不再依赖历史 Wave 计划反推现状。
- 后端全量测试反馈时间较当前 175 秒至少降低 50%，同时保持测试隔离和覆盖范围。

## 2. 范围与非目标

### 2.1 本计划范围

1. P0 契约与发布安全修复。
2. 远程任务执行 module 深化。
3. 告警通知持久化投递。
4. 文件管理与前端领域 module 深化。
5. 生产安全、测试效率、文档和可观测性收口。

### 2.2 非目标

- 不在本计划内新增新的业务页面。
- 不立即引入 Redis、Celery、Kafka 或 Kubernetes。
- 不立即迁移 PostgreSQL；SQLite 继续作为单实例部署数据库。
- 不自动重放进程中断时正在执行的 SSH 命令，避免非幂等命令重复执行。
- 不在只有 Webhook 一个通知类型时提前抽象多通知通道框架。
- 不强制引入边缘 Agent；保持当前纯 SSH/frp 管控模式。
- 不一次性重写全部 router、store 或 panel。
- 不改变现有 admin/operator 权限矩阵，除非具体步骤明确要求。

## 3. 冻结决策

1. 执行顺序固定为：P0 契约和部署 → 任务执行器 → 告警投递 → 文件与前端深化 → 生产治理。
2. 每个阶段独立提交、独立验证；后一个阶段不得与前一个阶段的未完成修改混合。
3. 设备创建未提供端口或端口为空时继续自动分配，保持现有行为。
4. 设备更新未提供端口字段表示不修改；显式传 `null` 表示释放并清空端口；传整数表示保留或切换到指定端口。
5. 切换端口必须在同一事务中先验证/预留新端口，再释放旧端口，冲突时完整回滚。
6. `POST /api/update-tasks/{id}/execute` 路径和响应模型保持兼容；执行动作改为持久化排队，返回任务当前状态，具体 HTTP 状态码在实现前由契约测试冻结。
7. 新增 `queued` 状态；worker 领取后转为 `running`，完成后进入 `completed|partial_failed|failed|canceled` 等终态。
8. worker 只部署在单个后端进程中；多 worker/多实例运行前必须另行设计分布式领取机制。
9. 进程重启发现遗留 `running` 任务时标记为中断/部分失败并要求人工重试，不自动重新执行远程命令。
10. `concurrency_limit` 限制同一批量任务内同时执行的设备数量，不等同于全局并发上限；全局上限另设安全配置。
11. `cancel` 只保证阻止尚未开始的设备；已经进入 Paramiko 调用的设备按超时或连接关闭结束，不能宣称强制回滚。
12. 告警通知复用现有 `alert_notification_deliveries` 作为持久化投递箱，不新增泛化事件总线。
13. 告警业务事务只创建 delivery 记录；后台投递 worker 负责 HTTP、重试和结果更新。
14. 文件管理保留一个领域 interface，Local 与 SFTP 是两个真实 adapter；树形和表格式 UI 是两个展示 adapter。
15. 生产部署必须绑定确定 Git SHA，不允许服务器仅执行 `pull main` 后发布不可追溯内容。
16. 引入 `development|production` 运行模式；生产模式对不安全默认配置执行 fail-fast。
17. PostgreSQL 迁移触发条件为：需要多实例/高可用、出现持续 SQLite 写锁问题或任务写入吞吐超过单实例能力；未满足前不迁移。

## 4. 总体执行策略

采用 tracer-bullet 方式逐步深化：

1. 先用设备端口编辑这条真实失败链打通“前端表单 → TypeScript DTO → FastAPI schema → 端口池 → 数据库 → API 集成测试”。
2. 再把部署流程绑定 CI 和 Git SHA，避免后续较大改动在失败状态下进入生产。
3. 任务执行先固化状态机和失败测试，再引入 worker、有限并发和短事务。
4. 告警投递复用现有 delivery 表，先移除同步 HTTP，再补扫描、领取、重试和诊断。
5. 文件管理先补共享契约测试，再拆 Local/SFTP adapter 和前端共享编排。
6. 最后收口安全模式、测试性能、可观测性和当前架构文档。

每一步均遵守：红灯测试 → 最小实现 → 目标测试 → 相邻测试 → 全量验证。连续 3 次同类失败时停止，报告失败点、已尝试方案、当前判断和所需输入。

## 5. 阶段 A：P0 契约修复与发布安全

预计周期：1–3 个工作日。

### Step A1：冻结设备端口写入契约

先补失败测试，不先改实现。

后端测试范围：

- `backend/tests/test_device_api.py`
- `backend/tests/test_port_pool.py`

至少覆盖：

- 创建设备未提供端口时自动分配 SSH/VNC 端口。
- 更新设备未提供端口字段时保持原端口。
- 更新为指定空闲端口后设备记录和端口池同时变化。
- 更新为已占用端口返回 `409`，设备和端口池均不变化。
- 显式传 `null` 释放端口并清空设备字段。
- 同时修改 SSH/VNC 时任一冲突导致整体回滚。
- 删除设备继续释放当前端口。

前端测试范围：

- `frontend/src/__tests__/app.spec.ts`
- 建议新增 `frontend/src/components/__tests__/DevicesPanel.spec.ts`

至少覆盖：

- 编辑表单提交的 DTO 含合法 `ssh_port`/`vnc_port`。
- 创建时空端口遵守自动分配语义。
- 后端冲突错误显示为局部中文提示。
- 测试不能只断言 mock 被调用，还要校验请求 DTO 和返回值回填。

### Step A2：实现端口池一致性

预计修改：

- `backend/app/schemas/device.py`
- `backend/app/services/device_service.py`
- `backend/app/services/port_pool.py`
- 必要时 `backend/app/models/port_pool.py`
- `frontend/src/api/domains/devices.ts`
- `frontend/src/components/DevicesPanel.vue`

实现要求：

- Pydantic schema 明确声明端口类型和 `1..65535` 范围。
- create 与 update 能区分字段未提供和显式 `null`。
- 端口变更逻辑集中在设备写入 module 内，不放回 router。
- 端口池记录与设备字段在同一 session/事务内更新。
- 端口冲突使用现有冲突错误映射，不新增模糊的 `500`。
- API 响应继续返回最终生效端口。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest backend\tests\test_device_api.py backend\tests\test_port_pool.py --basetemp '.pytest-tmp\roadmap-device-ports' -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run src/components/__tests__/DevicesPanel.spec.ts src/__tests__/app.spec.ts
npm.cmd run typecheck
```

### Step A3：部署必须等待 CI 成功

预计修改/新增：

- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `scripts/deploy/deploy.sh`
- `docs/deployment.md`
- `docs/openclaw-deployment-runbook.md`

推荐实现：

1. 保留独立 deploy workflow，但只通过成功完成的 CI workflow 触发；或合并为单 workflow，并让 deploy job `needs: [backend, frontend]`。
2. deploy 仅对 `main` 且 CI 成功的 revision 执行。
3. 将当前服务器侧 `deploy.sh` 的权威版本放入仓库。
4. deploy 接收目标 Git SHA，服务器 fetch 后检出该 SHA，不重新解析 `origin/main`。
5. 部署前记录当前 revision，备份 SQLite。
6. 构建、迁移、systemd 重启和 Nginx 检查失败时退出非零。
7. 健康检查至少确认 HTTP 200 且响应中的 `status=ok`、`database=ok`。
8. 回退入口接受上一 revision，并在数据库迁移不可逆时明确阻止自动降级。

安全要求：

- 不在 workflow 日志打印服务器密钥、数据库 URL 或应用密钥。
- SSH action 固定版本；后续依赖升级单独审查。
- GitHub Environment 可增加 production 审批，但不是本阶段强制项。

### Step A4：同步当前事实文档

至少修正：

- README 中 `FILE_BACKEND` 默认值与代码不一致。
- 原架构文档仍描述“单用户认证”，而当前已实现 admin/operator 多用户。
- README 最近测试数量更新为当前实际基线。
- 部署文档明确生产默认配置禁用计划。

### 阶段 A 完成标准

- [x] 真实 API 可修改、释放 SSH/VNC 端口。
- [x] 端口冲突不会产生部分提交。
- [x] 前后端类型均声明端口字段。
- [x] 新增真实后端集成测试，不只依赖前端 mock。
- [x] CI 失败时部署不会启动。
- [x] 部署绑定确定 Git SHA。
- [x] 权威 `deploy.sh` 已进入版本控制。
- [x] README 和部署文档默认值与实现一致。

## 6. 阶段 B：远程任务执行 module 深化

预计周期：1–2 周。该阶段是本计划风险最高的部分，必须独立分支/提交推进。

### Step B1：固化任务状态机

先定义并测试状态转换：

```text
pending -> queued -> running -> completed
                            -> partial_failed
                            -> failed
queued/running -> canceled
running + process restart -> interrupted/partial_failed -> manual retry
```

预计修改：

- `backend/app/enums.py`
- `backend/app/models/update_task.py`
- `backend/app/schemas/update_task.py`
- `backend/app/services/update_task_service.py`
- `backend/alembic/versions/<revision>_task_execution_state.py`

如现有表不足，迁移可增加：

- `queued_at`
- `started_at`
- `heartbeat_at`
- `finished_at`
- `worker_id`
- `cancel_requested_at`
- `interruption_reason`

要求：

- 非法状态转换抛出明确领域错误。
- 重复 execute 保持幂等，不重复创建单设备记录。
- 已完成任务不能再次原地执行；失败设备重试继续创建新任务。
- WebSocket 快照兼容新增中间状态。

### Step B2：建立执行 coordinator

建议新增：

- `backend/app/services/task_execution_coordinator.py`
- `backend/app/services/task_execution_worker.py`

职责：

- API 事务只校验并将任务转为 `queued`。
- coordinator 扫描和领取 queued 任务。
- worker 加载目标设备执行快照，关闭读取 session 后执行 SSH。
- 单设备结果使用短事务写回。
- 任务汇总状态在独立短事务中完成。
- 应用 lifespan 启动/停止 coordinator。

领取要求：

- 单实例 SQLite 下使用条件更新或等价原子操作，避免同一进程重复领取。
- 应用诊断明确显示 coordinator 是否启用、worker 标识、队列长度和遗留 running 数量。
- 检测到多 worker 部署时给出告警；本阶段不宣称支持分布式执行。

### Step B3：让并发限制真正生效

实现原则：

- 使用受控 `ThreadPoolExecutor` 或等价线程池承载阻塞 Paramiko I/O。
- 每个任务并发数为 `min(task.concurrency_limit, global_limit, pending_device_count)`。
- 全局配置建议新增 `TASK_EXECUTION_GLOBAL_CONCURRENCY`，默认保守值。
- 每个设备仍有独立 SSH 超时。
- `failure_strategy=pause` 在首个失败被观察到后不再提交新设备，但已在执行的设备允许结束。
- `failure_strategy=rollback` 本阶段仍不自动执行回滚命令；UI/API/文档必须明确该事实，或将取值重命名/废弃另立计划。

测试要求：

- 并发峰值不超过限制。
- `concurrency_limit=1` 保持顺序。
- 多设备执行时间证明并发实际生效，但测试避免依赖脆弱的绝对毫秒值。
- 某设备异常不会丢失其他设备结果。
- 取消后未开始设备进入 canceled/skipped 语义。
- 进程中断恢复测试不重新执行命令。

### Step B4：接入定时任务与 WebSocket

预计修改：

- `backend/app/services/scheduled_task_service.py`
- `backend/app/services/scheduler_service.py`
- `backend/app/websockets/update_tasks.py`
- `backend/app/routers/update_tasks.py`
- `frontend/src/stores/updates.ts`
- `frontend/src/components/UpdatesPanel.vue`
- `frontend/src/components/ScheduledTaskPanel.vue`

要求：

- 手动任务和定时任务均通过同一执行 interface 排队。
- APScheduler 不直接执行整批 SSH，只负责生成/排队任务。
- WebSocket 从数据库状态生成快照，不依赖仅存在于内存的进度。
- 前端展示 queued/running/canceling/interrupted 等状态。
- 页面刷新或后端短暂重启后可继续查询任务最终状态。

### 阶段 B 验证

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest backend\tests\test_wave10_update_task_ssh_execution.py backend\tests\test_wave16_update_task_safety.py backend\tests\test_wave18_scheduler.py backend\tests\test_wave8_remote_websockets.py --basetemp '.pytest-tmp\roadmap-task-execution' -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run typecheck
```

### 阶段 B 完成标准

- [ ] `concurrency_limit` 对真实 SSH 生效。
- [ ] API 请求不持有覆盖整批 SSH 执行的数据库事务。
- [ ] worker 领取和状态转换有测试。
- [ ] cancel 语义与实现一致。
- [ ] 进程中断不会自动重复远程命令。
- [ ] 定时任务与手动任务复用同一执行 interface。
- [ ] WebSocket 和刷新后查询均能获得持久化进度。
- [ ] 单实例部署约束已写入诊断和部署文档。

## 7. 阶段 C：告警通知持久化投递

预计周期：约 1 周。

### Step C1：将 delivery 表变成真正的投递箱

预计修改：

- `backend/app/services/alert_service.py`
- `backend/app/services/alert_notification_service.py`
- `backend/app/models/alert_notification.py`
- 必要时新增 Alembic 迁移。

行为调整：

- `record_event` 只匹配策略并写入 pending delivery。
- 不在设备、指标、任务业务事务中调用 `httpx.post`。
- delivery 唯一约束继续防止同一事件重复创建。
- 通知配置解密失败只影响 delivery，不回滚告警生命周期。

### Step C2：新增投递 worker 与 HTTP adapter seam

建议新增：

- `backend/app/services/alert_delivery_worker.py`
- `backend/app/services/webhook_delivery_adapter.py`

要求：

- worker 扫描 pending 和到期 retrying delivery。
- 领取、HTTP 调用、结果写回分别使用短事务。
- HTTP adapter 支持测试 fake；不再要求测试 monkeypatch module 全局 `httpx.post`。
- 保留当前退避规则和最大重试次数。
- 明确响应摘要截断和敏感头不落日志。
- 应用停止时不强行等待超过单次 Webhook timeout。

### Step C3：诊断、管理和恢复能力

扩展：

- 待投递数量。
- 最早待投递时间。
- 最近成功/失败时间。
- worker 运行状态和最近错误。
- 管理员手工重试继续走同一领取/投递 implementation。

测试范围：

- `backend/tests/test_wave19_alerts.py`
- `backend/tests/test_wave20_alert_notifications.py`
- `backend/tests/test_wave20_alert_notifications_api.py`
- `backend/tests/test_diagnostics_api.py`

### 阶段 C 完成标准

- [ ] 告警业务事务中没有同步 Webhook I/O。
- [ ] Webhook 不可达时告警仍正常创建/恢复。
- [ ] delivery 可自动重试、手动重试并持久化结果。
- [ ] HTTP adapter 有 fake 测试 seam。
- [ ] 诊断页可观察积压和 worker 状态。

## 8. 阶段 D：文件管理与前端领域 module 深化

预计周期：1–2 周。

### Step D1：后端文件 adapter 契约测试

先定义 Local/SFTP 必须共享的行为：

- 列目录。
- 上传与覆盖。
- 下载。
- 删除文件和目录。
- 创建目录。
- 重命名。
- 根路径、相对路径、`..` 和不存在路径错误。
- 连接关闭与异常归一化。

建议新增参数化契约测试：

- `backend/tests/test_file_backend_contract.py`

### Step D2：深化后端文件管理 module

建议结构：

```text
backend/app/services/device_files.py          # 领域 interface 与统一路径/错误语义
backend/app/adapters/local_file_backend.py    # Local adapter
backend/app/adapters/sftp_file_backend.py     # SFTP adapter
```

要求：

- router 仍只调用一个设备文件管理 interface。
- backend 选择只发生一次，不在六个方法内重复 `if file_backend`。
- 统一路径安全规则留在 deep module；adapter 只处理存储差异。
- 兼容现有 API 路径、响应和中文错误。

### Step D3：合并前端两套文件编排

现有入口：

- `frontend/src/components/FileTreePanel.vue`
- `frontend/src/components/DeviceFilePanel.vue`
- `frontend/src/components/RemotePanel.vue`
- `frontend/src/components/FilesPanel.vue`

建议新增：

- `frontend/src/composables/useDeviceFileBrowser.ts`，或同等领域 store/module。

共享内容：

- 当前路径和路径规范化。
- 加载/刷新。
- 上传后刷新并重新定位。
- 下载。
- 删除、建目录、重命名。
- 局部错误和 loading 状态。

树形 UI 和表格式 UI 只保留展示、选择和各自交互差异。

### Step D4：收紧前端领域依赖

采用增量方式：

1. 文件领域调用改为直接依赖 `api/domains/files`。
2. 设备领域调用改为直接依赖 `api/domains/devices`。
3. 新代码禁止继续从宽泛 `api/platform.ts` 导入领域函数。
4. 保留 barrel 兼容现有调用，待迁移完成后再删除。
5. 评估从 FastAPI OpenAPI 生成 TypeScript 类型；若引入生成工具，生成结果必须可复现并由 CI 检查无漂移。

### Step D5：测试重新分层

新增或补齐：

- `DeviceFilePanel.spec.ts`
- `DevicesPanel.spec.ts`
- `ScheduledTaskPanel.spec.ts`
- `AlertCenterPanel.spec.ts`
- `SystemSettingsPanel.spec.ts`

调整原则：

- `app.spec.ts` 只保留登录、权限、路由、跨页入口和全局错误。
- 领域表单、DTO、列表状态和局部错误归对应 panel/module 测试。
- WebSocket 通过 adapter/fake 测试，不继续扩散浏览器全局 mock。

### 阶段 D 完成标准

- [ ] Local/SFTP 通过同一组契约测试。
- [ ] 后端文件选择逻辑只存在一个 seam。
- [ ] 两种前端文件 UI 共享同一业务编排。
- [ ] 设备、文件领域新增代码不再依赖宽泛 barrel。
- [ ] App 集成测试减少领域细节 mock。
- [ ] 前后端契约漂移可被自动化检查发现。

## 9. 阶段 E：生产治理、测试效率与文档收口

预计周期：约 1 周，可与阶段 D 后半段并行，但提交仍保持独立。

### Step E1：生产模式 fail-fast

预计修改：

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/routers/diagnostics.py`
- `docs/deployment.md`

建议新增：

```text
DEPLOYMENT_MODE=development|production
```

production 启动校验至少拒绝：

- `JWT_SECRET_KEY=change-me-in-production`。
- 默认管理员密码 `admin`。
- 默认设备 SSH 密码 `123456`。
- 未配置 `CREDENTIAL_ENCRYPTION_KEY`。
- `SSH_HOST_KEY_POLICY=auto_add`。

开发模式继续允许启动，但诊断页保留风险提示。

### Step E2：优化后端测试反馈时间

当前证据：109 个测试约 175 秒，多数慢点来自每个测试初始化 SQLite、运行迁移并写入约 1000 条端口池记录。

优先措施：

1. `backend/tests/conftest.py` 为测试设置更小但足够的 SSH/VNC 端口范围。
2. 避免同一 client fixture 路径重复调用 `init_db` 与 `create_app` 初始化。
3. 将迁移正确性保留在专用迁移测试；普通 service 测试可复用已建 schema 的隔离数据库模板。
4. 继续保证每个测试数据隔离，不用共享可变数据库换速度。
5. CI 输出 `--durations`，持续观察最慢用例。

验收：

- 同一开发机全量后端测试时间相对 175 秒降低至少 50%。
- 所有 109 个既有测试和新增测试继续通过。
- 迁移测试仍从空库和旧库运行，不被测试模板绕过。

### Step E3：后端静态质量门槛

当前后端 CI 只有 pytest。建议评估并引入：

- Ruff：格式、未使用导入和基础错误。
- 类型检查：先对新增核心 module 开启，再逐步扩大；不要求一次清零全部旧代码。
- 依赖安全扫描：固定周期运行，不在普通本地循环中阻塞。

新增门槛必须先以 warning/限定目录方式落地，清理基线后再升级为 error。

### Step E4：当前架构与决策文档

建议新增：

- `CONTEXT.md`：设备、远程会话、批量任务、定时任务、告警、投递、端口池等领域词汇。
- `docs/current-architecture.md`：当前进程、数据库、任务 worker、通知 worker、前端 module 和部署拓扑。
- `docs/adr/0001-agentless-edge-management.md`
- `docs/adr/0002-sqlite-single-instance-execution.md`
- `docs/adr/0003-interrupted-remote-command-semantics.md`
- `docs/adr/0004-alert-delivery-outbox.md`

同时归档或标明：

- `docs/01-需求与架构设计文档.md` 是初始设计，不是完整当前事实。
- `docs/frontend-refactor-plan.md` 是迁移历史。
- Wave 需求/计划用于追溯，不作为当前架构入口。

### Step E5：可观测性与恢复演练

最低交付：

- 结构化日志包含 task_id、device_id、delivery_id、user_id、request_id，敏感字段除外。
- 诊断接口展示任务队列长度、遗留任务、通知积压和 worker 状态。
- SQLite 备份执行恢复演练，不只验证备份文件存在。
- 部署后记录 revision、迁移 revision、健康结果和回退 revision。
- 对 50–200 台设备的 dry-run/模拟 SSH 执行进行负载测试，记录队列和 SQLite 写入表现。

### 阶段 E 完成标准

- [ ] production 模式拒绝不安全默认配置。
- [ ] 后端测试时间降低至少 50%。
- [ ] CI 可定位最慢测试。
- [ ] 当前架构和关键 ADR 可供新维护者直接阅读。
- [ ] 任务、投递和部署有最小可观测性。
- [ ] 完成一次可记录的 SQLite 恢复演练。

## 10. 文件级影响预估

| 范围 | 主要文件 | 变化类型 |
| --- | --- | --- |
| 设备契约 | `schemas/device.py`、`device_service.py`、`port_pool.py`、`devices.ts`、`DevicesPanel.vue` | 修复与测试 |
| 发布 | `.github/workflows/*`、`scripts/deploy/deploy.sh`、部署文档 | CI/CD 治理 |
| 任务执行 | update task model/schema/service、coordinator/worker、scheduler、WebSocket | 核心架构变化 |
| 告警投递 | alert service、notification service、delivery worker/adapter | 外部 I/O 解耦 |
| 文件管理 | file service、Local/SFTP adapter、两个前端文件 panel | module 深化 |
| 前端契约 | API domain、领域 panel spec、可选 OpenAPI 生成 | 测试面收紧 |
| 生产安全 | config、main、diagnostics、deployment docs | fail-fast |
| 测试治理 | backend conftest、CI、前端 component specs | 反馈提速 |
| 文档 | `CONTEXT.md`、current architecture、ADR、README | 当前事实入口 |

## 11. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 端口切换造成端口池与设备记录不一致 | 单事务、冲突回滚测试、双端口原子测试 |
| 异步执行改变现有 API 时序 | 先冻结契约测试，保持路径和响应模型，前端适配中间状态 |
| SSH 命令被重复执行 | worker 领取幂等；进程中断不自动重放；人工创建重试任务 |
| 有限并发压垮服务器或 frps | 任务级与全局双重上限，默认保守值，压测后调整 |
| pause/cancel 在并发场景语义模糊 | 明确“停止提交新设备，不保证中断已运行设备”并写测试 |
| SQLite 多线程写竞争 | 网络 I/O 脱离 session，结果短事务串行/受控写入，监控锁错误 |
| 多 worker 重复调度 | 本阶段明确单 worker，启动诊断检测和部署文档限制 |
| Webhook 投递积压 | 持久化状态、退避、积压诊断、管理员手工重试 |
| adapter 抽取演变为无收益 pass-through | 只有 Local/SFTP 两个真实变化源建立 seam；契约测试验证 leverage |
| 前端拆分造成更多浅 module | 以共享用例和状态为 module，不按文件行数机械拆分 |
| production fail-fast 阻断现有服务器 | 先在诊断中预警，部署配置补齐后再启用 production 模式 |
| 测试提速破坏隔离 | 保留独立临时数据库/事务回滚，迁移测试不复用模板 |
| 数据库迁移不可逆影响回退 | 迁移前备份；破坏性迁移单独批准；部署脚本识别不可降级版本 |

## 12. 全量验证矩阵

每阶段结束至少运行受影响测试；阶段 E 和最终收尾运行全量矩阵。

### 后端

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest backend\tests --basetemp '.pytest-tmp\roadmap-all' -p no:cacheprovider --durations=20
```

### 前端

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test -- --run
npm.cmd run build
```

### 数据库与部署资产

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest backend\tests\test_migrations.py backend\tests\test_database_migrations.py --basetemp '.pytest-tmp\roadmap-migrations' -p no:cacheprovider

git diff --check
git status --short
```

另外必须完成：

- Postman Collection JSON 可解析。
- `deploy.sh` 静态检查和测试环境 dry-run。
- 备份/恢复演练记录。
- 浏览器验证设备端口编辑、任务排队/取消、通知积压和文件双入口。

## 13. 建议提交策略

每个提交只包含一个可验证主题：

1. `fix device remote port contract and pool consistency`
2. `gate production deploy on verified revision`
3. `add durable update task execution coordinator`
4. `enforce bounded concurrent ssh execution`
5. `move alert webhook delivery to persistent worker`
6. `deepen local and sftp file adapters`
7. `share frontend device file orchestration`
8. `add production configuration guardrails`
9. `speed up backend test database setup`
10. `document current architecture and decisions`

要求：

- 每个提交前运行对应目标测试。
- 阶段结束运行相邻测试。
- 全部阶段结束运行全量验证矩阵。
- 未经明确要求不推送；推送前确认工作区无无关改动。

## 14. 总体验收清单

### P0 正确性与发布

- [x] 设备端口编辑、清空、冲突和回滚均有真实 API 测试。
- [x] 前后端 DTO 与后端 schema 一致。
- [x] 失败 CI 不能触发生产部署。
- [x] 部署产物绑定确定 Git SHA，支持记录和回退。

### 任务可靠性

- [ ] `concurrency_limit` 实际生效。
- [ ] 任务状态机覆盖排队、执行、取消、中断和终态。
- [ ] SSH I/O 不占用整批数据库长事务。
- [ ] 进程中断不自动重复执行远程命令。
- [ ] 手动任务、定时任务和 WebSocket 使用同一持久化状态。

### 告警投递

- [ ] 告警生命周期与 HTTP 投递解耦。
- [ ] pending/retrying delivery 自动处理。
- [ ] Webhook adapter 可替换为测试 fake。
- [ ] 积压、失败和 worker 状态可观察。

### Module 深化

- [ ] Local/SFTP 两个 adapter 通过共享契约测试。
- [ ] 树形/表格式文件 UI 共享业务编排。
- [ ] 新领域代码不依赖宽泛平台 barrel。
- [ ] App 测试回归跨页职责，领域测试靠近所有权 module。

### 生产治理

- [ ] production 模式拒绝默认危险配置。
- [ ] 后端测试反馈时间降低至少 50%。
- [ ] README、当前架构和 ADR 与实现一致。
- [ ] SQLite 备份恢复演练成功。
- [ ] 后端全量 pytest 通过。
- [ ] 前端 lint、typecheck、Vitest、build 通过。
- [ ] `git diff --check` 通过。

## 15. 执行入口

阶段 A 已完成并通过全量验证。下一次继续执行时从阶段 B 开始，先固化远程任务状态机；不得把阶段 C/D/E 混入同一提交。阶段 A 已交付：

1. 修复设备端口真实写入。
2. 补端口池原子性集成测试。
3. 让部署等待 CI 并绑定 Git SHA。
4. 同步 README 和部署文档。

该最小范围可以独立上线，并为后续任务执行器改造建立可信发布基础。
