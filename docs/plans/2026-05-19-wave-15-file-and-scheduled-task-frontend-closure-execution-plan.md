# Wave 15 执行计划：文件管理与定时任务前端闭环

> 阶段：`xl_plan`  
> 状态：待确认，确认后进入实现  
> 冻结需求：`docs/requirements/2026-05-19-wave-15-file-and-scheduled-task-frontend-closure.md`

## 1. 执行目标

本轮补齐已有后端 API 的前端闭环：设备文件管理和定时任务管理。实现时同步开始拆分前端组件，避免继续扩大 `App.vue`。

完成后应达到：

- 设备管理页内可以打开设备文件管理面板。
- 文件管理支持目录浏览、任意文件上传、任意文件下载、删除和中文错误提示。
- 定时任务支持列表、创建、编辑、删除、启用/停用、立即执行和日志查看。
- 定时任务只做现有 API 管理闭环，不接入真实后台调度器。
- 前端新增文件管理和定时任务组件，`App.vue` 只保留入口和数据装配。
- 文档和 Postman 与新能力同步。

## 2. 冻结决策

1. 文件管理支持所有文件类型上传和下载，不限于文本文件。
2. 文件管理入口挂在设备管理详情或操作区内，不新增独立一级导航。
3. 定时任务本轮只做 API 管理闭环，不接入真实后台调度器。
4. Wave 15 开始拆分前端组件，避免继续扩大 `App.vue`。
5. Wave 15 需求和实现完成后统一提交并推送；计划确认前不提交需求文档。

## 3. 工作拆分

### Step 1：基线审计与失败优先测试

- 阅读并记录当前文件和定时任务相关代码：
  - `backend/app/routers/devices.py`
  - `backend/app/services/file_service.py`
  - `backend/app/schemas/file_transfer.py`
  - `backend/app/routers/scheduled_tasks.py`
  - `backend/app/services/scheduled_task_service.py`
  - `backend/app/schemas/scheduled_task.py`
  - `frontend/src/App.vue`
  - `frontend/src/api/platform.ts`
  - `frontend/src/__tests__/app.spec.ts`
- 找 3 个以上现有可复用模式：
  - 前端 API mock 和页面交互测试。
  - 文件接口后端测试。
  - 定时任务后端测试。
  - Element Plus 表格、表单、确认弹窗使用方式。
- 先补失败优先测试：
  - 文件面板可在设备管理中打开。
  - 目录加载、路径切换、返回上级。
  - 任意文件上传使用 `File`/`FormData` 或等价封装。
  - 下载触发 Blob 下载。
  - 删除前确认。
  - 定时任务列表、创建、编辑、启停、执行、日志。
  - 500/502 局部失败不退出登录。

### Step 2：后端文件接口扩展为任意文件

- 复核当前文件接口是否只支持 JSON 文本上传。
- 若仅支持文本，扩展上传接口以支持 multipart 文件：
  - `remote_path` 作为表单字段。
  - `file` 作为上传文件。
  - 保留已有 JSON 文本上传兼容路径，避免破坏旧 Postman/测试。
- 下载接口返回真实文件字节：
  - 设置合理 `Content-Type`。
  - 设置 `Content-Disposition`，便于浏览器保存。
  - 不把二进制内容错误地当作 UTF-8 文本处理。
- local 后端和 SFTP 后端都要支持二进制读写。
- 路径安全规则继续生效，禁止空路径、`.`、`..`、路径穿越和根路径删除。

### Step 3：前端 API 封装

- 在 `frontend/src/api/platform.ts` 补齐类型：
  - `FileItem`
  - `FileListResponse`
  - `FileOperationResponse`
  - `ScheduledTaskRead`
  - `ScheduledTaskCreateRequest`
  - `ScheduledTaskUpdateRequest`
  - `ScheduledTaskExecuteResponse`
- 补齐函数：
  - `listDeviceFiles`
  - `uploadDeviceFile`
  - `downloadDeviceFile`
  - `deleteDeviceFile`
  - `listScheduledTasks`
  - `createScheduledTask`
  - `updateScheduledTask`
  - `deleteScheduledTask`
  - `toggleScheduledTask`
  - `executeScheduledTask`
  - `listScheduledTaskLogs`
- 下载函数返回 `Blob`，上传函数支持 `File`/`FormData`。

