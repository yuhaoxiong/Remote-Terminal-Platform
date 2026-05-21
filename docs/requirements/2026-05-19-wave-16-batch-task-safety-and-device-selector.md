# Wave 16 需求文档：批量任务安全增强与设备选择器

> 阶段：`requirement_doc`  
> 状态：已确认，下一步进入执行计划  
> 基线：Wave 15 已完成设备文件管理与定时任务前端闭环，平台已具备真实 SSH 批量命令执行能力，但任务创建前的目标确认、模板复用、执行结果分析和实时进度体验仍偏弱。

## 1. 背景

平台当前已经具备以下批量任务基础：

- 后端已有批量更新任务模型和 API：
  - `GET /api/update-tasks`
  - `POST /api/update-tasks`
  - `GET /api/update-tasks/{id}`
  - `POST /api/update-tasks/{id}/execute`
  - `POST /api/update-tasks/{id}/cancel`
  - `WS /api/ws/update-tasks/{id}?token=<access_token>`
- 任务支持 `dry_run` 演练模式和 `ssh_command` 真实 SSH 命令执行。
- 任务目标可通过 `target_filter` 按项目、分组、标签、状态和设备 ID 匹配。
- 任务执行结果已经记录到每台设备维度，包含状态、退出码、输出摘要、错误摘要和失败原因。
- 前端已有“批量更新”页面，可以创建任务、执行任务和查看基础结果。

当前不足：

- 创建任务时目标设备不够可视，管理员不容易确认“到底会影响哪些设备”。
- 真实 SSH 执行前虽然有确认，但确认信息还不够具体，缺少目标设备清单和风险摘要。
- 常用命令无法模板化复用，容易重复输入和误输。
- 任务详情中的设备结果展示不够细，排查失败设备不方便。
- 已有更新任务 WebSocket 只做基础快照，前端没有形成实时进度体验。
- 失败设备不能快速重新执行，只能重新创建类似任务。

Wave 16 的目标是提升批量 SSH 任务的安全性、可控性和可观测性，让管理员在执行前明确影响范围，执行中看到实时进度，执行后能快速定位失败并导出结果。

## 2. 目标

Wave 16 完成后，管理员应能：

1. 在创建批量任务时通过设备选择器明确目标设备范围。
2. 按项目、分组、标签、状态筛选设备，并支持手动勾选设备。
3. 创建任务前看到命中设备数量、设备清单和风险提示。
4. 使用常用命令模板快速填充命令和说明。
5. 真实 SSH 执行前看到命令、执行模式、目标设备清单和二次确认。
6. 在任务详情中展开查看每台设备的退出码、标准输出摘要、错误输出摘要和失败原因。
7. 通过 WebSocket 查看任务实时进度，不完全依赖手动刷新。
8. 对失败设备快速创建“重试失败设备”任务或触发后端重试接口。
9. 导出任务结果 CSV，便于线下归档和排查。
10. 所有新增前端文案继续使用中文。

## 3. 非目标

本轮不实现以下内容：

- 不实现多用户 RBAC、审批流或项目级权限隔离。
- 不实现完整作业编排 DAG、条件分支或复杂任务流水线。
- 不实现自动回滚执行，只保留现有 `failure_strategy` 语义和结果提示。
- 不记录完整终端输入输出流，只展示和导出已有摘要字段。
- 不实现命令模板的共享市场、分类权限或版本历史。
- 不实现后台长期调度器；定时任务仍沿用 Wave 15 的 API 管理闭环。
- 不引入大型全局状态管理重构；如需拆分组件，应保持局部、可测试。
- 不要求真实生产设备参与自动化测试，真实 SSH 仍以手工联调为准。

## 4. 功能需求

### 4.1 设备选择器

批量任务创建区域新增设备选择器，用于把 `target_filter` 从“隐式 JSON 筛选”变成“可视化筛选 + 手动选择”。

选择器能力：

- 支持按以下条件筛选设备：
  - 项目号 `project_id`
  - 分组 `group_id`
  - 标签 `tags`
  - 状态 `status`
  - 关键词搜索：设备名称、序列号、位置
