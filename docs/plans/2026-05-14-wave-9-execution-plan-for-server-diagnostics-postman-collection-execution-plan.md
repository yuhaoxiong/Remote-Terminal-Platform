# Wave 9 执行计划：服务器诊断、Postman、frps 运维化与设备级凭据

## 运行时信息

- Vibe run id: `20260514T062303Z-85cabfc7`
- 阶段: `xl_plan`
- 需求文档: `docs/requirements/2026-05-14-generate-wave-9-requirement-document-for-remote-terminal-platfor.md`
- 计划状态: 待审批

## 冻结范围

本轮只实现以下能力：

1. 服务器部署诊断与 Nginx 单域名反向代理验收说明。
2. 仓库内 Postman Collection 或生成脚本，支持登录后自动保存 Token 并注入受保护接口。
3. frps 导入从一次性导入升级为可重复同步、冲突诊断和覆盖策略。
4. 设备级 SSH 凭据字段：默认用户 `ztl`，默认密码 `123456`，本轮直接保存至数据库。
5. 前端中文 UI 与错误处理补齐：502/503/504 不清空登录态。

本轮不实现真实批量 SSH 命令执行；该能力顺延到后续 Wave。

## 执行波次

### Wave 9.0：现状基线与兼容点确认

目标：在动代码前确认当前模型、接口、前端状态管理和测试入口。

执行项：

- 阅读设备模型、schema、设备 CRUD、frps 导入服务、鉴权拦截器、前端设备表单和当前 README/API 文档。
- 确认旧 SQLite 自动迁移位置，避免服务器旧库启动失败。
- 确认前端 401/403 与 502/503/504 的错误分流位置。

预期改动：无业务改动，只形成实现定位。

验证：

- 不运行全量测试，只记录相关文件和决策。

### Wave 9.1：后端诊断与健康检查增强

目标：让服务器 API 502 排查有可调用的后端诊断基础。

后端改动：

- 扩展 `/api/health`，返回服务名、版本、数据库连接状态。
- 新增受保护或半公开诊断接口，建议 `/api/diagnostics/config`：
  - API 前缀
  - 数据库类型或路径摘要
  - 文件后端
  - 远程 SSH 网关主机
  - VNC 网关主机
  - SSH/VNC 超时时间
  - 不返回密码、Token、私钥内容。
- 增加诊断服务单元测试。

前端改动：

- API 502/503/504 显示中文“后端服务不可达或代理配置错误”。
- 保持登录态；只有 401/403 清空登录态并回登录页。

文档改动：

- README 或 `docs/deployment.md` 增加 Nginx 单域名反代排查步骤：
  - 后端直连 `/api/health`
  - Nginx `/api/health`
  - `/api/ws` WebSocket 转发配置
  - `ss -lntp`、`systemctl status`、Nginx 日志位置。

验证：

- 后端测试覆盖健康检查与配置摘要脱敏。
- 前端测试覆盖 502 不退出登录。

### Wave 9.2：设备级 SSH 凭据字段

目标：让设备可以保存自己的 SSH 用户和密码，为后续真实 SSH 执行打基础。

后端改动：

- 扩展设备模型和 schema：
  - `ssh_user` 默认 `ztl`
  - `ssh_auth_type` 默认 `password`
  - `ssh_password` 默认 `123456`
  - `ssh_credential_configured` 或等效只读字段，用于前端显示是否已配置。
- 旧数据库自动迁移新增字段，并给旧设备补默认值。
- 设备创建/更新接口允许写入凭据字段。
- 设备读取接口不得返回明文密码；如需要更新密码，使用写入字段但响应脱敏。
- frps 新设备导入默认写入 `ssh_user=ztl`、`ssh_password=123456`。
- frps 同步已有设备时不得覆盖已配置凭据。

前端改动：

- 设备创建/编辑表单新增：
  - SSH 用户
  - 凭据类型
  - SSH 密码密码框
  - 凭据已配置状态展示
- 设备列表/详情不展示明文密码。

文档改动：

- `docs/api.md` 更新设备字段说明。
- README 说明本轮密码暂存数据库，后续再做加密保存；生产环境需修改默认密码。

验证：

- 后端测试覆盖新建、更新、读取脱敏、旧库迁移、frps 导入默认值。
- 前端测试覆盖表单字段和敏感值不回显。

### Wave 9.3：frps 运维化同步

目标：让 frps 导入支持重复同步、状态分类、冲突诊断和显式覆盖。

后端改动：

- 扩展 frps 预览结果状态：
  - `new`
  - `existing`
  - `conflict`
  - `missing_vnc`
  - `offline`
  - `skipped`
- 扩展导入请求参数：
  - `overwrite_project_location: boolean`
- 预览时按 `device_sn`、SSH 端口、VNC 端口识别已有设备和冲突。
- 导入时：
  - 新设备创建。
  - 已存在设备同步在线状态、代理名称和标签。
  - 只有 `overwrite_project_location=true` 时覆盖项目号和部署位置。
  - 不覆盖设备级凭据。
