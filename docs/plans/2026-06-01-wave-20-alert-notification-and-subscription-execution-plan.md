# Wave 20 执行计划：告警通知与订阅策略

> 阶段：`xl_plan`
> 状态：已实现，等待最终验收与提交
> 冻结需求：`docs/requirements/2026-05-27-wave-20-alert-notification-and-subscription.md`

## 1. 执行目标

Wave 20 在 Wave 19 告警中心基础上新增轻量外部通知能力。核心目标是让严重告警能通过 Webhook 主动触达外部系统，同时保证通知失败不影响告警主流程。

完成后应达到：

- 只支持 Webhook 通知通道，不实现 SMTP 邮件。
- 通知配置入口放在“告警中心”内，不新增一级导航。
- Webhook URL、Header、Token 等敏感配置复用 `CREDENTIAL_ENCRYPTION_KEY` 加密保存。
- 未配置加密密钥时，写入敏感配置必须阻断并返回明确提示。
- 可配置通知通道、通知策略和查看投递历史。
- 默认策略只通知 `critical` 级别的 `triggered` 事件。
- 告警触发、确认、恢复、自动恢复能产生可审计通知事件。
- 同一告警同一事件对同一通道只生成一条投递记录，避免重复刷屏。
- 外部 Webhook 失败时记录失败和重试状态，不阻塞告警创建或恢复。
- 系统诊断展示通知模块摘要和失败 warning。
- README、API、部署、前端手工测试和 Postman 同步更新。
- 测试完成后统一提交并推送到 `origin/main`。

## 2. 冻结决策

1. Wave 20 按“告警外部通知”推进，优先支持 Webhook。
2. 本轮只实现 Webhook，不实现邮件 SMTP。
3. 通知配置挂在“告警中心”内。
4. 敏感配置必须复用 `CREDENTIAL_ENCRYPTION_KEY` 加密保存；未配置密钥时不得明文保存敏感字段。
5. 删除通知通道前必须先删除或解除关联通知策略；仍有策略引用时接口返回 `409`。
6. 默认通知策略只通知 `critical` 的 `triggered` 事件。
7. 计划批准后实现；测试完成后统一提交并推送到 `origin/main`。

## 3. 总体执行策略

本轮是告警中心的外部投递扩展，关键风险在“敏感配置处理”和“通知失败隔离”。执行时应先建立数据模型和加密边界，再把通知服务接入 Wave 19 告警状态变化点。

推荐顺序：

1. 审计 Wave 19 告警模型、服务、router、前端告警中心组件和现有凭据加密工具。
2. 新增通知枚举、模型、迁移和 Schema。
3. 实现通知配置加密/脱敏、Webhook 投递、策略匹配、投递记录和重试服务。
4. 在告警触发、确认、手动恢复、自动恢复路径中派发通知事件。
5. 新增通知 API、操作日志和诊断摘要。
6. 扩展前端 API 和 `AlertCenterPanel.vue`，在告警中心内加入通知配置和投递历史。
7. 更新 README、API、部署、前端手工测试和 Postman。
8. 跑后端全量 pytest、前端 Vitest、前端 build、必要的本地 API/前端冒烟。
9. 清理临时文件，统一提交并推送。

连续 3 次同类失败时停止实现并报告失败点、根因和替代方案。

## 4. 工作拆分

### Step 1：基线审计与实现面确认

阅读并确认当前模式：