### Step 4：拆分文件管理组件

- 新增文件管理组件，建议路径：
  - `frontend/src/components/DeviceFilePanel.vue`
- 组件职责：
  - 接收当前设备。
  - 管理当前路径、文件列表、上传文件、远程路径、加载状态和错误状态。
  - 调用文件 API。
  - 发出局部操作成功/失败提示。
- 设备管理页集成方式：
  - 在设备表操作列新增“文件”按钮。
  - 点击后在设备管理页内展示文件面板或抽屉。
  - 不新增一级导航。
- UI 约束：
  - 中文文案。
  - 删除前二次确认。
  - 文件大小和时间格式清晰。
  - 缺少 SSH 端口或凭据时展示风险提示，但仍允许 local 文件后端场景使用。

### Step 5：拆分定时任务组件

- 新增定时任务组件，建议路径：
  - `frontend/src/components/ScheduledTaskPanel.vue`
- 集成方式：
  - 可以新增一级导航“定时任务”，因为需求只限制文件管理入口不新增一级导航。
  - 如为降低导航变化，也可挂在现有“批量更新”附近，但需要保持入口清晰。
- 组件职责：
  - 加载定时任务列表。
  - 创建/编辑表单。
  - 删除确认。
  - 启用/停用。
  - 立即执行并显示 `output_summary`。
  - 查询并展示任务日志。
- 表单校验：
  - `name` 必填。
  - `task_type` 必填。
  - `schedule` 必须以 `cron:` 或 `interval:` 开头。
  - `target_filter` 允许输入 JSON，解析失败时显示中文错误。

### Step 6：App.vue 收敛

- `App.vue` 只做：
  - 导航入口。
  - 基础设备数据传递。
  - 打开/关闭文件面板状态。
  - 引入定时任务组件。
- 避免把文件管理和定时任务的大量表单逻辑继续写入 `App.vue`。
- 若现有类型需要共享，优先从 API 层导出，避免组件之间复制类型。

### Step 7：文档与 Postman

- 更新 `README.md`：
  - 补充设备管理中的文件面板。
  - 补充定时任务管理页面。
- 更新 `docs/api.md`：
  - 补充 multipart 文件上传。
  - 补充 Blob 下载和响应头。
  - 补充定时任务前端使用流程。
- 更新 `docs/deployment.md`：
  - 补充 `FILE_BACKEND=sftp`、SSH 凭据、路径权限、Nginx 下载响应排查。
- 更新 `docs/postman/edge-platform.postman_collection.json`：
  - 增加文件列表、上传、下载、删除请求。
  - 增加定时任务 CRUD、启停、执行、日志请求。

### Step 8：验证与验收

- 后端：
  - 文件接口相关测试。
  - 定时任务相关测试。
  - 全量 pytest。
- 前端：
  - Vitest 全量。
  - 生产构建。
- 浏览器冒烟：
  - 登录页非空白。
  - 设备管理中可以打开文件面板。
  - 定时任务入口可见。

## 4. 验证命令

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave15'

Set-Location 'C:\01_work\02_program\远程终端平台\frontend'
npm.cmd test -- --run
npm.cmd run build
```

后端局部验证可先运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests -k "file or scheduled" --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave15-targeted'
```

## 5. 风险与回滚

- 任意文件上传会改变后端文件接口能力，需要兼容现有 JSON 文本上传测试和 Postman 请求。
- SFTP 二进制上传下载依赖 paramiko 文件对象读写模式，必须避免文本编码破坏二进制内容。
- 文件下载响应头在 Nginx 下可能被改写，部署文档需要给出排查路径。
- 前端组件拆分可能影响现有大页测试，需要以小步迁移保持现有测试稳定。
- 若定时任务组件范围过大，优先完成列表、创建、启停、执行，再补编辑、删除、日志。

## 6. 完成定义

- Wave 15 需求文档中的验收标准均有实现、测试或明确人工验收路径。
- 文件管理挂在设备管理内，支持目录、上传、下载、删除。
- 文件上传/下载支持非文本文件。
- 定时任务管理闭环可用。
- 前端已拆出文件管理和定时任务组件。
- 后端、前端测试和前端构建通过。
- README、API、部署文档、Postman Collection 更新完成。
- Wave 15 需求、计划和实现最终统一提交并推送。
