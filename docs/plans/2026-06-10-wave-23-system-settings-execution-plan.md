# Wave 23 执行计划：管理员系统设置与数据库配置覆盖

> 阶段：`xl_plan`
> 状态：已批准，执行中
> 冻结需求：`docs/requirements/2026-06-10-wave-23-system-settings.md`

## 1. 执行目标

Wave 23 在 Wave 22 前端企业后台和 Wave 21 权限基础上，新增仅 `admin` 可见的系统设置能力。核心目标是让部分后端运行参数支持数据库覆盖、分组保存、敏感值加密、待重启状态、systemd 重启和变更审计，同时保持启动级配置和部署边界清晰。

完成后应达到：

- 新增系统设置页，只有 `admin` 可见和可访问。
- 新增系统设置后端注册表，所有可编辑配置均来自白名单。
- 有效配置读取顺序固定为 `数据库覆盖值 > 系统配置/环境变量 > 代码默认值`。
- 后端启动时加载有效配置到内存，保存后刷新内存缓存。
- `DATABASE_URL` 和 `CREDENTIAL_ENCRYPTION_KEY` 仍为启动级配置，不允许数据库覆盖。
- `JWT_SECRET_KEY` 第一版只做状态展示和风险提示，不允许前端编辑。
- 敏感配置加密保存；未配置加密密钥时禁止保存敏感配置。
- 需重启配置保存后持久化 `pending_restart`，服务重启并成功应用后自动清除。
- 系统设置支持恢复默认值，即删除数据库覆盖值并回退到系统配置或默认值。
- 新增独立变更历史表，同时写入现有操作日志。
- 重启服务按钮通过 systemd 托管检测、高风险确认和健康轮询形成闭环。
- 诊断页继续给 `operator` 展示有限、脱敏、只读摘要。
- Alembic 迁移、后端测试、前端测试、类型检查、构建和文档更新完成。

## 2. 冻结决策

1. 配置读取顺序为 `数据库覆盖值 > 系统配置/环境变量 > 代码默认值`。
2. 尽量减少非必须环境变量。
3. `DATABASE_URL` 和 `CREDENTIAL_ENCRYPTION_KEY` 保持启动级配置，不允许数据库覆盖。
4. 启动时加载到内存，保存后刷新内存缓存。
5. 系统设置只允许修改后端注册表白名单内的配置项。
6. `JWT_SECRET_KEY` 第一版不纳入可编辑白名单，只做状态展示和风险提示。
7. 默认设备 SSH 凭据允许编辑，敏感值加密存库。
8. 未配置 `CREDENTIAL_ENCRYPTION_KEY` 时，不允许保存敏感配置，但允许保存非敏感配置。
9. Webhook 只配置通用运行参数，不管理具体 URL、密钥或通道。
10. 按分组单独保存。
11. 新增独立变更历史表，同时写操作日志。
12. 系统设置页和系统设置接口只允许 `admin`，诊断页继续允许 `operator` 查看有限只读状态。
13. 数据库迁移按 Alembic 推进。
14. 需重启配置保存前弹窗告知，保存后持久化待重启状态。
15. 系统设置页增加“重启服务”按钮。
16. 重启服务由 systemd 托管后端进程，后端返回 `202` 后延迟退出。
17. 检测不到 systemd 托管时，后端拒绝重启并返回中文错误。
18. 点击重启服务需要高风险二次确认。
19. 服务重启成功后自动清除待重启状态。
20. 启动读取到非法数据库设置时，按配置风险分级处理。
21. Wave23 白名单范围按需求文档冻结，先不继续扩大。

## 3. 总体执行策略

本轮同时触及数据库迁移、运行配置、权限、前端管理页和重启控制，风险高于纯前端优化。执行时采用“后端配置核心先行，前端页面后接入”的顺序。

推荐顺序：

1. 审计当前 `Settings`、依赖注入、服务读取配置、诊断、操作日志、Alembic 和权限模式。
2. 先补后端测试或最小失败用例，锁定读取顺序、白名单拒绝、敏感值脱敏和权限边界。
3. 新增模型、迁移、注册表和系统设置服务。
4. 接入应用启动加载、内存缓存刷新、待重启状态和非法配置处理。
5. 新增系统设置 API、恢复默认、变更历史和重启接口。
6. 扩展诊断摘要和 OpenAPI。
7. 前端新增系统设置 API 类型、导航入口、页面和分组表单。
8. 补齐前后端测试、文档、部署说明和手工测试指南。
9. 运行全量验证，清理临时文件。

连续 3 次同类失败时停止实现并报告失败点、已尝试方案、当前判断和所需输入。