- `backend/app/models/alert.py`
- `backend/app/services/alert_service.py`
- `backend/app/routers/alerts.py`
- `backend/app/schemas/alert.py`
- `backend/app/enums.py`
- `backend/app/services/credential_service.py` 或现有凭据加密实现所在文件
- `backend/app/core/config.py`
- `backend/app/routers/diagnostics.py`
- `backend/app/schemas/diagnostics.py`
- `backend/app/services/operation_log.py`
- `frontend/src/components/AlertCenterPanel.vue`
- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/__tests__/app.spec.ts`

需要确认：

- Wave 19 告警创建、确认、恢复、自动恢复方法的统一入口。
- `CREDENTIAL_ENCRYPTION_KEY` 当前如何读取和判定是否已配置。
- 设备 SSH 凭据加密工具是否能复用于 JSON secret。
- 告警中心当前组件是否适合继续承载通知配置，还是需要拆出子组件。
- 前端测试是否已有告警中心 mock，可扩展通知接口 mock。

产出：

- 不单独生成审计文档。
- 若发现无法可靠复用现有加密工具，应在实现前调整计划并说明。

阶段验证：

```powershell
git status --short
```

### Step 2：枚举、模型和迁移

新增枚举建议：

- `AlertNotificationChannelType`
  - `webhook`
- `AlertNotificationEventType`
  - `triggered`
  - `acknowledged`
  - `resolved`
  - `auto_resolved`
- `AlertNotificationDeliveryStatus`
  - `pending`
  - `success`
  - `failed`
  - `retrying`
  - `skipped`

新增模型文件建议：

- `backend/app/models/alert_notification.py`

新增模型：

- `AlertNotificationChannel`
- `AlertNotificationPolicy`
- `AlertNotificationDelivery`

新增迁移：

- `backend/alembic/versions/<revision>_wave20_alert_notifications.py`

迁移内容：

- 新增 `alert_notification_channels`。
- 新增 `alert_notification_policies`。
- 新增 `alert_notification_deliveries`。
- 增加必要索引：
  - `alert_notification_channels.channel_type`
  - `alert_notification_channels.enabled`
  - `alert_notification_policies.channel_id`
  - `alert_notification_policies.enabled`
  - `alert_notification_deliveries.alert_id`
  - `alert_notification_deliveries.channel_id`
  - `alert_notification_deliveries.policy_id`
  - `alert_notification_deliveries.status`
  - `alert_notification_deliveries.next_retry_at`
  - 唯一约束：同一 `alert_id + channel_id + policy_id + event_type` 只保留一条事件投递记录。

字段约束：

- `channel_type` 本轮只允许 `webhook`。
- `config` 保存非敏感 JSON，例如脱敏 URL 展示信息、timeout、Header key 列表。
- `secret_config_encrypted` 保存加密后的 Webhook URL、Header value/token 等敏感 JSON。
- `policy.source_types`、`policy.alert_statuses`、`policy.event_types` 可用 JSON 字段保存字符串数组。
- 删除通道时如存在策略引用，服务层返回 `409`，数据库层不做级联删除。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_migrations.py tests/test_database_migrations.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave20-migration'
```

### Step 3：Schema 和通知服务

新增 Schema 文件建议：

- `backend/app/schemas/alert_notification.py`

核心 Schema：

- `AlertNotificationChannelRead`
- `AlertNotificationChannelCreate`
- `AlertNotificationChannelUpdate`
- `AlertNotificationChannelListResponse`
- `AlertNotificationPolicyRead`
- `AlertNotificationPolicyCreate`
- `AlertNotificationPolicyUpdate`
- `AlertNotificationPolicyListResponse`
- `AlertNotificationDeliveryRead`
- `AlertNotificationDeliveryListResponse`
- `AlertNotificationSummaryResponse`
- `AlertNotificationTestRequest`

新增服务文件：

- `backend/app/services/alert_notification_service.py`

服务方法建议：

- `list_channels(session)`
- `create_channel(session, payload)`
- `update_channel(session, channel_id, payload)`
- `delete_channel(session, channel_id)`
- `test_channel(session, channel_id, user_id)`
- `list_policies(session)`
- `create_policy(session, payload)`
- `update_policy(session, policy_id, payload)`
- `delete_policy(session, policy_id)`
- `list_deliveries(session, filters, offset, limit)`
- `summary(session)`
- `record_event(session, alert, event_type)`
- `retry_delivery(session, delivery_id, user_id)`
- `process_pending_delivery(session, delivery_id)`
- `deliver_webhook(channel, delivery_payload)`

加密/脱敏要求：

