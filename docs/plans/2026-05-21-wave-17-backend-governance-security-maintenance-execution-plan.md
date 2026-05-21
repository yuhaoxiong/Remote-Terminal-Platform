# Wave 17 执行计划：后端治理、安全边界与长期维护

> 阶段：`xl_plan`  
> 状态：已完成，已通过验证  
> 冻结需求：`docs/requirements/2026-05-21-wave-17-backend-governance-security-maintenance.md`

## 1. 执行目标

Wave 17 不继续扩展大业务模块，而是把当前平台推进到更适合长期维护和生产测试的状态。

完成后应达到：

- 后端核心状态、类型和模式字段有统一枚举约束。
- Alembic 成为后续数据库结构变更的版本化入口，并兼容当前 SQLite 基线。
- 全局 Router 的 settings、session、错误处理和日志样板显著收敛。
- 后端测试开始使用统一 fixture/factory，减少重复构造数据。
- SSH 主机密钥策略支持 `auto_add|warning|reject`，默认保持 `auto_add`。
- 诊断接口和系统诊断页展示迁移、known_hosts、token 配置和安全摘要。
- 前端 access token 过期后自动 refresh，refresh 失败直接回登录页。
- 文档、Postman、后端测试、前端测试和构建同步完成。
- 需求、计划和实现测试完成后统一提交并推送。

## 2. 冻结决策

1. 数据库迁移治理引入 Alembic，不采用项目内最小迁移层。
2. SSH 主机密钥策略默认值保持 `auto_add`，仅通过诊断页和部署文档提示生产风险。
3. Router 收敛范围为全局 Router，不只覆盖少数高频模块。
4. Token 自动刷新失败后直接清理登录态并回登录页。
5. Wave 17 需求、计划和实现测试完成后统一提交并推送。

## 3. 总体执行策略

本轮改动范围较大，必须分批推进：

1. 先做基线审计和测试支架，避免后续大改无保护。
2. 再引入 Alembic，保证迁移入口和旧库兼容。
3. 然后收敛 Router 依赖和错误处理，每批改造后跑对应测试。
4. 再推进枚举约束、known_hosts 策略和诊断扩展。
5. 最后做前端 token refresh 和诊断页展示。
6. 统一更新文档/Postman，跑完整验收后再提交推送。

任何阶段出现 3 次连续失败，应停止并报告失败点、根因和替代方案。

## 4. 工作拆分

### Step 1：基线审计与模式确认

阅读并记录当前关键文件：

- `backend/app/database.py`
- `backend/app/dependencies.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/routers/*.py`
- `backend/app/schemas/*.py`
- `backend/app/models/*.py`
- `backend/app/services/ssh_service.py`
- `backend/app/services/encryption.py`
- `backend/tests/*.py`
- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`
- `docs/api.md`
- `docs/deployment.md`
- `docs/postman/edge-platform.postman_collection.json`

需要找出的既有模式：

- 当前测试如何初始化临时数据库和 settings。
- 当前认证测试如何登录和传递 Bearer token。
- 当前 router 如何处理 `session_scope`、service 和操作日志。
- 当前 diagnostics 如何暴露非敏感配置。
- 当前前端 axios 如何存储、注入、清理 token。
- 当前 SSH 服务如何创建 paramiko client。

产出：

- 不单独生成审计文档，但在实现中按现有模式落地。
- 若发现需求和现有代码冲突，先调整执行计划或向用户说明，不直接扩大范围。

### Step 2：后端测试 fixture/factory 先行

目标：先降低后续测试编写成本。

新增或整理测试支架，建议位置：

- `backend/tests/conftest.py`
- 如已有 conftest，则在原文件增量整理。

建议 fixture/factory：

- `auth_headers`
- `create_group`
- `create_device`
- `create_update_task`
- `fake_ssh_service`
- `session_scope` 辅助入口复用

要求：

- 不强制一次性迁移全部旧测试。
- 至少让 Wave 17 新增测试使用这些 fixture。
- 保持现有测试全部通过。

阶段测试：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave17-fixtures'
```

### Step 3：Alembic 迁移基线

目标：为后续数据库结构变更提供版本化入口。

新增：

