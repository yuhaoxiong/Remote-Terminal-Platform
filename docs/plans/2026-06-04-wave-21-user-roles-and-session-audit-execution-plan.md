# Wave 21 执行计划：多管理员账号、角色权限与会话审计基础

> 阶段：`xl_plan`
> 状态：已批准，已执行，验证收尾中
> 冻结需求：`docs/requirements/2026-06-04-wave-21-user-roles-and-session-audit.md`

## 1. 执行目标

Wave 21 在现有单管理员平台基础上补齐轻量多用户、角色权限和认证审计能力。核心目标是让平台从“登录即可全权限”收敛为“admin 管系统，operator 做日常运维”，并确保权限不足不会误判为登录失效。

完成后应达到：

- 用户表支持 `role`、`is_active`、最近登录时间、最近登录 IP 和密码更新时间。
- 旧数据库升级后默认管理员仍可登录，并自动拥有 `admin` 角色。
- 新增用户管理 API，支持创建用户、编辑角色/状态、重置密码、停用用户。
- 禁止停用最后一个启用状态的 `admin`。
- 停用用户不能登录，停用后 refresh 失败。
- 后端建立统一角色校验 helper，登录但权限不足返回 `403`。
- `operator` 可创建设备和编辑设备，但不能删除设备。
- `operator` 只允许 dry-run 批量任务，真实 SSH 批量任务仅 `admin`。
- `operator` 可查看定时任务和手动 dry-run，定时任务创建、编辑、删除仅 `admin`。
- 告警规则编辑、告警通知配置、用户管理仅 `admin`。
- 前端新增“用户管理”一级入口，仅 `admin` 可见。
- 前端根据角色隐藏或禁用高风险入口；收到 `403` 时显示中文权限提示，不退出登录。
- 认证事件、用户管理事件和关键权限失败写入操作日志，不记录密码、Token、哈希或敏感配置。
- 诊断接口新增用户摘要。
- README、API、部署、前端手工测试和 Postman 同步更新。
- 测试完成后统一提交并推送到 `origin/main`。

## 2. 冻结决策

1. `operator` 允许创建设备和编辑设备，删除设备仅 `admin`。
2. `operator` 本轮只允许创建/执行 dry-run 批量任务，真实 SSH 批量任务仅 `admin`。
3. `operator` 可查看定时任务和手动 dry-run，定时任务创建、编辑、删除仅 `admin`。
4. 用户删除采用停用优先，不做硬删除，保留操作日志关联。
5. 本轮不新增完整 refresh token 黑名单，只确保停用用户登录和 refresh 失败。
6. 用户管理作为一级导航入口，仅 `admin` 可见。
7. 测试完成后统一提交并推送到 `origin/main`。

## 3. 总体执行策略

本轮的主要风险在权限边界和登录态兼容。执行时先从数据模型和认证响应入手，再收敛后端高风险接口，最后做前端角色感知和用户管理页面。

推荐顺序：

1. 审计当前认证、用户模型、操作日志和前端登录状态流。
2. 新增用户角色枚举、模型字段、迁移和兼容初始化。
3. 扩展认证与当前用户响应，补齐停用用户登录/refresh 拦截。
4. 实现统一权限校验 helper 和用户管理服务/API。
5. 对高风险 router 分层加权限限制，并补操作日志。
6. 扩展诊断用户摘要。
7. 前端接入当前用户角色、导航权限和 `403` 处理。
8. 新增用户管理页面与测试。
9. 更新 README、API、部署、前端手工测试和 Postman。
10. 跑后端全量 pytest、前端 Vitest、typecheck、build。
11. 清理临时文件，统一提交并推送。

连续 3 次同类失败时停止实现并报告失败点、根因和替代方案。

## 4. 工作拆分

### Step 1：基线审计与实现面确认

阅读并确认当前模式：

- `backend/app/models/user.py`
- `backend/app/services/auth_service.py`
- `backend/app/routers/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/dependencies.py` 或当前认证依赖所在文件
- `backend/app/services/operation_log.py`
- `backend/app/routers/devices.py`
- `backend/app/routers/update_tasks.py`
- `backend/app/routers/scheduled_tasks.py`
- `backend/app/routers/alerts.py`
- `backend/app/routers/alert_notifications.py`
- `backend/app/routers/diagnostics.py`
- `frontend/src/App.vue`
- `frontend/src/api/platform.ts`
- `frontend/src/__tests__/app.spec.ts`

需要确认：

- 当前 access token payload 是否包含用户 ID 和用户名，是否需要加入角色。
- refresh token 校验路径是否每次读取用户状态。
- 前端当前如何处理 `401`、`403` 和 refresh 失败。
- 操作日志写入 helper 是否可复用到认证失败和权限失败。
- 当前测试 fixture 如何创建默认管理员。

