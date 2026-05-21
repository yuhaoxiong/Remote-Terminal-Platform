# Wave 16 执行计划：批量任务安全增强与设备选择器

> 阶段：`xl_plan`  
> 状态：已确认，进入实现  
> 冻结需求：`docs/requirements/2026-05-19-wave-16-batch-task-safety-and-device-selector.md`

## 1. 执行目标

本轮增强批量 SSH 任务的安全性和可控性，让管理员在真实执行前能明确目标设备、命令内容和风险，执行后能快速排查失败设备并导出摘要结果。

完成后应达到：

- 批量任务创建前可通过后端预览接口查看目标设备。
- 前端提供设备选择器，支持筛选和手动勾选设备。
- 真实 SSH 任务创建和执行前显示具体中文风险确认。
- 命令模板支持列表、创建、编辑、套用和删除。
- 任务详情增强为可排查的设备结果表。
- 失败设备可通过“以失败设备新建任务”快速重试。
- 任务结果支持 CSV 导出，只导出摘要和错误原因。
- 前端接入现有更新任务 WebSocket 快照，形成实时入口。
- 文档、Postman、后端测试、前端测试和构建同步完成。

## 2. 冻结决策

1. 失败设备重试采用“以失败设备新建任务”，不修改历史任务执行结果，不新增直接重跑旧任务语义。
2. 命令模板本轮需要完整编辑能力：列表、创建、编辑、套用、删除。
3. WebSocket 先接入现有快照并在前端形成实时入口；不强行扩展持续事件总线。
4. 目标预览接口纳入本轮，保证预览和任务创建复用同一套目标匹配逻辑。
5. 任务结果导出只导出摘要和错误原因，不导出完整终端输出。

## 3. 工作拆分

### Step 1：基线审计与失败优先测试

阅读并记录当前批量任务链路：

- `backend/app/routers/update_tasks.py`
- `backend/app/services/update_task_service.py`
- `backend/app/schemas/update_task.py`
- `backend/app/models/update_task.py`
- `backend/app/websockets/update_tasks.py`
- `frontend/src/App.vue`
- `frontend/src/api/platform.ts`
- `frontend/src/__tests__/app.spec.ts`
- `docs/postman/edge-platform.postman_collection.json`

找 3 个以上现有可复用模式：

- 设备筛选和列表查询模式。
- 批量任务创建、执行、取消测试模式。
- 日志 CSV 导出注入防护模式。
- ScheduledTask CRUD 后端和前端封装模式。
- WebSocket 鉴权和快照测试模式。

先补失败优先测试：

- 后端目标预览按 `project_id`、`group_id`、`status`、`tags`、`device_ids` 命中设备。
- 后端模板 CRUD。
- 后端任务结果 CSV 导出和注入防护。
- 前端设备选择器提交 `device_ids`。
- 前端模板创建、编辑、套用、删除。
- 前端任务结果导出触发 Blob 下载。
- 前端 WebSocket 快照更新任务详情。

### Step 2：后端目标预览接口

新增：

```http
POST /api/update-tasks/preview-targets
```

实现要求：

- 请求体接收 `target_filter` 和可选 `execution_mode`。
- 复用 `UpdateTaskService` 当前目标匹配逻辑，避免预览和创建不一致。
- 返回目标设备清单和 warnings。
- warnings 至少覆盖：
  - 缺少 SSH 端口。
  - 缺少 SSH 凭据。
  - 目标设备数为 0。
- 不返回明文密码、Token、私钥或凭据内容。
- 记录操作日志可选；若记录，只记录筛选摘要和命中数量。

### Step 3：后端命令模板模型与接口

新增模板模型，建议表名：

```text
update_task_templates
```

字段：

- `id`
- `name`
- `description`
- `command`
- `task_type`
- `default_execution_mode`
- `created_at`
- `updated_at`

新增接口：

