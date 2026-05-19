# Wave 14 执行计划：远程连接体验产品化

> 阶段：`xl_plan`  
> 状态：待确认，确认后进入实现  
> 冻结需求：`docs/requirements/2026-05-18-wave-14-remote-connection-experience.md`

## 1. 执行目标

本轮围绕“管理员可以真实使用远程连接页完成 SSH/VNC 操作”推进，重点把现有后端远程会话能力和前端入口产品化。

完成后应达到：

- 远程连接页可以从设备列表选择设备，并清楚展示 SSH/VNC 可用状态。
- SSH 使用 xterm 渲染终端，支持输出、输入、resize、断开和重连。
- VNC 使用 noVNC 内嵌画面，支持连接、断开和全屏。
- SSH/VNC 失败只影响远程连接区域，不触发非 401/403 的登录态清理。
- 后端远程会话创建、失败和关键连接事件有日志或测试覆盖，不记录敏感内容。
- README、接口文档、部署文档和 Postman Collection 与新能力保持一致。

## 2. 冻结决策

1. 批准引入 `xterm`、`@xterm/addon-fit`、`@novnc/novnc`。
2. VNC 本轮只做内嵌连接、断开、全屏，不做剪贴板和文件拖拽。
3. SSH/VNC 真实设备手工验收继续使用已导入的 frps 设备。
4. 若构建继续出现大 chunk warning，本轮只记录风险，暂不做拆包优化。

## 3. 工作拆分

### Step 1：基线审计与失败优先测试

- 阅读并记录当前远程连接相关代码：
  - `frontend/src/App.vue`
  - `frontend/src/api/platform.ts`
  - `backend/app/routers/devices.py`
  - `backend/app/services/remote_access.py`
  - `backend/app/websockets/devices.py`
  - `backend/app/services/ssh_service.py`
- 对照现有测试找 3 个以上可复用模式：
  - 前端页面交互测试模式。
  - API mock 与 WebSocket mock 模式。
  - 后端远程会话、鉴权、操作日志测试模式。
- 先补或调整失败优先测试：
  - SSH 连接会调用会话接口并建立 WebSocket。
  - SSH 输出会写入终端区域。
  - SSH 输入会发送 WebSocket 消息。
  - SSH resize 会发送 `{ "type": "resize", "columns": N, "rows": M }`。
  - SSH 断开会关闭 WebSocket 并显示中文断开状态。
  - VNC 连接会创建 noVNC 客户端。
  - SSH/VNC 失败展示中文局部错误，不回到登录页。

### Step 2：依赖引入与构建边界

- 在 `frontend` 引入：
  - `xterm`
  - `@xterm/addon-fit`
  - `@novnc/novnc`
- 更新 `package.json` 和 `package-lock.json`。
- 补齐测试 mock，避免单元测试依赖真实浏览器终端、真实 noVNC 或真实设备。
- 执行一次前端测试和构建，记录是否仍有大 chunk warning；若仅为体积警告，本轮记录风险，不做拆包。

### Step 3：后端远程会话加固

- 复核 REST 会话接口：
  - `POST /api/devices/{device_id}/remote/ssh`
  - `POST /api/devices/{device_id}/remote/vnc`
- 复核 WebSocket 端点：
  - `/api/ws/devices/{device_id}/ssh?token=<access_token>`
  - `/api/ws/devices/{device_id}/vnc?token=<access_token>`
- 补齐或确认以下行为：
  - 设备不存在、端口缺失、凭据不可用时返回明确中文或可被前端翻译的错误。
  - WebSocket token 缺失或无效时拒绝连接。
  - SSH resize 消息可以被接受并传递给 SSH channel。
  - 远程会话创建成功、创建失败、连接失败记录安全摘要。
  - 日志不记录 SSH 密码、token、私钥、完整终端输入、VNC 画面内容。

### Step 4：远程连接页产品化布局

- 将远程连接页整理为左侧设备列表、右侧操作区：
  - 左侧显示设备名称、项目号、状态、SSH/VNC 端口。
  - 支持按名称、序列号、项目号搜索。
  - 清楚标识缺少端口或凭据的设备。
  - 未选择设备时显示中文空状态。
- 右侧展示当前设备摘要、连接类型、连接状态和操作按钮。
- SSH/VNC 状态相互独立，状态枚举保持：
  - `idle`
  - `connecting`
  - `ready`
  - `connected`
  - `failed`
  - `disconnected`