- 支持手动勾选设备。
- 支持“全选当前筛选结果”和“清空选择”。
- 显示当前命中设备数量。
- 显示目标设备清单，至少包含：
  - 设备名称
  - 序列号
  - 项目号
  - 分组
  - 状态
  - SSH 端口
  - 凭据状态

目标筛选落库策略：

- 若只使用筛选条件，可继续提交 `target_filter` 中的项目、分组、标签、状态字段。
- 若手动勾选设备，应提交 `target_filter.device_ids`。
- 若同时使用筛选条件和手动勾选，以手动勾选设备 ID 为准，避免“看见的设备”和“实际命中设备”不一致。

### 4.2 目标预览接口

为避免前端重复实现复杂筛选逻辑，建议后端新增目标预览接口：

```http
POST /api/update-tasks/preview-targets
```

请求体：

```json
{
  "target_filter": {
    "project_id": "frps-import",
    "group_id": 1,
    "status": "online",
    "tags": ["vision"],
    "device_ids": [1, 2, 3]
  }
}
```

响应：

```json
{
  "total": 2,
  "items": [
    {
      "id": 1,
      "name": "edge-01",
      "device_sn": "SN001",
      "project_id": "frps-import",
      "group_id": 1,
      "status": "online",
      "ssh_port": 12001,
      "ssh_credential_configured": true
    }
  ],
  "warnings": [
    "1 台设备缺少 SSH 凭据，将无法执行真实 SSH 命令"
  ]
}
```

要求：

- 预览接口需要登录鉴权。
- 不返回明文密码、Token、私钥或凭据内容。
- 对 `ssh_command` 模式，应标记缺少 SSH 端口或凭据的设备。
- 前端创建任务前以该接口结果作为最终目标确认依据。

### 4.3 真实 SSH 执行确认

当 `execution_mode=ssh_command` 时，执行前必须显示二次确认。

确认内容至少包括：

- 任务名称。
- 命令内容。
- 目标设备数量。
- 目标设备清单摘要。
- 失败策略。
- 并发限制。
- 风险提示：“该操作会通过 SSH 在目标设备上真实执行命令”。

确认要求：

- 二次确认不能只显示笼统文字。
- 目标设备数量为 0 时禁止创建或执行真实 SSH 任务。
- 若存在缺少 SSH 端口或凭据的设备，应显示警告；是否允许创建由执行计划结合现有后端行为决定，但真实执行结果必须明确标识失败原因。

### 4.4 命令模板

新增命令模板能力，用于保存常用命令。

模板字段：

- `id`
- `name`
- `description`
- `command`
- `task_type`
- `default_execution_mode`
- `created_at`
- `updated_at`

建议新增 API：

- `GET /api/update-task-templates`
- `POST /api/update-task-templates`
- `PUT /api/update-task-templates/{template_id}`
- `DELETE /api/update-task-templates/{template_id}`

前端要求：

- 批量任务创建表单可选择模板。
- 选择模板后自动填充命令、任务类型和默认执行模式。
- 模板只保存命令和说明，不保存设备凭据、Token 或私钥。
- 模板删除前需要二次确认。

如本轮时间不足，模板管理可先做最小闭环：

- 仅支持列表、创建、套用、删除。
- 编辑模板可放到后续 Wave。

### 4.5 任务详情增强

批量任务详情页需要更适合排查结果。

展示要求：

- 总体信息：
  - 任务名称
  - 执行模式
  - 任务状态
  - 目标设备数
  - 成功数
  - 失败数
  - 跳过数
  - 创建时间
  - 更新时间
- 设备结果表：
  - 设备 ID
  - 设备名称或序列号
  - 状态
  - 退出码
  - 标准输出摘要
  - 错误输出摘要
  - 错误原因
  - 开始时间
  - 结束时间
- 行展开：
  - 展示更完整的 stdout/stderr 摘要。
  - 长文本需要折叠或限制高度，避免撑破页面。

### 4.6 失败设备重试

支持对失败设备快速重试。

优先方案：

- 后端新增接口：

```http
POST /api/update-tasks/{task_id}/retry-failed
```

- 该接口基于原任务命令和失败设备集合创建一个新任务，或重置失败设备状态并重新执行，具体由执行计划结合现有模型选择。

备选方案：