- `GET /api/update-task-templates`
- `POST /api/update-task-templates`
- `PUT /api/update-task-templates/{template_id}`
- `DELETE /api/update-task-templates/{template_id}`

实现要求：

- 模板名称必填且长度受限。
- 命令必填且长度受限。
- `default_execution_mode` 只允许 `dry_run` 或 `ssh_command`。
- 不接受、不保存、不返回敏感字段。
- 模板创建、更新、删除写入操作日志。
- SQLite 自动建表或迁移方式沿用项目现有数据库初始化模式。

### Step 4：后端任务结果导出

新增：

```http
GET /api/update-tasks/{task_id}/export
```

实现要求：

- 返回 `text/csv; charset=utf-8`。
- 设置 `Content-Disposition: attachment; filename="update_task_{id}_results.csv"`。
- 字段包含：
  - `task_id`
  - `task_name`
  - `device_id`
  - `device_sn`
  - `status`
  - `exit_code`
  - `stdout_summary`
  - `stderr_summary`
  - `error_message`
  - `started_at`
  - `finished_at`
- 复用或抽取现有日志 CSV 注入防护逻辑。
- 只导出摘要和错误原因，不导出完整终端输出。
- 任务不存在返回 404。

### Step 5：失败设备新建任务支持

不新增直接重跑旧任务的后端语义。

后端只需保证：

- `GET /api/update-tasks/{id}` 返回足够识别失败设备的字段。
- 前端可从失败设备中提取 `device_id`。
- `POST /api/update-tasks` 支持 `target_filter.device_ids`。

前端实现：

- 在任务详情中显示“以失败设备新建任务”按钮。
- 点击后打开创建任务表单，自动填入：
  - 原任务命令。
  - 原任务类型。
  - 原任务执行模式。
  - 原任务失败策略和并发限制。
  - `target_filter.device_ids` 为失败设备 ID。
  - 任务名称追加“失败重试”。
- 若失败设备数为 0，按钮禁用。

### Step 6：前端 API 封装

在 `frontend/src/api/platform.ts` 中新增类型和函数：

- `UpdateTaskTargetPreviewRequest`
- `UpdateTaskTargetPreviewResponse`
- `UpdateTaskTemplateRead`
- `UpdateTaskTemplateCreateRequest`
- `UpdateTaskTemplateUpdateRequest`
- `previewUpdateTaskTargets(payload)`
- `listUpdateTaskTemplates()`
- `createUpdateTaskTemplate(payload)`
- `updateUpdateTaskTemplate(templateId, payload)`
- `deleteUpdateTaskTemplate(templateId)`
- `exportUpdateTaskResults(taskId)`

同时复核现有：

- `createUpdateTask`
- `executeUpdateTask`
- `listUpdateTasks`
- `buildApiWebSocketUrl`
- `getAccessToken`

### Step 7：前端组件拆分

优先拆分以下组件：

1. `DeviceTargetSelector.vue`
   - 管理目标筛选、设备勾选、目标预览。
   - 对外输出最终 `target_filter`、预览设备和 warnings。
2. `UpdateTaskTemplatePanel.vue`
   - 管理模板列表、创建、编辑、删除、套用。
   - 对外发出“套用模板”事件。
3. `UpdateTaskResultTable.vue`
   - 展示每台设备执行结果。
   - 支持展开 stdout/stderr 摘要。
   - 提供失败设备集合。

`App.vue` 保留现有批量更新入口，但要尽量把新状态和复杂 UI 下沉到组件内。

如拆分 `UpdateTaskPanel.vue` 风险过高，本轮不强制整体迁移批量更新页，只完成上述三个局部组件拆分。

### Step 8：前端批量任务创建增强

调整“批量更新”创建流程：

- 保留现有基础字段：
  - 任务名称
  - 命令
  - 执行模式
  - 失败策略
  - 并发限制
