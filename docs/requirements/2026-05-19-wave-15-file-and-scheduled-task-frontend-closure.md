# Wave 15 需求文档：文件管理与定时任务前端闭环

> 阶段：`requirement_doc`  
> 状态：已确认，下一步进入执行计划  
> 基线：Wave 14 已完成远程连接体验产品化，平台已有文件管理接口和定时任务接口，但前端还没有完整可操作入口。

## 1. 背景

平台当前已经具备较完整的设备运维主线：

- 设备 CRUD、分组、frps 导入、设备级 SSH 凭据和凭据加密诊断。
- 仪表盘真实监控指标、异常设备摘要和系统诊断页。
- 远程连接页已支持 SSH xterm 终端和 noVNC 画面。
- 批量更新任务已支持演练和真实 SSH 命令执行。
- 后端已经存在设备文件接口和定时任务接口。

当前缺口是：文件接口和定时任务接口只能通过 API/Postman 使用，管理员无法在前端完成日常操作。本轮目标是补齐这两个“已有后端能力但前端不可用”的闭环。

## 2. 目标

Wave 15 完成后，管理员登录前端后应能：

1. 从设备列表选择一台设备，进入文件管理区域。
2. 浏览设备文件目录，查看文件名、路径、类型、大小和修改时间。
3. 选择本地文件并上传到设备指定远程路径。
4. 下载设备上的任意文件。
5. 删除指定文件，并有明确二次确认。
6. 管理定时任务：列表、创建、编辑、删除、启用/停用、立即执行。
7. 查看定时任务执行日志。
8. 所有新增界面文案继续使用中文。

## 3. 非目标

本轮不实现以下内容：

- 不实现断点续传、目录打包下载。
- 不实现可视化文件拖拽上传。
- 不实现在线代码编辑器、语法高亮和 diff。
- 不实现真实后台调度器或 cron daemon；沿用当前后端接口语义。
- 不实现复杂 cron 表达式编辑器，只提供基础输入和常用提示。
- 不重构为独立路由或全局状态管理。
- 不引入 RBAC、多用户权限隔离或审批流。

## 4. 功能需求

### 4.1 文件管理入口

文件管理入口挂在“设备管理”的设备详情或操作区内，不新增独立一级导航。

文件管理页布局：

- 左侧：设备列表。
  - 显示设备名称、序列号、项目号、状态、SSH 端口、凭据状态。
  - 支持按名称、序列号、项目号搜索。
  - 缺少 SSH 端口或凭据时标识为“文件后端可能不可用”。
- 右侧：文件操作区。
  - 顶部显示当前设备和当前路径。
  - 中部显示文件列表。
  - 底部或侧栏提供上传、下载、删除操作。

### 4.2 目录浏览

沿用当前后端接口：

```http
GET /api/devices/{device_id}/files?path=/opt/app
```

前端要求：

- 默认路径为 `/`。
- 支持输入路径并刷新。
- 文件列表字段至少包括：
  - 名称
  - 类型
  - 路径
  - 大小
  - 修改时间
- 点击目录项时进入该目录。
- 提供“返回上级”按钮。
- 接口失败时显示中文错误，不退出登录，除非返回 401/403。

### 4.3 文件上传

当前后端文件上传接口需要扩展到支持任意文件类型。实现方式由执行计划结合现有代码确定，优先使用标准 multipart 文件上传；若保留兼容 JSON 文本上传，也不得影响新文件上传能力。

```http
POST /api/devices/{device_id}/files/upload
```

目标能力：

- 支持选择本地文件。
- 支持输入远程目标路径。
- 支持上传文本、图片、压缩包、二进制文件等常见文件类型。
- 上传成功后刷新当前目录。
- 上传前如果本地文件或远程路径为空，展示中文校验错误。

前端要求：

- 支持输入远程路径。
- 支持选择本地文件。
- 上传时显示处理中状态。
- 上传成功后刷新当前目录。
- 上传失败显示中文错误。