- 新增和调整的前端文案全部使用中文。

### Step 5：SSH 终端集成

- 使用 `xterm` 和 `@xterm/addon-fit` 渲染 SSH 终端。
- 建立连接流程：
  - 点击连接按钮后调用 SSH 会话接口。
  - 使用返回的 `websocket_url` 和 access token 创建 WebSocket。
  - WebSocket 打开后设置为已连接。
  - 后端 `output` 消息写入终端。
- 输入与 resize：
  - 用户终端输入发送到 WebSocket。
  - 容器尺寸变化后执行 fit。
  - fit 后向后端发送 resize 消息。
- 断开与失败：
  - 主动断开关闭 WebSocket，并显示“已断开”。
  - WebSocket 错误显示中文错误，不清理登录态。
  - 组件卸载或切换设备时释放 terminal、fit addon、WebSocket。

### Step 6：VNC noVNC 集成

- 使用 `@novnc/novnc` 在页面容器内创建 VNC 客户端。
- 建立连接流程：
  - 点击连接按钮后调用 VNC 会话接口。
  - 使用返回的 `websocket_url` 和 access token 创建 noVNC 连接。
  - 监听连接、断开、失败事件并更新中文状态。
- 操作能力：
  - 支持主动断开。
  - 支持浏览器 Fullscreen API 全屏。
  - 浏览器不支持全屏时显示中文提示。
- 严格不实现剪贴板、文件拖拽和远程分辨率高级控制。
- 组件卸载或切换设备时释放 noVNC 客户端。

### Step 7：文档与 Postman

- 更新 `README.md`：
  - 补充 Wave 14 远程连接体验说明。
  - 标明 SSH/VNC 依赖 frps 代理、设备端口和凭据。
- 更新 `docs/api.md`：
  - 明确 SSH/VNC REST 与 WebSocket 连接流程。
  - 说明 WebSocket token 传递方式。
- 更新 `docs/deployment.md`：
  - 补充 Nginx WebSocket 反向代理注意事项。
  - 补充 SSH/VNC 端口、防火墙、frps 可达性排查。
- 更新 `docs/postman/edge-platform.postman_collection.json`：
  - 增加创建 SSH 会话请求。
  - 增加创建 VNC 会话请求。
  - WebSocket 交互以文档说明为主，不强制纳入 Collection 自动化。

### Step 8：验证与验收

- 后端验证：
  - 运行远程会话相关测试。
  - 运行全量后端 pytest。
- 前端验证：
  - 运行 Vitest。
  - 运行生产构建。
  - 记录 chunk warning 风险。
- 浏览器冒烟：
  - 打开登录页，确认非空白。
  - 登录后进入“远程连接”。
  - 选择设备，确认 SSH/VNC 操作区可见。
  - 若本地无真实可达设备，则使用 mock 自动化测试覆盖连接流程，真实连接留给服务器/frps 环境验收。

## 4. 验证命令

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave14'

Set-Location 'C:\01_work\02_program\远程终端平台\frontend'
npm.cmd test -- --run
npm.cmd run build
```

若只验证后端远程相关测试，先运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest backend\tests\test_wave8_remote_websockets.py backend\tests\test_remote_access_api.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave14-remote'
```

## 5. 风险与回滚

- `xterm` 和 `@novnc/novnc` 会增加前端 bundle 体积；若构建只有大 chunk warning，本轮记录风险并继续。
- noVNC 在单元测试环境需要 mock，否则可能依赖浏览器 API 导致测试不稳定。
- 真实 VNC 验收依赖设备端 VNC 服务、frpc、frps、防火墙、Nginx WebSocket 代理同时正确。
- 真实 SSH 验收依赖设备端凭据和代理端口可用；不得在前端显示或日志中记录明文凭据。
- 若新依赖导致构建不可恢复，回滚依赖与相关前端集成，保留后端加固和文档更新。

## 6. 完成定义

- 需求文档中 Wave 14 验收标准全部有实现、测试或明确人工验收路径。
- 后端远程会话接口和 WebSocket 行为通过测试。
- 前端远程连接页测试通过，覆盖 SSH/VNC 关键交互。
- 前端生产构建通过，chunk warning 已记录。
- README、接口文档、部署文档、Postman Collection 已更新。
- 工作树中 Wave 14 相关改动可以形成一次清晰提交。