产出：

- 不单独生成审计文档。
- 若发现 refresh 流程无法可靠检查停用状态，应优先修正认证服务再继续。

阶段验证：

```powershell
git status --short
```

### Step 2：枚举、用户模型和迁移

新增或扩展枚举：

- `UserRole`
  - `admin`
  - `operator`

扩展 `users` 表字段：

- `role`
- `is_active`
- `last_login_at`
- `last_login_ip`
- `password_changed_at`
- `created_at`
- `updated_at`

迁移要求：

- 新增 Alembic revision，例如 `wave21_user_roles_and_audit`。
- 旧库现有用户补齐 `role='admin'` 或至少默认管理员设为 `admin`。
- 旧库现有用户补齐 `is_active=true`。
- 保持 `password_hash` 不变，确保默认管理员可继续登录。
- `init_db` 的兼容兜底也要能在 SQLite 旧库中补齐字段。

测试：

- `test_migrations.py` 覆盖新字段。
- `test_database_migrations.py` 覆盖旧用户表升级。

阶段验证：

```powershell
$env:PYTHONPATH=(Resolve-Path backend).Path
pytest backend/tests/test_migrations.py backend/tests/test_database_migrations.py -q --basetemp .tmp/pytest-wave21-migration -p no:cacheprovider
```

### Step 3：认证响应、停用拦截和审计

改造点：

- `GET /api/auth/me` 返回 `id`、`username`、`role`、`is_active`。
- 登录成功后更新 `last_login_at` 和 `last_login_ip`。
- 登录成功、登录失败写入操作日志。
- refresh 成功和失败写入操作日志。
- 停用用户登录返回 `401`。
- 停用用户 refresh 返回 `401`。
- 修改密码成功后更新 `password_changed_at`。

注意：

- 日志不得记录密码、access token、refresh token 或 hash。
- 登录失败可记录用户名和 IP。
- 不引入完整 token 黑名单。

测试：

- 默认管理员登录成功。
- 停用用户登录失败。
- 停用用户 refresh 失败。
- `me` 返回角色。
- 登录失败日志不含密码。

### Step 4：权限依赖和用户管理 API

新增统一权限 helper：

- `require_current_user`
- `require_admin_user`
- `require_roles`

新增用户管理 Schema：

- `UserRead`
- `UserCreate`
- `UserUpdate`
- `UserResetPasswordRequest`
- `UserListResponse`

新增用户管理 Router：

```http
GET /api/users
POST /api/users
GET /api/users/{user_id}
PUT /api/users/{user_id}
POST /api/users/{user_id}/reset-password
POST /api/users/{user_id}/toggle
DELETE /api/users/{user_id}
```

实现语义：

- 以上用户管理接口全部仅 `admin`。
- `DELETE` 采用停用语义，不做硬删。
- 禁止停用最后一个启用 `admin`。
- 禁止把最后一个启用 `admin` 改成 `operator`。
- 用户名重复返回 `409`。
- 用户不存在返回 `404`。
- 空更新返回 `422`。
- 操作成功写入 `user.create`、`user.update`、`user.reset_password`、`user.toggle`、`user.disable` 等操作日志。

测试：

- admin 创建 operator。
- admin 修改角色和启用状态。
- admin 重置密码。
- operator 访问用户管理返回 `403`。
- 禁止停用最后一个 admin。

### Step 5：高风险接口权限收敛

按冻结决策收敛：

设备：

- `GET /api/devices`、`GET /api/devices/{id}`：admin/operator。
- `POST /api/devices`、`PUT /api/devices/{id}`：admin/operator。
- `DELETE /api/devices/{id}`：admin。

分组：

- 查询：admin/operator。
- 创建/编辑：可维持 admin/operator 或按当前实现最小改动。
- 删除：admin。

批量任务：

- dry-run 创建/执行：admin/operator。
- `execution_mode=ssh_command` 创建或执行：admin。
- 取消真实 SSH 任务：admin。
- 导出结果：admin/operator。

定时任务：

- 查询和执行 dry-run：admin/operator。
- 创建、编辑、删除、启停：admin。
- `execution_mode=ssh_command` 的手动执行：admin。

告警：

- 查询、确认、恢复：admin/operator。
- 告警规则编辑：admin。

告警通知：

- 查询摘要和投递记录：admin/operator。
- 通道/策略创建、编辑、删除、测试、重试：admin。

诊断：

- 查询：admin/operator。

测试：

- 针对每类至少覆盖一个 admin 成功和 operator 403。
- 重点覆盖 `403` 不应变成 `401`。

### Step 6：诊断用户摘要

扩展 `GET /api/diagnostics/config`：

