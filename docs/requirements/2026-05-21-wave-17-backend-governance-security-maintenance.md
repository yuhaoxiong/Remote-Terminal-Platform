# Wave 17 需求文档：后端治理、安全边界与长期维护

> 阶段：`requirement_doc`  
> 状态：已确认，执行计划已批准  
> 基线：Wave 16 已完成批量任务安全增强与设备选择器，平台核心业务功能已经可用。下一阶段应优先降低长期维护风险，补齐安全边界、迁移治理、测试治理和登录态稳定性，而不是继续堆叠大模块。

## 1. 背景

平台截至 Wave 16 已经具备以下能力：

- 管理员登录、JWT access/refresh token、修改密码。
- 设备 CRUD、分组、标签、frps Dashboard 导入、设备级 SSH 凭据和凭据加密。
- 远程 SSH/VNC WebSocket、xterm 终端和 noVNC 画面入口。
- 设备指标、监控总览、系统诊断和操作日志。
- 批量更新任务：目标预览、命令模板、dry-run、真实 SSH 执行、失败设备重试入口、结果 CSV 导出和 WebSocket 快照。
- 设备文件管理和定时任务 API 管理闭环。
- README、API 文档、部署文档和 Postman Collection。

当前主要风险已经从“功能缺失”转为“长期维护和生产边界不足”：

- Schema 约束偏松，部分状态、类型、模式仍以字符串自由传递。
- Router 中重复出现 `get_app_settings + session_scope + service + log` 的样板逻辑。
- 数据库结构演进仍依赖 `create_all` 和手写 SQLite 补列，后续继续扩展会变得不可控。
- 测试中重复构造用户、设备、分组、任务，新增功能时容易复制旧模式。
- SSH 主机密钥策略仍偏开发友好，生产环境缺少 `known_hosts` 明确边界。
- 前端 access token 过期后的处理仍偏直接退出，长时间使用时体验不稳定。

Wave 17 的目标是先治理这些基础问题，为后续真实调度器、告警、多用户权限和资产生命周期打地基。

## 2. 目标

Wave 17 完成后，系统应达到以下状态：

1. 后端核心枚举字段有统一约束，非法值能稳定返回 `422` 或明确错误。
2. Router 层重复样板逻辑减少，新增接口可以复用统一依赖和错误处理模式。
3. 数据库结构变更开始进入版本化迁移流程，后续新增表/列不再只依赖手写补列。
4. 测试 fixture 和 factory 更集中，后续新增后端测试不需要重复复制认证和数据准备逻辑。
5. SSH 主机密钥策略有开发/生产区分，诊断页能提示生产风险。
6. 前端遇到 access token 过期时优先自动 refresh，refresh 失败才清理登录态。
7. 文档明确生产部署下 JWT、凭据加密、known_hosts、迁移和备份的最低要求。

## 3. 非目标

本轮不实现以下内容：

- 不实现多用户 RBAC、项目级权限、审计审批流。
- 不实现告警规则、Webhook、邮件通知或事件中心。
- 不实现真实后台定时调度器，Wave 15 的定时任务仍保持 API 管理闭环。
- 不切换数据库到 PostgreSQL；本轮仍以 SQLite 兼容为主。
- 不重写全部 Router，不做大规模架构搬迁。
- 不引入 Pinia、Vue Router 全量页面化或前端整体重构。
- 不强制生产环境拒绝启动，但必须通过诊断和文档给出清晰 warning。
- 不改变现有 API 的成功响应结构，除非是增加向后兼容字段。

## 4. 功能需求

### 4.1 后端枚举与 Schema 约束

需要统一梳理当前后端中的自由字符串字段，并逐步收敛为 `Literal`、`Enum` 或共享常量。

优先字段：

- 设备状态：
  - `online`
  - `offline`
  - `degraded`
  - `unknown`
- SSH 认证类型：
  - `password`
  - `key`
- 更新任务状态：
  - `pending`
  - `running`
  - `completed`
  - `canceled`
  - `partial_failed`
- 更新任务设备状态：
  - `pending`
  - `running`
  - `success`
  - `failed`
  - `skipped`
  - `canceled`
  - `completed`
- 更新执行模式：
  - `dry_run`
  - `ssh_command`
- 失败策略：
  - `continue`
  - `pause`
  - `rollback`
- 文件后端：
  - `local`
  - `sftp`
- 定时任务启停状态和任务类型。

要求：

- 请求 Schema 对非法枚举值返回 `422`。
- 响应 Schema 保持现有字段名，不破坏前端。
- 数据库中旧值如存在未知值，不应导致列表接口整体崩溃；应在服务层做兼容或迁移策略。
- 枚举定义应集中放置，避免各 Schema 重复硬编码。