- 创建或更新 Webhook URL、Header value、token 时必须检测 `CREDENTIAL_ENCRYPTION_KEY`。
- 未配置加密密钥时返回业务错误，禁止写入敏感配置。
- API 读取通道时只返回脱敏摘要：
  - URL 可显示 scheme、host 和 path，query token 必须脱敏。
  - Header 只返回 key 和是否已配置 value。
  - 不返回 `secret_config_encrypted` 或解密后的 secret。

策略匹配要求：

- 默认只匹配 `critical` 的 `triggered`，但不自动创建外部通道。
- `min_severity=warning` 匹配 warning 和 critical。
- `min_severity=critical` 只匹配 critical。
- `source_types` 为空表示所有来源。
- `event_types` 为空时按默认 `triggered` 处理，或创建时补默认值。

投递要求：

- Webhook 使用短超时，建议默认 5 秒，可配置 1-30 秒。
- 响应摘要截断，建议 500 字符以内。
- 异常摘要截断，避免泄露完整堆栈。
- `attempt_count` 初始为 0，投递后递增。
- 失败后按 1/5/15 分钟计算 `next_retry_at`，超过 3 次标记 `failed`。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave20_alert_notifications.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave20-service'
```

### Step 4：接入告警事件派发

修改 Wave 19 告警服务：

- 告警新建或从已恢复进入新周期时派发 `triggered`。
- 管理员确认告警成功后派发 `acknowledged`。
- 管理员手动恢复告警成功后派发 `resolved`。
- 系统自动恢复告警成功后派发 `auto_resolved`。

建议做法：

- 在 `AlertService` 内部调用 `AlertNotificationService.record_event(...)`。
- 事件派发失败不能回滚告警状态变化；应记录投递失败或本地错误摘要。
- 同一 `alert_id + policy_id + channel_id + event_type` 已存在投递记录时跳过新建，避免重复刷屏。

需要特别验证：

- 指标持续超阈值只会在首次打开告警时生成 `triggered` 投递。
- 告警自动恢复只生成 `auto_resolved`，不混淆为管理员手动 `resolved`。
- 未配置任何通道/策略时，告警服务无异常。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave19_alerts.py tests/test_wave20_alert_notifications.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave20-events'
```

### Step 5：API、操作日志和诊断摘要

新增 Router：

- `backend/app/routers/alert_notifications.py`

新增接口：

```http
GET /api/alert-notification-channels
POST /api/alert-notification-channels
PUT /api/alert-notification-channels/{id}
DELETE /api/alert-notification-channels/{id}
POST /api/alert-notification-channels/{id}/test

GET /api/alert-notification-policies
POST /api/alert-notification-policies
PUT /api/alert-notification-policies/{id}
DELETE /api/alert-notification-policies/{id}

GET /api/alert-notification-deliveries
POST /api/alert-notification-deliveries/{id}/retry
GET /api/alert-notification-summary
```

操作日志建议：

- `alert_notification_channel.create`
- `alert_notification_channel.update`
- `alert_notification_channel.delete`
- `alert_notification_channel.test`
- `alert_notification_policy.create`
- `alert_notification_policy.update`
- `alert_notification_policy.delete`
- `alert_notification_delivery.retry`

诊断扩展：

- `backend/app/schemas/diagnostics.py` 新增 `DiagnosticsNotificationSummary`。
- `backend/app/routers/diagnostics.py` 返回 `notifications`。
- warning 场景：
  - 存在启用策略但无启用通道。
  - 存在失败或重试中的投递。
  - 未配置 `CREDENTIAL_ENCRYPTION_KEY` 且尝试使用通知 secret 配置。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave20_alert_notifications_api.py tests/test_diagnostics_api.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave20-api'