- 前端提供“以失败设备新建任务”按钮。
- 点击后打开创建任务表单，自动填入：
  - 原任务命令。
  - 原任务执行模式。
  - `target_filter.device_ids` 为失败设备 ID。
  - 任务名称追加“失败重试”。

本轮建议优先选择“以失败设备新建任务”，风险更低，不改变已有任务历史。

### 4.7 任务结果导出

新增任务结果 CSV 导出能力。

建议 API：

```http
GET /api/update-tasks/{task_id}/export
```

响应：

- `Content-Type: text/csv; charset=utf-8`
- `Content-Disposition: attachment; filename="update_task_{id}_results.csv"`

CSV 字段至少包含：

- task_id
- task_name
- device_id
- device_sn
- status
- exit_code
- stdout_summary
- stderr_summary
- error_message
- started_at
- finished_at

安全要求：

- 继续沿用日志 CSV 的注入防护策略。
- 不导出密码、Token、私钥或完整凭据内容。

### 4.8 WebSocket 实时进度

前端“批量更新”页面接入：

```text
WS /api/ws/update-tasks/{task_id}?token=<access_token>
```

要求：

- 执行任务后自动连接 WebSocket。
- 收到快照后更新任务状态和设备结果。
- WebSocket 失败时显示中文提示，并允许手动刷新任务详情。
- WebSocket 失败不得导致退出登录，除非鉴权明确失败。
- 页面离开或任务结束后关闭 WebSocket。

如当前后端 WebSocket 只返回一次快照，本轮可先实现前端连接和快照消费；是否增强为持续推送由执行计划评估。

### 4.9 中文显示与局部错误

新增或调整的前端文案必须为中文，包括：

- 按钮
- 表格列名
- 空状态
- 风险提示
- 二次确认
- 接口错误
- 测试断言中的可见文本

批量任务相关接口失败不得导致前端退出登录，除非返回 401/403。

## 5. 后端需求

后端本轮建议新增或完善：

1. 目标预览接口 `POST /api/update-tasks/preview-targets`。
2. 命令模板 CRUD 接口。
3. 任务结果 CSV 导出接口。
4. 失败设备重试或“失败设备新建任务”所需的后端支持。
5. 更新任务 WebSocket 行为复核。

必须确认：

- 真实 SSH 执行仍不返回明文凭据。
- 任务模板不保存敏感信息。
- CSV 导出有注入防护。
- 任务预览和任务创建使用同一套目标匹配逻辑，避免预览与实际执行不一致。
- 操作日志覆盖模板创建/删除、任务导出、失败重试等关键动作。

## 6. 前端需求

### 6.1 API 封装

在 `frontend/src/api/platform.ts` 中补齐类型和函数：

- 目标预览：
  - `previewUpdateTaskTargets(payload)`
- 模板：
  - `listUpdateTaskTemplates()`
  - `createUpdateTaskTemplate(payload)`
  - `updateUpdateTaskTemplate(templateId, payload)`
  - `deleteUpdateTaskTemplate(templateId)`
- 任务增强：
  - `exportUpdateTaskResults(taskId)`
  - `retryFailedUpdateTaskDevices(taskId)` 或前端复用 `createUpdateTask`
- WebSocket：
  - 复用已有 `buildApiWebSocketUrl`

### 6.2 组件拆分

Wave 16 继续收敛 `App.vue`。

建议拆分：

- `UpdateTaskPanel.vue`
  - 承载批量任务列表、创建、执行和详情主逻辑。
- `DeviceTargetSelector.vue`
  - 承载筛选、勾选、目标预览。
- `UpdateTaskTemplatePanel.vue`
  - 承载模板列表、创建、删除、套用。
- `UpdateTaskResultTable.vue`
  - 承载设备结果表、展开和导出入口。

如拆分成本过高，可以先拆 `DeviceTargetSelector.vue` 和 `UpdateTaskResultTable.vue`，保留现有更新任务主流程。

### 6.3 交互约束

- 真实 SSH 任务创建和执行必须有中文风险提示。
- 目标设备数量为 0 时禁用保存或执行。
- 选择模板后，用户仍可手动修改命令。
- 导出任务结果时使用浏览器下载。
- WebSocket 失败时保留页面状态，不清空任务结果。

## 7. 文档与 Postman