### 4.2 Router 依赖和错误处理收敛

当前多个 router 重复执行：

- 从 request 取 settings。
- 打开 `session_scope(settings)`。
- 构造 service。
- 捕获 NotFound / InvalidState。
- 写操作日志。

本轮需要设计一个轻量收敛方案。

建议方向：

- 新增数据库 session 依赖，例如 `get_db_session` 或类似封装。
- 保留现有 `session_scope` 行为，避免一次性重写所有事务。
- 提供统一错误转换工具：
  - not found -> `404`
  - invalid state -> `409`
  - validation -> `422`
- 操作日志保留显式调用，不做过度魔法化，但允许提取小型 helper。

优先改造范围：

- `devices`
- `groups`
- `update_tasks`
- `update_task_templates`
- `scheduled_tasks`
- `logs`
- `diagnostics`

要求：

- 改造后行为不变。
- 已有测试继续通过。
- 每次改造应小步推进，避免一次性全局重写导致回归定位困难。

### 4.3 数据库迁移治理

当前系统使用 SQLite，并通过 SQLAlchemy `create_all` 和手写补列兼容旧库。Wave 17 需要引入可持续迁移策略。

本轮确认引入 Alembic 作为版本化迁移方案。

最低要求：

- 新增迁移版本表，记录已执行迁移版本。
- 现有数据库可无损升级。
- 当前已有的自动补列逻辑保留兼容，但新增结构变更必须有迁移脚本。
- 迁移执行应在应用启动或部署脚本中有明确入口。
- Alembic 配置和迁移脚本必须适配当前 SQLite 开发/测试基线。
- 诊断接口能返回迁移摘要：
  - 当前迁移版本
  - 是否存在待执行迁移
  - 最近一次迁移状态
- 需要补充 `alembic.ini` 或等价配置。
- 文档说明 SQLite 下的迁移限制。
- 迁移失败不得静默吞掉，应记录清晰错误。

### 4.4 测试 fixture 与 factory 收敛

后端测试需要减少重复样板。

需要新增或整理：

- 认证 fixture：
  - 创建管理员
  - 登录
  - 返回 auth headers
- 设备 factory：
  - 默认在线设备
  - 缺少 SSH 端口设备
  - 缺少凭据设备
  - 带分组/标签设备
- 分组 factory。
- 更新任务 factory。
- fake SSH service fixture。
- 临时数据库 fixture 与 settings fixture 的边界说明。

要求：

- 优先迁移新增测试和高重复测试，不要求一次性重写全部历史测试。
- fixture 命名清晰，避免测试可读性下降。
- 保持 Windows 中文路径下 pytest 可运行。

### 4.5 SSH known_hosts 与主机密钥策略

当前 SSH 连接更偏开发测试。生产环境应支持更明确的主机密钥校验策略。

新增配置建议：

```text
SSH_KNOWN_HOSTS_FILE=/path/to/known_hosts
SSH_HOST_KEY_POLICY=auto_add|reject|warning
```

语义：

- `auto_add`：开发模式，自动接受未知主机密钥。
- `warning`：允许连接，但诊断页提示生产风险。
- `reject`：未知主机密钥拒绝连接。

要求：

- 默认值确认保持 `auto_add`，避免现有测试和开发环境突然不可用。
- 诊断接口返回当前策略摘要，不返回私钥、密码或敏感路径内容之外的信息。
- 文档说明生产建议使用 `reject` 或至少 `warning`，并维护 known_hosts。
- 真实 SSH 执行和 Web SSH 都应复用同一策略。

### 4.6 前端 Token 自动刷新

当前前端已经保存 access token 和 refresh token。Wave 17 需要让 axios 在 access token 过期时优先刷新。

要求：

- REST 请求收到 `401` 时，如果本次请求不是刷新 token：
  1. 调用 `POST /api/auth/refresh`。
  2. 保存新的 access token 和 refresh token。
  3. 重放原请求。
- 同时多个请求遇到 `401` 时，应避免并发刷新风暴。
- refresh 失败时直接清理登录态并回到登录页。
- `403` 不自动刷新，按无权限/禁止访问处理。
- WebSocket 连接失败不触发全局退出；远程连接和更新任务 WebSocket 仍只在局部显示失败。

前端测试需要覆盖：

- access token 过期后 refresh 成功并重放请求。
- refresh 失败后清理登录态。
- 多请求同时 401 时只发起一次 refresh。
- 远程 WebSocket 错误不清理登录态。

### 4.7 诊断页与文档增强

诊断接口和前端系统诊断页需要补充治理状态。