```

### Step 6：前端 API 和告警中心通知配置

扩展：

- `frontend/src/api/platform.ts`

新增类型和函数：

- `AlertNotificationChannelRead`
- `AlertNotificationChannelCreateRequest`
- `AlertNotificationChannelUpdateRequest`
- `AlertNotificationPolicyRead`
- `AlertNotificationPolicyCreateRequest`
- `AlertNotificationPolicyUpdateRequest`
- `AlertNotificationDeliveryRead`
- `AlertNotificationSummaryResponse`
- `listAlertNotificationChannels`
- `createAlertNotificationChannel`
- `updateAlertNotificationChannel`
- `deleteAlertNotificationChannel`
- `testAlertNotificationChannel`
- `listAlertNotificationPolicies`
- `createAlertNotificationPolicy`
- `updateAlertNotificationPolicy`
- `deleteAlertNotificationPolicy`
- `listAlertNotificationDeliveries`
- `retryAlertNotificationDelivery`
- `getAlertNotificationSummary`

前端组件策略：

- 优先把通知配置拆为子组件，避免 `AlertCenterPanel.vue` 继续膨胀：
  - `frontend/src/components/AlertNotificationPanel.vue`
- 在 `AlertCenterPanel.vue` 内使用 tabs 或分段控件：
  - `告警列表`
  - `告警规则`
  - `通知配置`
  - `投递历史`

通知配置 UI：

- Webhook 通道表格：
  - 名称、启用状态、脱敏 URL、Header 配置状态、最近测试状态、最近错误。
  - 操作：测试、编辑、删除。
- Webhook 表单：
  - 名称。
  - URL。
  - Header JSON 或 key/value 简化输入。
  - Timeout。
  - 启用开关。
  - 敏感字段保存后不回显，只显示“已配置”。
- 策略表格：
  - 名称、通道、最小级别、来源、事件类型、启用状态。
  - 默认策略模板按钮可选：只通知 critical triggered。
- 投递历史：
  - 告警标题、通道、策略、事件类型、状态、尝试次数、最近错误、重试按钮。

前端错误处理：

- 401/403 沿用全局认证逻辑。
- 409 删除通道失败显示“请先删除关联通知策略”。
- 未配置加密密钥导致创建失败时显示后端中文提示。
- Webhook 测试失败只在通知配置区提示，不影响告警列表。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run src/__tests__/app.spec.ts
npm.cmd run build
```

### Step 7：测试补齐

后端新增测试建议：

- `backend/tests/test_wave20_alert_notifications.py`
  - Webhook 通道创建、脱敏读取、更新、删除。
  - 未配置加密密钥时写入敏感配置被阻断。
  - 策略匹配 `critical triggered`。
  - 告警触发生成投递记录。
  - 同一事件不重复生成投递记录。
  - Webhook 投递成功/失败。
  - 手动重试失败投递。
- `backend/tests/test_wave20_alert_notifications_api.py`
  - 通道 CRUD。
  - 策略 CRUD。
  - 投递列表和 retry。
  - 测试通知。
  - 删除仍被策略引用的通道返回 `409`。

既有测试更新：

- `backend/tests/test_migrations.py`
- `backend/tests/test_database_migrations.py`
- `backend/tests/test_diagnostics_api.py`
- `frontend/src/__tests__/app.spec.ts`

全量验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

### Step 8：文档、Postman 和手工验收

更新文档：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/frontend-manual-test-guide.md`
- `docs/postman/edge-platform.postman_collection.json`

README 补充：

- Wave 20 支持 Webhook 外部通知。
- 只支持 Webhook，不支持 SMTP。
- 默认策略只通知 critical triggered。
- 敏感配置必须依赖 `CREDENTIAL_ENCRYPTION_KEY`。

API 文档补充：

- 通知通道 API。
- 通知策略 API。
- 投递历史 API。
- Webhook payload 示例。
- 409 删除通道约束。

部署文档补充：

- 后端服务器需要能访问 Webhook 目标地址。
- Nginx 不需要新增 location。
- `CREDENTIAL_ENCRYPTION_KEY` 必须配置。
- 出站防火墙、DNS、TLS 证书失败排查路径。

前端手工测试补充：

- 创建 Webhook 通道。
- 测试通知。
- 创建默认策略。
- 触发 critical 告警并查看投递历史。
- 删除通道前策略引用的 409 提示。

Postman 补充：

- 新增 “Wave 20 告警通知” 分组。
- 请求包括：
  - 创建 Webhook 通道。
  - 查询通道。
  - 测试通道。
  - 创建通知策略。
  - 查询投递历史。
  - 重试投递。
  - 删除策略。
  - 删除通道。

阶段验证：

```powershell
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman ok')"
```

### Step 9：浏览器与 API 冒烟

实现完成后启动本地服务：

```powershell
cd C:\01_work\02_program\远程终端平台\backend
$env:PYTHONPATH=(Get-Location).Path
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8020