- 新增目标选择器区域。
- 新增模板选择/管理区域。
- 创建前调用目标预览接口。
- 目标设备数为 0 时禁止保存真实 SSH 任务。
- 手动勾选设备时提交 `target_filter.device_ids`。
- 真实 SSH 模式保存或执行前显示具体确认：
  - 命令
  - 目标数量
  - 前几台目标设备摘要
  - 风险提示

### Step 9：前端任务详情、导出与 WebSocket 快照

任务详情增强：

- 使用 `UpdateTaskResultTable.vue` 展示设备结果。
- 显示成功、失败、跳过、待执行数量。
- 支持 stdout/stderr 摘要展开。
- 支持导出 CSV：
  - 调用 `exportUpdateTaskResults(taskId)`。
  - 使用 Blob 下载。
- 支持以失败设备新建任务。

WebSocket 快照：

- 执行任务后连接 `/api/ws/update-tasks/{id}?token=<access_token>`。
- 收到 `task.snapshot` 后更新当前任务详情。
- 连接失败显示中文局部错误。
- WebSocket 关闭不清空页面状态。
- 页面切换或任务结束时关闭连接。

### Step 10：文档与 Postman

更新：

- `README.md`
  - 补充 Wave16 批量任务安全增强说明。
- `docs/api.md`
  - 目标预览接口。
  - 模板 CRUD。
  - 任务结果导出。
  - 失败设备新建任务流程说明。
  - WebSocket 快照使用说明。
- `docs/deployment.md`
  - 真实 SSH 批量任务执行前检查。
  - `/api/ws` WebSocket 代理检查。
  - CSV 下载响应头排查。
- `docs/postman/edge-platform.postman_collection.json`
  - 新增 Wave16 分组：
    - 目标预览。
    - 模板创建、更新、列表、删除。
    - 创建真实 SSH 任务。
    - 执行任务。
    - 查询任务详情。
    - 导出任务结果。

### Step 11：验证与验收

后端：

- 新增目标预览测试。
- 新增模板 CRUD 测试。
- 新增任务结果导出测试。
- 新增 WebSocket 快照结构或鉴权测试。
- 运行全量 pytest。

前端：

- 新增或扩展 App 测试覆盖设备选择器、模板、导出、WebSocket 快照。
- 运行 Vitest 全量。
- 运行生产构建。

浏览器冒烟：

- 登录页非空白。
- 批量更新页可以打开创建表单。
- 目标预览显示设备数量。
- 模板可套用到命令。
- 任务结果表可见。

## 4. 验证命令

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave16'

Set-Location 'C:\01_work\02_program\远程终端平台\frontend'
npm.cmd test -- --run
npm.cmd run build
```

后端局部验证可先运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests -k "update_task or template or websocket" --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave16-targeted'
```

## 5. 风险与回滚

- 目标预览和任务创建若使用不同匹配逻辑，会造成执行范围不可信；必须复用同一服务函数。
- 模板编辑涉及新增数据表，需沿用当前 SQLite 初始化/补列策略，避免破坏已有数据库。
- 真实 SSH 任务确认必须具体展示命令和目标数量，不能退化成泛化确认。
- WebSocket 本轮不扩展持续事件总线，避免扩大后端任务执行机制风险。
- CSV 导出必须复用注入防护，避免打开 CSV 时触发公式。
- 前端批量更新逻辑在 `App.vue` 中已有历史复杂度，本轮组件拆分应小步推进。

## 6. 完成定义

- Wave16 需求文档中的已确认决策全部落实。
- 后端目标预览、模板 CRUD、任务结果导出可用。
- 前端设备选择器、模板管理、任务结果增强、导出和 WebSocket 快照入口可用。
- 失败设备可通过“以失败设备新建任务”快速重试。
- 局部接口失败不导致登录闪退。
- 新增文案为中文。
- README、API、部署文档、Postman Collection 更新完成。
- 后端全量测试、前端测试和前端构建通过。