## 4. 工作拆分

### Step 1：基线审计与测试切入点

阅读并确认当前模式：

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/dependencies.py`
- `backend/app/models`
- `backend/app/routers/diagnostics.py`
- `backend/app/services`
- `backend/app/services/operation_log.py`
- `backend/alembic`
- `backend/tests`
- `frontend/src/App.vue`
- `frontend/src/api/platform.ts`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/AppTopbar.vue`
- `frontend/src/components/DiagnosticCard.vue`
- `frontend/src/__tests__/app.spec.ts`

需要确认：

- 当前 `get_settings()` 和 `app.state.settings` 的使用链路。
- 哪些服务在请求期读取配置，哪些在启动期缓存配置。
- 当前凭据加密工具或服务如何复用。
- Alembic revision 命名和测试夹具模式。
- 操作日志 helper 的调用方式。
- 前端导航权限和 admin-only 菜单模式。

阶段验证：

```powershell
git status --short
```

### Step 2：后端失败用例与迁移设计

先补最小后端测试，覆盖本轮核心行为：

- 未知配置 key 保存被拒绝。
- 非 admin 调用系统设置接口返回 `403`。
- 数据库覆盖值优先于系统配置。
- 未配置 `CREDENTIAL_ENCRYPTION_KEY` 时敏感配置保存失败。
- 敏感配置 API 响应不回显明文。
- 需重启配置保存后 `pending_restart=true`。
- 恢复默认值后删除数据库覆盖并回退。

设计 Alembic 迁移：

- `system_settings`
- `system_setting_changes`

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests -q --basetemp .tmp/pytest-wave23-red -p no:cacheprovider
```

说明：

- 初始测试可以失败，用于记录 TDD 红灯证据。
- 如果现有测试结构不适合全量红灯，可先运行新增测试文件。

### Step 3：模型、注册表和配置值类型

新增后端模型：

- `SystemSetting`
- `SystemSettingChange`

新增或扩展 Schema：

- `SystemSettingSchemaItem`
- `SystemSettingEffectiveValue`
- `SystemSettingGroupUpdate`
- `SystemSettingChangeRead`
- `SystemSettingRestartStatus`

新增注册表：

- `SYSTEM_SETTING_REGISTRY`
- 分组定义：
  - `remote_connection`
  - `device_credentials`
  - `file_storage`
  - `scheduler`
  - `alert_notification`
  - `security_auth`
  - `readonly_status`

注册表要求：

- key 必须来自冻结需求白名单。
- 每项声明类型、分组、是否敏感、是否可编辑、是否需重启、是否立即生效、校验规则。
- `JWT_SECRET_KEY`、`DATABASE_URL`、`CREDENTIAL_ENCRYPTION_KEY` 只读展示，不可编辑。
- 不支持任意 key。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests/test_system_settings*.py -q --basetemp .tmp/pytest-wave23-registry -p no:cacheprovider
```

### Step 4：系统设置服务与有效配置缓存

新增系统设置服务，建议职责：

- 从系统配置/环境变量构造基础 `Settings`。
- 从数据库读取覆盖值。
- 校验并合并为有效配置。
- 写入或刷新 `app.state.settings`。
- 保存分组配置。
- 恢复默认值。
- 加密和解密敏感值。
- 写入 `system_setting_changes`。
- 写入操作日志。
- 处理 `pending_restart` 状态。

生效规则：

- 立即生效项保存后刷新内存配置。
- 需重启项保存后刷新可见状态，但标记 `pending_restart=true`。
- 服务启动成功并应用待重启配置后，自动清除对应 `pending_restart`。
- 非法普通配置跳过覆盖并记录诊断风险。
- 启动关键非法配置拒绝启动。
- 敏感配置解密失败时回退或标记能力不可用。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests/test_system_settings*.py -q --basetemp .tmp/pytest-wave23-service -p no:cacheprovider
```

### Step 5：系统设置 API 与权限

新增 Router：

```http
GET /api/system-settings/schema
GET /api/system-settings/effective
PUT /api/system-settings/groups/{group_key}
POST /api/system-settings/{key}/reset
GET /api/system-settings/changes
POST /api/system-settings/restart
```

权限：

- 全部系统设置接口要求 `admin`。
- 未登录返回 `401`。
- 非 admin 返回 `403`。
- `operator` 不能通过系统设置接口枚举配置。

行为：

- `schema` 返回注册表和 UI 渲染元数据。
- `effective` 返回有效值、来源、数据库覆盖状态、待重启状态；敏感项脱敏。
- `PUT /groups/{group_key}` 只保存指定分组。
- `reset` 删除数据库覆盖值。
- `changes` 支持分页、key、分组、操作者、时间范围筛选。
- 所有错误使用中文 message 或可被前端转换为中文。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests/test_system_settings*.py backend/tests/test_auth*.py -q --basetemp .tmp/pytest-wave23-api -p no:cacheprovider
```