### 4.4 文件下载

沿用当前后端接口：

```http
GET /api/devices/{device_id}/files/download?remote_path=/opt/app/config.txt
```

前端要求：

- 文件列表中提供“下载”操作。
- 下载结果以浏览器文件下载形式保存。
- 下载失败显示中文错误。

### 4.5 删除文件

沿用当前后端接口：

```http
DELETE /api/devices/{device_id}/files
```

请求体：

```json
{
  "remote_path": "/opt/app/config.txt"
}
```

前端要求：

- 删除前必须二次确认。
- 删除成功后刷新当前目录。
- 禁止在前端主动提交空路径、`.`、`..` 或 `/`。
- 后端返回路径安全错误时，前端展示中文错误。

### 4.6 定时任务管理

新增前端“定时任务”导航页。

沿用当前后端接口：

- `GET /api/scheduled-tasks`
- `POST /api/scheduled-tasks`
- `PUT /api/scheduled-tasks/{task_id}`
- `DELETE /api/scheduled-tasks/{task_id}`
- `POST /api/scheduled-tasks/{task_id}/toggle`
- `POST /api/scheduled-tasks/{task_id}/execute`
- `GET /api/scheduled-tasks/{task_id}/logs`

列表展示字段：

- 任务名称
- 任务类型
- 调度表达式
- 命令
- 目标筛选
- 启用状态
- 创建时间
- 更新时间

创建/编辑字段：

- `name`
- `task_type`
- `schedule`
- `command`
- `target_filter`
- `enabled`

调度表达式约束：

- 继续使用后端现有格式：`cron:<表达式>` 或 `interval:<秒数/描述>`。
- 前端提供占位示例，例如：
  - `interval:300`
  - `cron:0 * * * *`
- 本轮不做复杂 cron 解析器，只做必填和前缀校验。

### 4.7 定时任务执行与日志

立即执行：

- 点击“立即执行”调用 `POST /api/scheduled-tasks/{task_id}/execute`。
- 执行成功后显示 `output_summary`。
- 执行失败显示中文错误。

日志查看：

- 点击“查看日志”调用 `GET /api/scheduled-tasks/{task_id}/logs`。
- 展示时间、动作、状态和详情。
- 日志为空时显示中文空状态。

### 4.8 中文显示与局部错误

新增或调整的前端文案必须为中文，包括：

- 导航项
- 按钮
- 表格列名
- 空状态
- 校验错误
- 接口错误
- 测试断言中的可见文本

文件管理和定时任务接口失败不得导致前端退出登录，除非返回 401/403。

## 5. 后端需求

后端以复核和小修为主。

必须确认：

- 文件上传/下载接口鉴权完整。
- 文件路径安全限制仍有效。
- `file_backend=local` 和 `file_backend=sftp` 错误能返回可理解的状态码和错误信息。
- 文件上传/下载支持非文本文件，不破坏已有文本上传兼容路径。
- 定时任务 CRUD、启停、立即执行和日志查询返回结构稳定。
- 操作日志覆盖文件上传、下载、删除以及定时任务关键操作。

如当前后端行为已满足，本轮只补测试和文档，不做大范围重构。

## 6. 前端需求

### 6.1 API 封装

在 `frontend/src/api/platform.ts` 补齐类型和函数：

- 文件：
  - `listDeviceFiles(deviceId, path)`
  - `uploadDeviceFile(deviceId, payload)`
  - `downloadDeviceFile(deviceId, remotePath)`
  - `deleteDeviceFile(deviceId, payload)`
- 定时任务：
  - `listScheduledTasks(params?)`
  - `createScheduledTask(payload)`
  - `updateScheduledTask(taskId, payload)`
  - `deleteScheduledTask(taskId)`
  - `toggleScheduledTask(taskId)`
  - `executeScheduledTask(taskId)`
  - `listScheduledTaskLogs(taskId)`

### 6.2 前端组件拆分

