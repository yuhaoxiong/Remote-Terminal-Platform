# Wave 14 需求文档：远程连接体验产品化

> 阶段：`requirement_doc`  
> 状态：已确认，下一步进入执行计划  
> 基线：Wave 13 已完成监控指标可观测性，当前远程 SSH/VNC 已具备后端 WebSocket 基础代理和前端会话入口，但还不是完整可操作体验。

## 1. 背景

平台当前已经具备以下远程连接基础：

- 设备记录中包含 SSH/VNC frp 代理端口。
- 后端已提供远程会话描述接口：
  - `POST /api/devices/{device_id}/remote/ssh`
  - `POST /api/devices/{device_id}/remote/vnc`
- 后端已存在 WebSocket 端点：
  - `/api/ws/devices/{device_id}/ssh?token=<access_token>`
  - `/api/ws/devices/{device_id}/vnc?token=<access_token>`
- 前端“远程连接”页面可以请求 SSH/VNC 会话描述，并展示连接状态。
- Wave 13 已验证前端登录态和局部接口失败不会轻易闪退回登录页。

当前不足：

- SSH 页面还不是完整终端 UI，缺少成熟的输入、输出、光标、resize 和断开体验。
- VNC 页面还没有嵌入 noVNC 画面，无法直接在平台内进行图形远程操作。
- 远程连接状态、失败原因和断开行为缺少清晰产品化展示。
- 远程会话审计仍偏弱，不利于后续排查连接失败、误操作和设备可达性问题。

Wave 14 的目标是把已有远程代理能力产品化，形成管理员可实际使用的 SSH 终端和 VNC 画面入口。

## 2. 目标

管理员登录后，应能在“远程连接”页面完成以下操作：

1. 从左侧设备列表选择一台设备。
2. 在右侧打开 SSH 终端，看到连接状态、终端输出，并能输入命令。
3. 终端窗口尺寸变化时，向后端上报 resize 信息。
4. 能主动断开 SSH 会话，并看到断开状态。
5. 在右侧打开 VNC 画面，能连接、断开，并进入可视化远程桌面。
6. 连接失败时展示明确中文失败原因，不导致页面退出登录，除非后端返回 401/403。
7. 远程连接成功、失败、断开等关键动作写入操作日志。

## 3. 非目标

本轮不实现以下内容：

- 不实现多标签页同时连接多个 SSH/VNC 会话。
- 不实现完整会话录屏、终端录像或命令审计回放。
- 不记录终端输入内容、密码、Token、私钥或完整屏幕内容。
- 不实现 VNC 剪贴板同步、文件拖拽、远程分辨率自动调整等高级功能。
- 不新增 RBAC 或多用户会话隔离。
- 不重构整站路由或引入新的全局状态管理。
- 不要求所有服务器环境都具备真实可达 VNC 设备；允许用 mock WebSocket 和可达 SSH 设备完成自动化与手工验收。

## 4. 功能需求

### 4.1 远程连接页面布局

前端“远程连接”页面改为更适合操作的布局：

- 左侧：设备列表。
  - 显示设备名称、项目号、状态、SSH/VNC 端口。
  - 支持按名称、序列号、项目号搜索。
  - 明确标识无法远程连接的设备，例如缺少 SSH/VNC 端口或凭据未配置。
- 右侧：远程操作区。
  - 顶部显示当前设备、连接类型、连接状态和操作按钮。
  - 中间根据模式显示 SSH 终端或 VNC 画面。
  - 底部或侧边显示最近状态消息。

页面必须保持中文显示。

### 4.2 SSH 终端体验

建议引入 `xterm` 和 `@xterm/addon-fit`。

SSH 终端需要支持：