### Step 6：systemd 重启接口与待重启闭环

重启接口实现要求：

- 仅 `admin` 可调用。
- 检测 systemd 托管状态，例如 `INVOCATION_ID`、`SYSTEMD_EXEC_PID`、父进程信息或等价可靠信号。
- 无法确认 systemd 托管时拒绝执行，返回中文错误，不退出进程。
- 可执行时写操作日志和系统设置变更历史。
- 返回 `202 Accepted` 后延迟 1-2 秒退出当前进程。
- 测试中必须 mock 退出函数，不能真实结束 pytest 进程。

前端轮询依赖：

- 复用现有健康检查接口。
- 重启发起后前端进入等待状态。
- 健康恢复后刷新系统设置页。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests/test_system_settings*.py -q --basetemp .tmp/pytest-wave23-restart -p no:cacheprovider
```

### Step 7：诊断摘要和文档化 API 输出

扩展诊断页后端摘要：

- 系统设置表是否存在。
- 数据库覆盖项数量。
- 待重启配置数量。
- 是否配置凭据加密密钥。
- 是否检测到 systemd 托管。
- 是否存在非法数据库覆盖值。
- JWT 是否使用默认密钥。

要求：

- `operator` 可看有限脱敏摘要。
- 不返回密码、Token、私钥、Webhook 明文密钥或完整数据库连接串。
- OpenAPI 或 API 文档描述系统设置接口权限和脱敏规则。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests/test_diagnostics*.py backend/tests/test_system_settings*.py -q --basetemp .tmp/pytest-wave23-diagnostics -p no:cacheprovider
```

### Step 8：前端 API 类型与导航入口

扩展前端 API：

- 系统设置 schema。
- 有效配置值。
- 分组保存。
- 恢复默认值。
- 变更历史。
- 重启服务。

导航：

- 左侧新增“系统设置”一级入口。
- 仅 `admin` 可见。
- `operator` 不显示入口。
- `403` 显示中文无权限提示，不清理登录态。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run typecheck
```

### Step 9：系统设置前端页面

建议新增组件：

- `frontend/src/views/SystemSettingsView.vue`
- `frontend/src/components/SystemSettingsPanel.vue`
- `frontend/src/components/SystemSettingGroupCard.vue`
- `frontend/src/components/SystemSettingHistoryTable.vue`
- `frontend/src/components/SystemRestartPanel.vue`

页面结构：

- 顶部状态：配置健康、待重启数量、加密密钥状态、systemd 托管状态、重启服务按钮。
- 分组表单：
  - 远程连接。
  - 默认设备凭据。
  - 文件与存储。
  - 调度器。
  - 告警通知。
  - 安全与认证。
- 只读状态：数据库、凭据加密密钥、JWT 风险、systemd 状态。
- 变更历史。

交互要求：

- 分组单独保存。
- 每项显示来源标签：`数据库覆盖`、`系统配置`、`默认值`。
- 数据库覆盖项支持恢复默认值。
- 敏感字段不回显旧值，只允许输入新值。
- 未配置加密密钥时敏感字段禁用保存。
- 保存需重启配置前弹窗告知。
- 保存后显示待重启状态。
- 重启服务要求输入 `确认重启`。
- 重启中轮询健康检查。
- 所有提示中文。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
npm.cmd run typecheck
```

### Step 10：测试补强

后端测试至少覆盖：

- Alembic 迁移。
- 白名单拒绝未知 key。
- 读取顺序。
- 敏感配置加密和脱敏。
- 无加密密钥时敏感配置保存失败。
- `pending_restart` 保存、启动清除。
- 恢复默认值。
- 变更历史。
- 操作日志。
- admin/operator 权限。
- systemd 未检测到时拒绝重启。
- 重启成功路径 mock 退出。

前端测试至少覆盖：