- `backend/alembic.ini` 或项目适配等价配置。
- `backend/alembic/env.py`
- `backend/alembic/versions/<revision>_baseline.py`
- 迁移运行 helper，如有必要可放在 `backend/app/migrations.py`。

实现要求：

- Alembic 使用当前 SQLAlchemy `Base.metadata`。
- SQLite 数据库可执行 `upgrade head`。
- 空库可以通过 Alembic 创建当前核心表。
- 旧库可以在不丢数据的情况下标记或升级到基线版本。
- 当前 `init_db` 的 `create_all` 和兼容补列逻辑不应被粗暴删除；本轮应让 Alembic 与旧逻辑平滑共存。
- 测试环境必须能使用临时 SQLite 文件运行迁移。

诊断准备：

- 提供读取当前 Alembic revision 的服务函数。
- 若读取失败，返回非敏感错误摘要供 diagnostics 使用。

阶段测试：

- 空库迁移测试。
- 旧库兼容测试。
- 后端全量测试。

### Step 4：全局 Router 依赖收敛

目标：降低 router 中重复样板。

建议新增或扩展：

- `backend/app/dependencies.py`
  - `get_settings`
  - `get_db`
  - `get_services` 或按需 service factory
- `backend/app/routers/_helpers.py` 或类似文件
  - not found 转换
  - invalid state 转换
  - 操作日志 helper

改造范围：

- `auth`
- `devices`
- `groups`
- `frps`
- `remote`
- `update_tasks`
- `update_task_templates`
- `scheduled_tasks`
- `logs`
- `monitoring`
- `diagnostics`
- 文件相关 router

执行方式：

1. 先改造一组低风险 router，例如 diagnostics/logs。
2. 跑对应测试。
3. 再改造 devices/groups。
4. 跑设备和分组相关测试。
5. 再改造 update/scheduled/file/remote。
6. 跑后端全量测试。

要求：

- API 路径、请求体和响应结构保持兼容。
- 操作日志行为保持兼容。
- 异常状态码保持兼容。
- 不为了抽象而隐藏业务逻辑；helper 只处理横切样板。

### Step 5：枚举与 Schema 约束

目标：收敛自由字符串。

建议新增：

- `backend/app/enums.py` 或 `backend/app/domain/enums.py`

定义：

- `DeviceStatus`
- `SshAuthType`
- `UpdateTaskStatus`
- `UpdateTaskDeviceStatus`
- `ExecutionMode`
- `FailureStrategy`
- `FileBackend`
- `ScheduledTaskType` 或最小任务类型约束

改造范围：

- Pydantic schema 使用 Enum 或 Literal。
- 服务层使用统一常量，减少散落字符串。
- 前端类型保持现有 union，不强制本轮共享生成类型。

测试要求：

- 非法设备状态返回 `422`。
- 非法 SSH auth type 返回 `422`。
- 非法 execution mode 返回 `422`。
- 非法 failure strategy 返回 `422`。
- 旧数据中未知状态不导致列表接口 500。

阶段测试：

- 新增枚举测试。
- 后端全量测试。
- 前端测试，确认响应结构未破坏。

### Step 6：SSH known_hosts 策略

目标：给生产环境明确 SSH 主机密钥边界。

配置新增：

```text
SSH_KNOWN_HOSTS_FILE=
SSH_HOST_KEY_POLICY=auto_add
```

策略：

- `auto_add`：默认值，保持当前兼容行为。
- `warning`：允许连接，但诊断页提示风险。
- `reject`：未知主机密钥拒绝连接。

实现位置：

- `backend/app/config.py`
- `backend/app/services/ssh_service.py`
- `backend/app/routers/diagnostics.py`
- 对应 schema 和前端类型

测试：

- 默认策略为 `auto_add`。
- `warning` 策略不阻止连接，但 diagnostics 有 warning。
- `reject` 策略配置进入 SSH client 行为。
- 不暴露 known_hosts 文件内容。

### Step 7：诊断接口与系统诊断页扩展

后端诊断新增摘要：

- migration：
  - current_revision
  - head_revision
  - has_pending_migrations
  - last_error
- ssh_host_key：
  - policy
  - known_hosts_configured
  - warnings