- 点击“连接 SSH”后调用 `POST /api/devices/{id}/remote/ssh`。
- 使用返回的 `websocket_url` 拼接 access token 建立 WebSocket。
- WebSocket 连接成功后展示终端。
- 后端 `output` 消息写入终端。
- 用户键盘输入发送到后端。
- 支持窗口 resize：
  - 终端容器尺寸变化后调用 fit。
  - 向后端发送 `{ "type": "resize", "columns": N, "rows": M }`。
- 支持主动断开：
  - 发送 close 消息或关闭 WebSocket。
  - UI 显示“已断开”。
- 连接失败时显示中文错误，例如“SSH WebSocket 连接失败”“无法创建 SSH 会话”。

### 4.3 VNC 画面体验

建议引入 `@novnc/novnc`。

VNC 画面需要支持：

- 点击“连接 VNC”后调用 `POST /api/devices/{id}/remote/vnc`。
- 使用返回的 `websocket_url` 拼接 access token 建立 noVNC 连接。
- 在页面内渲染 VNC 画面容器。
- 支持主动断开。
- 支持“全屏”入口：
  - 优先使用浏览器 Fullscreen API。
  - 不支持时显示中文提示。
- 连接失败时显示中文错误，不影响其他页面。

### 4.4 远程会话状态管理

前端需要区分以下状态：

- `idle`：未连接。
- `connecting`：正在创建会话或连接 WebSocket。
- `ready`：会话描述已创建，等待 WebSocket 建立。
- `connected`：已连接。
- `failed`：连接失败。
- `disconnected`：已断开。

状态展示要求：

- 每个状态都有中文文案。
- 失败状态保留最近错误原因。
- 断开后允许重新连接。
- SSH 和 VNC 状态互不覆盖。

### 4.5 操作日志审计

后端需要复核并补齐远程会话相关操作日志。

必须记录：

- 创建 SSH 会话请求。
- 创建 VNC 会话请求。
- 后端无法创建会话的失败原因摘要。
- WebSocket 认证失败或连接失败时的安全摘要。
- 主动断开可由前端本地日志提示；如后端可识别断开事件，则记录服务端日志。

不得记录：

- 设备 SSH 密码。
- access token / refresh token。
- 私钥内容。
- 终端完整输入内容。
- VNC 画面内容。

### 4.6 鉴权与错误处理

- REST 远程会话接口继续使用 Bearer Token。
- WebSocket 继续使用 `?token=<access_token>`。
- 401/403 视为登录失效，清理 token 并回到登录页。
- 502/503/504 或网络错误视为远程代理/后端不可达，只显示局部错误。
- SSH/VNC 失败不能影响仪表盘、设备管理、批量任务等其他页面。

### 4.7 中文显示

新增或调整的前端文案必须全部为中文，包括：

- 连接按钮。
- 状态标签。
- 错误提示。
- 空状态。
- 测试断言中的可见文本。

## 5. 后端需求

后端以复核和小幅增强为主。

必须保持：

- `POST /api/devices/{device_id}/remote/ssh` 返回 SSH 会话描述。
- `POST /api/devices/{device_id}/remote/vnc` 返回 VNC 会话描述。
- `/api/ws/devices/{device_id}/ssh` 校验 token。
- `/api/ws/devices/{device_id}/vnc` 校验 token。

需要补齐或确认：

- 缺少端口、设备不存在、凭据不可用时返回明确错误。
- WebSocket 关闭时后端不泄漏异常堆栈到前端。
- SSH resize 消息能被后端接受并传递给 SSH channel。
- 操作日志覆盖会话创建成功与失败。

如果当前后端已经满足部分行为，本轮只补测试和必要修复。

## 6. 前端需求

### 6.1 依赖

建议新增：

- `xterm`
- `@xterm/addon-fit`
- `@novnc/novnc`

构建后必须记录 bundle 体积变化和是否出现 chunk warning。当前项目已经因 Element Plus 和 ECharts 存在大 chunk warning，本轮不要求彻底拆包，但不能引入运行时报错。

### 6.2 API 与 WebSocket

沿用已有 API：