Wave 15 开始拆分前端组件，避免继续扩大 `App.vue`。

拆分要求：

- 文件管理相关 UI 和状态优先拆为独立组件，例如 `DeviceFilePanel.vue`。
- 定时任务相关 UI 和状态优先拆为独立组件，例如 `ScheduledTaskPanel.vue`。
- 公共类型和工具函数可继续放在 `frontend/src/api/platform.ts` 或新增轻量工具文件。
- 不做 Vue Router/Pinia 大重构。
- 保持现有 Element Plus 风格。
- 不使用纯英文 UI 文案。

## 7. 文档与 Postman

需要更新：

- `README.md`
  - 补充文件管理和定时任务前端能力。
- `docs/api.md`
  - 补充文件接口和定时任务接口的前端使用说明。
- `docs/deployment.md`
  - 补充 `FILE_BACKEND=sftp`、SSH 凭据、路径权限、Nginx 下载响应排查。
- `docs/postman/edge-platform.postman_collection.json`
  - 增加文件管理分组。
  - 增加定时任务分组。

## 8. 测试需求

### 8.1 后端测试

至少运行现有后端全量测试。

如修改后端，必须覆盖：

- 文件路径非法。
- 文件列表、上传、下载、删除。
- 定时任务创建、更新、启停、执行、日志。

### 8.2 前端测试

在 `frontend/src/__tests__/app.spec.ts` 或新增测试文件中覆盖：

- 文件管理页显示设备列表。
- 选择设备后加载文件列表。
- 切换路径并刷新。
- 上传文件调用接口并显示成功状态。
- 下载文件调用接口并触发浏览器下载。
- 删除文件前出现确认，确认后调用接口。
- 定时任务列表展示。
- 创建定时任务。
- 编辑定时任务。
- 启用/停用定时任务。
- 立即执行定时任务并显示输出摘要。
- 查看定时任务日志。
- 文件/定时任务接口 500/502 失败时页面不退出登录。

### 8.3 验证命令

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave15'

Set-Location 'C:\01_work\02_program\远程终端平台\frontend'
npm.cmd test -- --run
npm.cmd run build
```

建议额外做浏览器冒烟：

- 登录页非空白。
- 登录后可看到“文件管理”和“定时任务”导航。
- 选择设备后文件列表区域可见。
- 创建一个测试定时任务后能在列表中看到。

## 9. 验收标准

Wave 15 完成后必须满足：

- 前端存在可用的文件管理入口。
- 文件列表、上传、下载、删除可通过前端触发真实后端 API。
- 前端存在可用的定时任务管理入口。
- 定时任务列表、创建、编辑、删除、启停、立即执行和日志查看可用。
- 局部接口失败不导致登录闪退。
- 新增文案全部为中文。
- README、API 文档、部署文档和 Postman Collection 更新完成。
- 后端测试、前端测试和前端构建通过。

## 10. 风险与约束

- 本轮要求支持所有文件类型上传/下载；如当前后端接口只支持文本内容，需要扩展为适合二进制文件的传输方式。
- SFTP 模式依赖设备 SSH 端口、设备凭据、frpc/frps、防火墙和后端 `paramiko` 环境。
- 定时任务当前更偏 API 能力闭环，不等价于完整生产级调度系统。
- `App.vue` 已经较大，本轮开始拆分前端组件，避免继续无边界膨胀。
- 文件下载在测试中需要 mock `URL.createObjectURL`、`HTMLAnchorElement.click` 等浏览器 API。

## 11. 已确认决策

1. 文件管理需要支持所有文件类型的上传和下载，不限于文本文件。
2. 文件管理入口挂在设备管理详情或操作区内，不新增独立一级导航。
3. 定时任务本轮只做 API 管理闭环，不接入真实后台调度器。
4. Wave 15 开始拆分前端组件，避免继续扩大 `App.vue`。
5. Wave 15 需求文档先不提交、不推送；等待需求确认，等 Wave 15 开发完毕后统一提交并推送。