- token：
  - access_token_expire_minutes
  - refresh_token_expire_minutes
  - jwt_secret_configured
- database：
  - database_summary
  - sqlite_backup_recommended

前端系统诊断页新增展示：

- 迁移状态卡片。
- SSH 主机密钥策略卡片。
- Token 配置卡片。
- 数据库/备份提醒。

要求：

- 中文文案。
- 不显示密钥、密码、token、私钥内容。
- 诊断接口失败不导致登录退出，除非 REST 返回 401/403 且 refresh 失败。

### Step 8：前端 Token 自动刷新

目标：让长时间使用更稳定。

改造位置：

- `frontend/src/api/platform.ts`
- `frontend/src/__tests__/app.spec.ts`

实现要求：

- axios response interceptor 捕获 `401`。
- 排除 `/auth/login` 和 `/auth/refresh` 自身。
- 使用 refresh token 调 `POST /api/auth/refresh`。
- 成功后保存新 token 并重放原请求。
- 并发多个 `401` 时只发起一次 refresh，其它请求等待同一个刷新 Promise。
- refresh 失败后调用 `clearAuthTokens` 并让页面回到登录页。
- `403` 不刷新。
- WebSocket 错误不触发 refresh。

测试：

- access token 过期后 refresh 成功并重放请求。
- refresh 失败后回登录页。
- 并发 `401` 只调用一次 refresh。
- WebSocket 错误不清理登录态。

### Step 9：文档与 Postman 更新

更新：

- `README.md`
  - Wave 17 能力说明。
  - Alembic 迁移命令。
  - known_hosts 策略说明。
- `docs/api.md`
  - 诊断接口新增字段。
  - token refresh 行为。
  - 枚举字段约束。
- `docs/deployment.md`
  - Alembic 迁移执行顺序。
  - SQLite 备份和升级注意事项。
  - known_hosts 生产建议。
  - JWT 和凭据密钥要求。
- `docs/postman/edge-platform.postman_collection.json`
  - 确认刷新 token 请求可验收。
  - 诊断接口响应说明补充。

### Step 10：全量验收与统一提交推送

必须执行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave17-full'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build

cd C:\01_work\02_program\远程终端平台
git diff --check
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman json ok')"
```

清理：

- 删除 `.pytest-tmp-wave17-*` 临时目录。
- 不删除用户已有数据、日志或非本轮文件。

提交：

- 需求、计划和实现测试完成后统一提交。
- 建议提交信息：

```text
Implement Wave 17 backend governance
```

- 推送当前分支到远端。

## 5. 文件级影响预估

后端可能新增/修改：

- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/*.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/dependencies.py`
- `backend/app/enums.py`
- `backend/app/main.py`
- `backend/app/routers/*.py`
- `backend/app/schemas/*.py`
- `backend/app/services/ssh_service.py`
- `backend/app/services/diagnostics` 或现有 diagnostics router/service
- `backend/tests/conftest.py`
- 新增 Wave17 测试文件

前端可能新增/修改：

- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`
- 视情况拆出诊断页组件，但不强制。

文档：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/postman/edge-platform.postman_collection.json`
- 本执行计划
- Wave17 需求文档

## 6. 风险控制

- Alembic 风险：先让迁移在空库和旧库上通过，再接入应用启动或部署文档。
- 全局 Router 收敛风险：分批改造，每批跑测试，避免一次性失控。
- 枚举约束风险：对请求严格，对旧数据兼容，避免历史脏数据导致 500。
- Token refresh 风险：排除刷新接口自身，使用单 flight Promise 避免刷新风暴。
- known_hosts 风险：默认保持 `auto_add`，生产风险通过诊断和文档显式提示。

## 7. 验收标准映射

- Alembic 在空库/旧库上可运行：Step 3。
- 全局 Router 依赖收敛：Step 4。
- 枚举非法值校验：Step 5。
- known_hosts 策略和诊断：Step 6、Step 7。
- Token 自动刷新：Step 8。
- 文档/Postman：Step 9。
- 后端、前端、构建、diff 和 JSON 验证：Step 10。

## 8. 下一步

本计划确认后进入 Wave 17 实现阶段。实现阶段必须按上述步骤小步推进，测试完成后统一提交并推送。