cd C:\01_work\02_program\远程终端平台\frontend
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8020'
npm.cmd run dev -- --host 127.0.0.1 --port 5178
```

冒烟路径：

1. 登录前端。
2. 进入“告警中心”。
3. 打开“通知配置”。
4. 确认无配置时页面空状态正常。
5. 尝试创建 Webhook 通道；若未配置 `CREDENTIAL_ENCRYPTION_KEY`，应看到中文阻断提示。
6. 配置加密密钥后创建通道，确认列表脱敏显示。
7. 创建默认 critical triggered 策略。
8. 查询投递历史。

如果无法稳定做真实 Webhook，可用本地测试 HTTP server 或后端测试 mock 完成投递验证。

### Step 10：提交与推送

完成全部验证后：

```powershell
git status --short
git diff --check
git add <wave20 files>
git commit -m "feat: add alert webhook notifications"
git push origin main
```

提交前检查：

- 不提交 `.pytest-tmp*`、`frontend/dist`、本地数据库或日志。
- 确认没有明文 Webhook secret、Token、密码进入文档、测试快照或 Postman 默认变量。
- 工作区无未解释变更。

## 5. 关键实现约束

- 不引入 SMTP、短信或第三方平台 SDK。
- 不引入 Redis、Celery、外部消息队列。
- 不把通知失败作为告警创建失败。
- 不在 API 响应、操作日志、投递记录、前端表格或 Postman 默认变量中暴露 Webhook secret。
- 不新增一级导航；通知配置必须挂在告警中心内。
- 删除仍被策略引用的通道必须返回 `409`。
- 默认策略只通知 `critical` 的 `triggered` 事件。

## 6. 风险与回退

| 风险 | 处理 |
| --- | --- |
| 现有加密工具只面向设备密码 | 抽出通用 secret 加密 helper，设备凭据继续复用原行为 |
| Webhook 外部服务慢或不可达 | 短超时、记录失败、后续重试，不阻塞告警主事务 |
| 通知事件重复创建 | 使用唯一约束和服务层幂等检查 |
| 敏感字段泄露 | Schema 层脱敏，日志只写摘要，测试覆盖不回显 |
| 前端告警组件继续膨胀 | 拆出 `AlertNotificationPanel.vue` |
| 未配置加密密钥但用户要创建通道 | 明确阻断，诊断和文档说明需要配置密钥 |

## 7. 验收清单

- [ ] 新增通知相关 Alembic 迁移，空库升级到 head 通过。
- [ ] Webhook 通道 CRUD 可用，读取响应脱敏。
- [ ] 未配置 `CREDENTIAL_ENCRYPTION_KEY` 时不能保存敏感 Webhook 配置。
- [ ] 策略 CRUD 可用，默认策略只通知 `critical triggered`。
- [ ] 删除被策略引用的通道返回 `409`。
- [ ] 告警触发后生成投递记录并尝试投递。
- [ ] 同一告警同一事件不会重复生成投递记录。
- [ ] 投递失败记录可见，可手动重试。
- [ ] 告警确认、手动恢复、自动恢复事件可按策略生成投递记录。
- [ ] 系统诊断展示通知摘要和失败 warning。
- [ ] 前端告警中心内可管理通道、策略和投递历史。
- [ ] README、API、部署、前端手工测试和 Postman 更新。
- [ ] 后端全量 pytest 通过。
- [ ] 前端 Vitest 通过。
- [ ] 前端 build 通过。
- [ ] 本地 API/前端冒烟通过。
- [ ] 提交并推送到 `origin/main`。