- 操作日志记录发现、新增、同步、跳过、冲突、失败数量。

前端改动：

- frps 导入面板增加“覆盖项目号和部署位置”开关。
- 导入/预览结果以中文表格展示每个代理状态、端口、设备 SN、处理结果和错误原因。
- Dashboard 认证失败、不可达、超时均显示中文错误，并保留表单输入。

文档改动：

- `docs/api.md` 更新 frps discover/import 请求和响应。
- README 更新 frps 运维同步说明。

验证：

- 后端测试覆盖新设备、已有设备、端口冲突、缺失 VNC、离线代理、覆盖与不覆盖策略。
- 前端测试覆盖表格结果、覆盖开关和错误提示。

### Wave 9.4：Postman Collection 入仓

目标：让 API 验收不依赖下载目录中的临时 JSON。

交付方式：

- 新增 `docs/postman/edge-platform.postman_collection.json`。
- 可选新增生成脚本；若脚本成本过高，本轮可提交静态 Collection，并在后续再生成化。

Collection 要求：

- 集合变量：
  - `base_url`
  - `username`
  - `password`
  - `access_token`
  - `refresh_token`
- 集合级 Bearer Token 使用 `{{access_token}}`。
- 登录接口 Tests：
  - 保存 `access_token`
  - 保存 `refresh_token`
- 刷新 Token 接口 Tests：
  - 更新 `access_token`
  - 更新 `refresh_token`
- 健康检查、登录、刷新 Token 不带鉴权。
- 最小回归分组包含：
  - 健康检查
  - 登录
  - 当前用户
  - 设备列表
  - frps 预览
  - 监控概览
  - 日志列表

文档改动：

- README 增加 Postman 使用流程。
- `docs/api.md` 增加常见错误：
  - 把脚本放到 Pre-request Script 导致 `pm.response` 为空。
  - 未先运行登录接口导致 Bearer Token 为空。

验证：

- 使用 JSON 解析脚本校验 Collection schema、变量、登录 Tests 和集合级 auth。

### Wave 9.5：Nginx 单域名部署文档与配置样例

目标：让服务器测试路径从 Vite dev server 收敛到 Nginx 单域名。

文档/资产改动：

- 更新 `docs/deployment.md`：
  - 前端 `npm run build`
  - Nginx 静态站点根目录
  - `/api/` 反向代理到 `127.0.0.1:8000`
  - `/api/ws/` WebSocket upgrade 代理
  - 502 排查顺序
  - systemd 后端服务示例
- 如已有部署脚本，补充 Nginx 示例配置文件或模板。

验证：

- 文档命令可读、路径一致、端口一致。
- 不要求本地实际启动 Nginx，但必须提供服务器手工验收清单。

### Wave 9.6：文档、测试与回归收口

目标：保证本轮变更可验收、可回归。

验证命令：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
py -3.12 -m pytest tests --basetemp C:\01_work\02_program\远程终端平台\.pytest-tmp

cd C:\01_work\02_program\远程终端平台\frontend
npm test -- --run
npm run build
```

如本机 Python/Node 版本与服务器不一致，需记录实际可运行命令和失败原因。

手工验收清单：

- 服务器后端直连：`curl http://127.0.0.1:8000/api/health`
- Nginx 入口：`curl http://<域名或IP>/api/health`
- Postman：先登录，再访问设备列表。
- frps：预览、导入、重复同步、覆盖项目号/位置。
- 前端：502 不退出登录；401/403 才退出登录。

## 文件影响范围

预计修改：

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models/device.py`
- `backend/app/schemas/device.py`
- `backend/app/services/device_service.py`
- `backend/app/services/frps_import.py`
- `backend/app/routers/devices.py`
- `backend/app/routers/frps.py`
- `backend/tests/*`
- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`
- `docs/api.md`
- `docs/deployment.md`
- `README.md`

预计新增：

- `backend/app/routers/diagnostics.py` 或等效诊断路由
- `backend/app/schemas/diagnostics.py` 或等效 schema
- `backend/tests/test_diagnostics_api.py`
- `backend/tests/test_device_credentials_api.py`
- `docs/postman/edge-platform.postman_collection.json`
- 可选：`scripts/deploy/nginx-edge-platform.conf`

## 风险与约束

- 本轮明确允许密码 `123456` 直接存数据库，但文档必须标注这是临时方案。
- 响应和日志不得返回明文密码。
- frps 覆盖项目号/位置必须由用户显式选择，不得默认覆盖。
- 旧 SQLite 数据库迁移是硬要求。
- 真实批量 SSH 执行不纳入本轮，避免扩大范围。

## 审批条件

批准本计划后，进入 Wave 9 实现阶段。实现阶段必须按上述波次推进，先做后端测试和迁移，再接前端和文档，最后运行后端、前端测试与构建。