- `openSshSession(deviceId)`
- `openVncSession(deviceId)`
- `buildApiWebSocketUrl(path, token)`

需要补齐：

- SSH 终端输入到 WebSocket 的消息格式。
- SSH resize 消息格式。
- VNC noVNC 连接创建和断开封装。

### 6.3 交互约束

- 未选择设备时显示“请选择设备”。
- 设备无 SSH 端口时禁用 SSH 连接按钮。
- 设备无 VNC 端口时禁用 VNC 连接按钮。
- 凭据未配置时显示“凭据未配置”，但不展示密码。
- 连接中按钮显示 loading。
- 已连接后显示断开按钮。

## 7. 测试需求

### 7.1 后端测试

至少运行现有：

- `backend/tests/test_wave8_remote_websockets.py`
- `backend/tests/test_remote_access_api.py`
- 后端全量 pytest

如修改后端，必须新增或调整测试覆盖：

- 缺少端口时创建会话失败。
- WebSocket token 缺失或无效。
- SSH resize 消息处理。
- 远程会话操作日志。

### 7.2 前端测试

在 `frontend/src/__tests__/app.spec.ts` 或新的远程页测试中覆盖：

- 远程页左侧设备列表展示中文设备信息。
- 点击 SSH 连接后调用会话接口并建立 WebSocket。
- SSH 输出消息写入终端区域。
- 用户输入会发送 WebSocket 消息。
- 点击断开会关闭 WebSocket 并显示“已断开”。
- 点击 VNC 连接后创建 noVNC 客户端。
- SSH/VNC 连接失败时显示中文错误，并保持登录后的页面。

### 7.3 构建验证

必须运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave14'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

建议额外做浏览器冒烟：

- 打开登录页确认非空白。
- 登录后进入“远程连接”。
- 选择一台设备，确认 SSH/VNC 操作区可见。

## 8. 文档与 Postman

需要更新：

- `README.md`
  - 补充 Wave 14 远程连接体验说明。
- `docs/api.md`
  - 明确 SSH/VNC REST 与 WebSocket 连接流程。
- `docs/deployment.md`
  - 补充 Nginx WebSocket 代理、SSH/VNC 端口、防火墙和 frps 可达性排查。
- `docs/postman/edge-platform.postman_collection.json`
  - 增加创建 SSH 会话、创建 VNC 会话请求。
  - WebSocket 仍以文档说明为主，Postman Collection 不强制覆盖 WebSocket 交互。

## 9. 验收标准

Wave 14 完成后必须满足：

- 远程连接页能展示可选择设备列表和当前设备详情。
- SSH 终端能显示输出、接收输入、断开并重连。
- VNC 画面能在页面中建立连接并断开。
- SSH/VNC 失败只影响远程连接区域，不导致登录闪退。
- 远程会话关键动作有操作日志或清晰本地状态记录。
- 新增文案为中文。
- 后端测试、前端测试和前端构建通过。
- 文档和 Postman 更新完成。

## 10. 风险与约束

- noVNC 和 xterm 会增加前端 bundle 体积，可能继续触发 Vite chunk warning。
- 真实 VNC 验收依赖设备端 VNC 服务、frpc、frps、防火墙和 Nginx WebSocket 代理都配置正确。
- 真实 SSH 验收依赖设备 SSH 凭据可用；不得在前端暴露明文凭据。
- WebSocket 的自动化测试需要 mock `WebSocket`、`ResizeObserver`、xterm/noVNC，避免依赖真实设备。

## 11. 已确认决策

1. 批准引入 `xterm`、`@xterm/addon-fit`、`@novnc/novnc`。
2. VNC 本轮只做内嵌连接、断开、全屏，不做剪贴板和文件拖拽。
3. SSH/VNC 真实设备手工验收继续使用已导入的 frps 设备。
4. 若构建继续出现大 chunk warning，本轮只记录风险，暂不做拆包优化。