需要更新：

- `README.md`
  - 补充批量任务增强、设备选择器、模板、结果导出。
- `docs/api.md`
  - 补充新增接口请求/响应示例。
- `docs/deployment.md`
  - 补充真实 SSH 批量任务执行前检查、WebSocket 代理和 CSV 下载排查。
- `docs/postman/edge-platform.postman_collection.json`
  - 新增 Wave 16 分组：
    - 目标预览
    - 创建模板
    - 创建真实 SSH 任务
    - 执行任务
    - 查询任务详情
    - 导出任务结果
    - 以失败设备重试或新建任务

## 8. 测试需求

### 8.1 后端测试

至少覆盖：

- 目标预览按项目、分组、标签、状态、设备 ID 匹配。
- 预览接口不返回敏感字段。
- 预览结果和任务创建命中设备一致。
- 模板创建、列表、删除。
- 模板不接受或不返回敏感字段。
- 任务结果 CSV 导出字段完整。
- CSV 注入防护。
- 失败设备重试或“失败设备新建任务”逻辑。
- 更新任务 WebSocket 鉴权和快照结构。

### 8.2 前端测试

在 `frontend/src/__tests__/app.spec.ts` 或新增测试文件中覆盖：

- 设备选择器按条件加载并展示设备。
- 手动勾选设备后创建任务提交 `device_ids`。
- 目标数量为 0 时不能创建真实 SSH 任务。
- 真实 SSH 执行前显示包含命令和目标数量的二次确认。
- 模板创建、套用和删除。
- 任务详情展示 stdout/stderr、退出码和失败原因。
- 导出任务结果触发 Blob 下载。
- WebSocket 快照更新任务状态。
- WebSocket 失败不退出登录。
- 局部接口 500/502 失败不退出登录。

### 8.3 验证命令

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave16'

Set-Location 'C:\01_work\02_program\远程终端平台\frontend'
npm.cmd test -- --run
npm.cmd run build
```

建议额外做浏览器冒烟：

- 登录页非空白。
- 批量更新页可以打开任务创建表单。
- 设备选择器可以展示目标设备数量。
- 选择模板后命令被填入。
- 任务详情页可以看到设备结果表。

## 9. 验收标准

Wave 16 完成后必须满足：

- 批量任务创建前可以预览目标设备。
- 真实 SSH 任务创建或执行前必须显示具体目标和风险确认。
- 支持至少一种常用命令模板复用方式。
- 任务详情能查看每台设备的执行摘要和失败原因。
- 支持任务结果 CSV 导出。
- 支持失败设备快速重试或以失败设备新建任务。
- 前端接入更新任务 WebSocket 快照或实时进度，不再完全依赖手动刷新。
- 局部接口失败不导致登录闪退。
- 新增文案全部为中文。
- README、API 文档、部署文档和 Postman Collection 更新完成。
- 后端测试、前端测试和前端构建通过。

## 10. 风险与约束

- 目标预览和任务创建必须复用同一套匹配逻辑，否则会造成“预览安全、执行越界”的高风险问题。
- 真实 SSH 命令执行具有破坏性，前端确认必须具体展示目标和命令。
- WebSocket 持续推送如果涉及后端任务状态事件机制，可能需要控制范围；本轮可先消费现有快照并保留手动刷新。
- 命令模板容易被误认为安全白名单；本轮模板只是便捷填充，不代表命令已审核。
- CSV 导出需要继续防止公式注入。
- 批量更新当前逻辑仍依赖设备 SSH 端口、凭据、frps 可达性和防火墙配置。

## 11. 已确认决策

1. 失败设备重试采用“以失败设备新建任务”方式，不在本轮直接修改历史任务或追加 `retry-failed` 后端重试执行语义。
2. 命令模板本轮需要完整编辑能力，覆盖列表、创建、编辑、套用和删除。
3. WebSocket 本轮先接入现有快照，并在前端形成实时入口；若后端当前只返回一次快照，不强行扩展持续事件总线。
4. 目标预览接口允许纳入本轮，用于降低前端重复筛选和预览/执行不一致风险。
5. 任务结果导出只导出摘要和错误原因，不导出完整终端输出，避免文件过大和敏感信息泄漏。