新增诊断摘要：

- 迁移状态：
  - 当前版本
  - 是否有待执行迁移
  - 最近迁移结果
- SSH 主机密钥策略：
  - 当前 policy
  - 是否配置 known_hosts
  - 是否存在生产风险 warning
- Token 配置：
  - access token 过期分钟数
  - refresh token 过期分钟数
  - 是否仍使用默认 JWT secret
- 数据库摘要：
  - 数据库类型
  - SQLite 路径摘要
  - 备份建议 warning

要求：

- 不返回 JWT secret、Fernet key、SSH 密码、私钥内容或 refresh token。
- 前端展示中文文案。
- README、API 文档、部署文档同步更新。
- Postman Collection 增加诊断接口验收说明即可，不强制新增复杂脚本。

## 5. 安全要求

- 不在日志、诊断接口、导出文件、Postman 示例中输出明文设备密码、私钥、JWT secret、Fernet key 或 token。
- 自动 refresh token 时不得把 token 写入 URL。
- known_hosts 配置路径可以显示“已配置/未配置”，不应暴露文件内容。
- 迁移失败信息可以记录错误摘要，但不得输出敏感环境变量。
- 枚举收敛不得让旧数据导致接口 500；应优先返回兼容展示或给出迁移 warning。

## 6. 测试要求

后端测试：

- 枚举非法值返回 `422`。
- 旧数据兼容场景不导致列表接口崩溃。
- 数据库迁移可在空库和旧库上重复执行。
- 迁移状态进入诊断接口。
- known_hosts policy 在 `auto_add`、`warning`、`reject` 下行为符合预期。
- fixture/factory 被至少一组新测试实际使用。

前端测试：

- access token 过期后 refresh 成功。
- refresh 失败后回登录页。
- 并发 `401` 只触发一次 refresh。
- 诊断页展示迁移和 known_hosts 摘要。
- WebSocket 失败不触发全局退出登录。

回归测试：

- 后端全量 pytest。
- 前端 `npm test -- --run`。
- 前端 `npm run build`。
- `git diff --check`。

## 7. 文档与 Postman

需要更新：

- `README.md`
  - 增加 Wave 17 治理、安全边界和迁移说明。
- `docs/api.md`
  - 补充诊断接口新增字段。
  - 补充枚举字段约束说明。
  - 补充 token refresh 行为。
- `docs/deployment.md`
  - 补充迁移执行、known_hosts、JWT/凭据密钥和备份建议。
- `docs/postman/edge-platform.postman_collection.json`
  - 确认登录、刷新 token、诊断接口可用于 Wave 17 验收。

## 8. 验收标准

Wave 17 完成后必须满足：

- 非法枚举请求有稳定校验错误，不再被自由字符串悄悄写入。
- 全局 Router 使用统一依赖/错误处理模式，行为与旧接口兼容。
- Alembic 可在空库和旧库上执行。
- 诊断页能看到迁移、known_hosts、token、安全配置摘要。
- 前端 access token 过期可以自动 refresh，不影响用户继续使用。
- WebSocket 局部失败不会导致登录闪退。
- 后端全量测试、前端测试、构建均通过。
- 文档和 Postman 已同步。

## 9. 风险与约束

- 引入 Alembic 会改变部署和测试习惯，需要谨慎处理 SQLite 兼容。
- Router 依赖收敛容易扩大改动面，应分批迁移并持续跑测试。
- token refresh 涉及全局 axios 拦截器，容易引发循环刷新或重复请求，需要明确排除刷新接口自身。
- known_hosts 严格校验可能影响现有 frps SSH 测试，默认策略必须保持兼容。
- 枚举约束如果直接作用于旧数据，可能暴露历史脏数据，需要兼容策略。

## 10. 已确认决策

1. 数据库迁移治理引入 Alembic。
2. SSH 主机密钥策略默认值保持 `auto_add`，并在诊断页提示生产风险。
3. Router 收敛范围扩大为全局 Router 收敛，不只覆盖少数高频模块。
4. Token 自动刷新失败后直接清理登录态并回登录页。
5. Wave 17 需求、计划和实现测试完成后统一提交并推送。

## 11. 执行约束

1. 下一阶段先生成 Wave 17 执行计划，不直接进入代码实现。
2. 全局 Router 收敛必须分批推进，每批改造后运行对应测试，避免一次性大改难以定位回归。
3. Alembic 引入必须兼容现有 SQLite 数据库和测试临时库。
4. 最终提交前必须完成后端全量测试、前端测试、前端构建和文档/Postman 更新。
5. 测试完成后统一提交并推送，不拆分中途提交。