```json
{
  "users": {
    "total_count": 2,
    "active_count": 2,
    "admin_count": 1,
    "operator_count": 1,
    "disabled_count": 0,
    "warnings": []
  }
}
```

warning 建议：

- 仍只有默认 `admin` 用户。
- 启用 admin 数量为 0。
- 存在停用用户。
- 默认管理员密码仍在使用时复用 `security.warnings`，不要重复泄露细节。

测试：

- 诊断响应包含 `users`。
- 不返回密码、hash、token。

### Step 7：前端 API、登录态和权限错误处理

扩展 `frontend/src/api/platform.ts`：

- `CurrentUser` 增加 `role`、`is_active`。
- 新增用户管理类型和 API 方法。

前端状态：

- 登录成功后加载当前用户。
- 保存当前用户角色。
- refresh 成功后保持当前用户状态；必要时重新拉取 `me`。
- `403` 只显示中文权限提示，不触发 auth expired。

导航：

- 新增“用户管理”一级入口，仅 `admin` 可见。
- `operator` 不显示用户管理入口。

测试：

- admin 看到用户管理。
- operator 不看到用户管理。
- `403` 不回登录页。

### Step 8：用户管理前端页面

建议新建组件：

- `frontend/src/components/UserManagementPanel.vue`

页面能力：

- 用户列表：用户名、角色、启用状态、最近登录、最近登录 IP、创建时间。
- 新增用户表单。
- 编辑用户角色和启用状态。
- 重置密码表单。
- 停用/启用按钮。

交互要求：

- 所有文案中文。
- 不展示密码 hash。
- 密码输入框不回显已有密码。
- 操作成功刷新列表。
- 操作失败显示中文错误。

测试：

- 创建用户。
- 修改角色。
- 停用用户。
- 重置密码。

### Step 9：文档和 Postman

更新：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/frontend-manual-test-guide.md`
- `docs/postman/edge-platform.postman_collection.json`

Postman 新增 “Wave 21 用户与权限”：

- admin 登录。
- 查询当前用户。
- 创建 operator。
- 查询用户列表。
- 重置 operator 密码。
- operator 登录。
- operator 调用 admin-only 接口，期望 `403`。
- admin 停用 operator。
- operator refresh 失败。

### Step 10：验证与收尾

运行：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
pytest backend/tests -q --basetemp .tmp/pytest-all -p no:cacheprovider

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run typecheck
npm.cmd run build
```

收尾：

- 删除 `.tmp` 等临时目录。
- `git diff --check`。
- `git status --short`。
- 确认没有无关文件。
- 提交并推送到 `origin/main`。

## 5. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 旧数据库用户表升级后默认管理员无法登录 | 先写迁移测试和兼容 `init_db` 测试 |
| operator 权限过宽导致高风险操作暴露 | 按冻结权限矩阵逐项测试 admin/operator |
| 前端把 403 当登录过期 | 单独测试 403，不触发清 token 和跳登录 |
| 停用用户 refresh 仍能续期 | refresh 流程强制读取用户 `is_active` |
| 操作日志泄露敏感字段 | 日志断言不包含密码、Token、hash、Webhook header 值 |
| 用户硬删除破坏历史日志关联 | DELETE 仅做停用语义 |

## 6. 验收清单

1. 旧库升级后默认管理员仍可登录。
2. admin 可创建、编辑、停用用户和重置密码。
3. operator 无法访问用户管理、告警规则编辑和通知配置管理接口。
4. operator 可创建设备和编辑设备，但不能删除设备。
5. operator 只能创建/执行 dry-run 批量任务，真实 SSH 任务返回 `403`。
6. operator 可查看定时任务和手动 dry-run，不能创建、编辑、删除定时任务。
7. 停用用户不能登录，也不能 refresh。
8. `GET /api/diagnostics/config` 返回用户摘要且不泄露敏感字段。
9. 前端 admin 可见“用户管理”，operator 不可见。
10. 前端收到 `403` 显示中文权限提示，不退出登录。
11. README、API、部署、前端手工测试和 Postman 已更新。
12. 后端测试、前端测试、类型检查和构建通过。

## 7. 执行结果摘要

- 已完成用户模型、Alembic 迁移、SQLite 兼容补列和默认管理员角色迁移。
- 已完成用户管理 API、角色权限 helper、认证审计和权限失败审计。
- 已按冻结决策收敛设备/分组删除、真实 SSH 批量任务、定时任务管理、告警规则和告警通知配置权限。
- 已完成前端用户名登录、当前用户角色展示、管理员用户管理入口、用户创建/启停/重置密码和 403 不退出登录处理。
- 已更新 README、API、部署、前端手工测试指南和 Postman Collection。
- 最终测试结果以本轮收尾命令为准。