- admin 可见系统设置。
- operator 不可见系统设置。
- 分组、来源标签、只读安全状态渲染。
- 未配置加密密钥时敏感字段禁用。
- 保存需重启配置前弹窗。
- 保存后显示待重启状态。
- 恢复默认值确认。
- 重启服务输入 `确认重启`。
- `403` 不退出登录。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests -q --basetemp .tmp/pytest-all -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run typecheck
```

### Step 11：文档更新

更新：

- `README.md`
- API 文档或 OpenAPI 文件。
- 部署文档。
- `docs/frontend-manual-test-guide.md`

文档必须说明：

- 系统设置页仅 `admin` 可见。
- 配置读取顺序。
- 哪些配置仍为启动级配置。
- `CREDENTIAL_ENCRYPTION_KEY` 对敏感配置保存的影响。
- systemd 托管和 `Restart` 配置要求。
- 重启按钮的行为和失败条件。
- 敏感信息不会回显。

### Step 12：最终验证与收尾

最终运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests -q --basetemp .tmp/pytest-all -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run typecheck
npm.cmd run build

cd C:\01_work\02_program\远程终端平台
git diff --check
git status --short
```

收尾要求：

- 不提交 `.tmp`、数据库、日志、截图、构建产物或本地环境文件。
- 如 OpenAPI 自动生成导致大 diff，需要确认只包含系统设置相关接口。
- 记录任何 Vite chunk warning 或非阻塞警告。
- 测试完成后按用户确认统一提交并推送。

## 5. 关键实现约束

- 不允许数据库覆盖 `DATABASE_URL`。
- 不允许数据库覆盖 `CREDENTIAL_ENCRYPTION_KEY`。
- 第一版不允许编辑 `JWT_SECRET_KEY`。
- 不开放任意 key。
- 不从前端修改 `.env`、systemd unit 或服务器环境变量。
- 不在 API、前端、日志或变更历史中泄露敏感明文。
- systemd 检测失败时不能退出进程。
- 测试中不能真实触发进程退出。
- 不能把 operator 只读诊断扩展成系统设置读取权限。
- 不删除现有测试，不降低权限断言。

## 6. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 配置缓存与旧 `get_settings()` 使用链路不一致 | 先审计调用链，统一通过 `app.state.settings` 或依赖读取有效配置 |
| 敏感配置保存导致明文泄露 | 后端脱敏测试、变更历史脱敏测试、前端不回显旧值 |
| 重启接口误杀开发环境进程 | systemd 检测失败拒绝执行，测试 mock 退出函数 |
| 待重启状态清除时机错误 | 启动加载配置后再清除，并记录变更历史 |
| 非法数据库配置导致服务不可用 | 按风险分级处理，普通配置可回退并记录诊断风险 |
| 前端保存整页导致局部失败难定位 | 按分组单独保存 |
| operator 通过 API 枚举配置 | 系统设置 API 全部 admin-only，诊断另走脱敏摘要 |
| Alembic 与测试初始化路径不一致 | 迁移测试和测试夹具同时覆盖 |

## 7. 验收清单

- [ ] Wave 23 需求文档和执行计划已确认。
- [ ] Alembic 迁移新增 `system_settings` 和 `system_setting_changes`。
- [ ] 后端注册表白名单覆盖冻结配置范围。
- [ ] 未知 key 保存被拒绝。
- [ ] 配置读取顺序符合数据库覆盖优先。
- [ ] 启动加载有效配置到内存，保存后刷新内存缓存。
- [ ] 敏感配置加密保存且不回显。
- [ ] 无 `CREDENTIAL_ENCRYPTION_KEY` 时敏感配置保存失败。
- [ ] 需重启配置保存后持久化 `pending_restart`。
- [ ] 服务启动成功应用配置后清除 `pending_restart`。
- [ ] 恢复默认值删除数据库覆盖并回退。
- [ ] 系统设置变更历史可查询。
- [ ] 操作日志记录保存、恢复默认和重启操作。
- [ ] 重启接口 systemd 检测失败时拒绝执行。
- [ ] 重启接口成功路径返回 `202`，测试通过 mock 验证。
- [ ] 诊断页返回脱敏系统设置摘要。
- [ ] 前端 admin 可见系统设置，operator 不可见。
- [ ] 前端分组保存、来源标签、恢复默认、待重启提示可用。
- [ ] 前端重启服务需要输入 `确认重启`。
- [ ] README、API/部署/手工测试文档已更新。
- [ ] 后端测试通过。
- [ ] 前端测试通过。
- [ ] 前端 typecheck 通过。
- [ ] 前端 build 通过。
- [ ] `git diff --check` 通过。

## 8. 建议提交策略

如果用户确认本轮实现后需要提交，建议提交信息：

```text
feat: add admin system settings
```

提交前必须确认：

- 只包含 Wave 23 系统设置、配置覆盖、重启控制、诊断和文档相关改动。
- 不包含本地数据库、临时测试目录、日志、截图和构建产物。
- 验证命令结果已记录。
