# Wave 20 需求文档：告警通知与订阅策略

> 阶段：`requirement_doc`
> 状态：已实现，等待最终验收与提交
> 基线：Wave 19 已完成平台内告警中心、告警规则、告警确认/恢复、自动恢复、诊断摘要和前端告警入口。下一阶段应把“管理员登录后才能看到告警”推进为“关键告警可主动触达管理员”，但仍保持单实例、轻量、可测试的运维边界。

## 1. 背景

截至 Wave 19，平台已经具备：

- 管理员登录、JWT access/refresh token、修改密码和前端自动 refresh。
- 设备 CRUD、分组、标签、frps Dashboard 导入、设备级 SSH 凭据、凭据加密和 known_hosts 策略。
- Web SSH、VNC、设备文件管理、设备状态、设备指标、监控总览和系统诊断。
- 批量更新任务：目标预览、命令模板、dry-run、真实 SSH 执行、失败设备重试、结果 CSV 导出和 WebSocket 快照。
- 定时任务：配置管理、自动调度、立即执行、执行记录和调度器状态。
- 告警中心：设备状态、指标阈值、指标冻结、定时任务失败、批量任务失败告警，支持确认、恢复、规则启停和阈值编辑。
- 操作日志、README、API 文档、部署文档和 Postman Collection。

当前告警已经可以在平台内集中处理，但仍存在运维响应限制：

- 管理员必须主动打开前端才能看到新告警。
- 严重告警和普通告警没有不同的触达策略。
- 告警确认、恢复、自动恢复已有状态，但缺少通知投递记录，无法判断是否已通知到外部系统。
- 后续如果直接引入完整工单、排班或 RBAC，范围会过大，不适合在 Wave 20 一次完成。

Wave 20 的目标是新增轻量告警通知能力，优先支持 Webhook 和邮件这类通用通道，并提供可审计的投递记录、重试和前端配置入口。

## 2. 目标

Wave 20 完成后，系统应达到以下状态：

1. 平台可配置告警通知通道，至少支持 Webhook；邮件作为可选增强项。
2. 告警触发、确认、恢复等事件可按订阅策略投递到外部通道。
3. 通知策略支持按告警级别、来源和状态过滤，避免所有告警无差别刷屏。
4. 通知投递有独立记录，可查看成功、失败、重试次数和最近错误。
5. 投递失败不会影响告警创建、告警恢复、任务执行或主 API 可用性。
6. 前端新增通知配置与投递历史入口，所有文案继续使用中文。
7. 系统诊断展示通知模块摘要，便于部署后判断通道是否配置、是否有失败堆积。
8. API、迁移、测试、文档和 Postman 验收路径完整闭环。

## 3. 非目标

本轮不实现以下内容：

- 不实现完整工单系统、审批流、值班排班、升级策略或 SLA 计时。
- 不实现多用户 RBAC、项目级权限、团队订阅和个人通知偏好。
- 不实现短信、语音电话、企业微信、钉钉、Slack、飞书等所有专用平台的完整适配。
- 不实现复杂模板编辑器、富文本通知模板或多语言模板。
- 不实现通知中心实时 WebSocket 推送；前端仍通过普通 API 查看状态。
- 不引入外部消息队列、Redis、Celery 或分布式事件总线。
- 不保证后端进程停止期间的通知补偿投递；SQLite 单实例仍是基线。

## 4. 功能需求

### 4.1 通知通道

本轮建议新增通知通道实体，至少支持：

| 通道类型 | 是否必做 | 说明 |
| --- | --- | --- |
| `webhook` | 是 | 通用 HTTP POST，便于接入自建系统、企业机器人或自动化工具 |
| `email` | 待确认 | SMTP 邮件，适合无机器人平台的测试环境 |

Webhook 通道要求：

- 支持配置 URL。
- 支持配置可选 HTTP Header。
- 支持配置超时时间。
- 支持启用/停用。
- 支持发送测试通知。
- 请求体使用稳定 JSON 结构，不包含敏感凭据。

邮件通道如本轮确认支持，要求：

- SMTP 主机、端口、TLS/SSL、用户名、密码、发件人、收件人配置。
- SMTP 密码不得通过 API 响应返回。
- 可发送测试邮件。
- 部署文档说明常见邮件服务端口与安全注意事项。

### 4.2 通知策略

通知策略用于决定哪些告警事件应投递到哪些通道。

建议字段：

```text
id
name
enabled
channel_id
min_severity
source_types
alert_statuses
event_types
created_at
updated_at
```

策略语义：

- `min_severity=warning` 表示 warning 和 critical 都通知。
- `min_severity=critical` 表示只通知 critical。
- `source_types` 可为空，空表示所有来源。
- `alert_statuses` 可包含 `open`、`acknowledged`、`resolved`。
- `event_types` 可包含 `triggered`、`acknowledged`、`resolved`、`auto_resolved`。

默认策略建议：

- 默认不自动创建外部通道。
- 创建第一条 Webhook 通道后，可提示管理员创建默认策略。
- 默认策略建议只通知 `critical` 的 `triggered` 事件，避免测试环境通知噪音过大。

### 4.3 通知事件

需要定义清晰的告警事件来源。

至少支持：

- 告警新建或重新触发：`triggered`
- 告警被管理员确认：`acknowledged`
- 告警被管理员手动恢复：`resolved`
- 告警被系统自动恢复：`auto_resolved`

要求：

- 通知触发必须复用 Wave 19 告警状态变化，不重复创建另一套告警判断逻辑。
- 同一活跃告警持续触发时，不应每次指标上报都通知；需要节流或只在首次打开时通知。
- 若告警从 `resolved` 后再次进入新周期，可以再次发送通知。
- 通知事件要能关联 `alert_id`、告警标题、级别、来源、设备/任务 ID、当前状态和发生时间。

### 4.4 投递记录

通知投递必须可审计，建议新增 `alert_notification_deliveries`。

建议字段：

```text
id
alert_id
channel_id
policy_id
event_type
status
attempt_count
last_attempt_at
next_retry_at
response_status_code
response_summary
error_message
created_at
updated_at
```

状态建议：

- `pending`
- `success`
- `failed`
- `retrying`
- `skipped`

要求：

- 响应摘要长度必须限制，不保存完整外部响应大文本。
- `error_message` 不能包含明文密码、Token 或私钥。
- 投递记录按创建时间倒序展示。
- 投递成功、失败、重试都不应阻塞主业务流程。

### 4.5 重试与节流

通知投递必须避免外部通道短暂故障导致大量失败刷屏。

最低要求：

- 支持失败重试，默认最多 3 次。
- 支持简单退避，例如 1 分钟、5 分钟、15 分钟。
- 支持手动重试单条失败投递。
- 同一告警同一事件对同一通道只应生成一条投递记录。
- 告警持续触发更新时不重复发送 `triggered` 通知，除非进入新的告警周期。

本轮不要求：

- 精确分布式锁。
- 大规模队列吞吐。
- 对外部服务的高级限速协议。

### 4.6 数据模型建议

建议新增以下实体：

#### 4.6.1 alert_notification_channels

```text
id
name
channel_type
enabled
config
secret_config
last_test_status
last_test_at
last_error
created_at
updated_at
```

要求：

- `config` 保存非敏感配置，例如 URL、Headers 名称、超时时间、SMTP host。
- `secret_config` 保存敏感配置，例如 Webhook token、SMTP 密码。
- 若已有凭据加密能力可复用，应优先复用加密存储。
- API 响应不得返回 `secret_config` 明文。

#### 4.6.2 alert_notification_policies

```text
id
name
enabled
channel_id
min_severity
source_types
alert_statuses
event_types
created_at
updated_at
```

#### 4.6.3 alert_notification_deliveries

见 4.4。

### 4.7 API 需求

建议新增接口：

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

要求：

- 所有接口需要登录鉴权。
- 创建/更新通道时敏感字段允许写入，但读取时必须脱敏。
- 删除通道前若存在策略，应返回 `409` 或级联停用策略；具体行为需冻结。
- 测试通知必须写投递记录或测试记录，便于排查。
- 手动重试失败投递必须写操作日志。

### 4.8 前端通知管理

建议在“告警中心”内新增“通知配置”区域，或新增一级“通知配置”入口。

页面至少包含：

- 通知通道列表：
  - 名称
  - 类型
  - 启用状态
  - 最近测试状态
  - 最近错误
  - 操作：测试、编辑、停用、删除
- 通知策略列表：
  - 名称
  - 通道
  - 最小级别
  - 来源过滤
  - 事件类型
  - 启用状态
- 投递历史：
  - 告警标题
  - 通道
  - 策略
  - 事件类型
  - 状态
  - 尝试次数
  - 最近错误
  - 操作：重试

要求：

- 前端展示敏感字段时只显示“已配置/未配置”，不显示明文。
- 失败提示仅作用于通知配置区域，不导致登录态退出。
- 表单默认使用中文说明和清晰占位。
- Webhook JSON 示例可在文档中给出，页面不需要复杂模板编辑器。

### 4.9 诊断与部署

`GET /api/diagnostics/config` 建议新增 `notifications` 摘要：

```json
{
  "notifications": {
    "enabled_channel_count": 1,
    "enabled_policy_count": 1,
    "failed_delivery_count": 0,
    "retrying_delivery_count": 0,
    "last_delivery_at": "2026-05-27T10:00:00",
    "warnings": []
  }
}
```

要求：

- 只返回计数、状态和 warning，不返回 Webhook URL 中的敏感 token、SMTP 密码或 Header 值。
- 若存在连续失败投递，诊断页显示 warning。
- 部署文档说明 Nginx 无需新增 location，后端主动访问外部通道时需要服务器出站网络可用。

### 4.10 通知内容

Webhook 默认 JSON 建议：

```json
{
  "event_type": "triggered",
  "alert": {
    "id": 1,
    "title": "CPU 高负载",
    "severity": "critical",
    "status": "open",
    "source_type": "metric",
    "alert_type": "cpu_high",
    "device_id": 1,
    "message": "设备 edge-01 CPU 94% 超过阈值 85%",
    "created_at": "2026-05-27T10:00:00"
  },
  "platform": {
    "service_name": "edge-platform"
  }
}
```

要求：

- 不包含 access token、refresh token、设备 SSH 密码、私钥、passphrase、凭据加密密钥。
- 不复制完整远程命令输出。
- 长字段必须截断。

## 5. 安全要求

- Webhook Header、SMTP 密码等敏感字段不得通过 API 响应返回。
- 通知配置中的敏感字段应复用现有凭据加密能力；未配置加密密钥时，诊断页必须提示风险。
- 通知投递日志不得保存完整敏感请求头。
- Webhook URL 可能包含 token，前端展示时应脱敏。
- 测试通知和真实通知都不得绕过鉴权接口创建配置。
- 外部通知失败时不得把异常堆栈完整暴露给前端，只返回可排查摘要。

## 6. 兼容性要求

- Wave 20 不破坏 Wave 19 告警中心现有 API。
- 未配置通知通道时，告警创建、确认、恢复流程必须完全正常。
- 旧数据库升级后通知表为空，平台仍可启动。
- 诊断接口只新增向后兼容字段。
- Postman 旧请求继续可用。

## 7. 测试要求

后端测试至少覆盖：

- Webhook 通道创建、读取脱敏、更新、删除或停用。
- 通知策略创建、筛选条件生效。
- 告警触发后按策略生成投递记录。
- 同一告警同一事件不会重复生成多条投递记录。
- Webhook 投递成功记录 `success`。
- Webhook 投递失败记录 `failed` 或 `retrying`。
- 手动重试失败投递。
- 通知测试接口。
- 诊断接口通知摘要。
- Alembic 迁移创建通知相关表。

前端测试至少覆盖：

- 通知通道列表展示。
- 创建/编辑 Webhook 通道时敏感字段不回显。
- 测试通知按钮调用 API。
- 策略列表和启停编辑。
- 投递历史展示失败原因和重试入口。
- 通知配置接口失败不退出登录。

验证命令：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave20'

cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

## 8. 文档与 Postman

需要更新：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/frontend-manual-test-guide.md`
- `docs/postman/edge-platform.postman_collection.json`

文档必须说明：

- Wave 20 支持的通知通道类型。
- Webhook 请求体格式。
- 敏感字段脱敏和加密存储边界。
- 通知失败重试语义。
- 未配置通知通道时平台行为。
- 如何用 Postman 验收通道测试、策略配置、投递历史和手动重试。

## 9. 验收标准

Wave 20 只有在以下条件全部满足后才算完成：

- 可创建并启用 Webhook 通知通道。
- 可创建通知策略，并按级别、来源和事件类型过滤告警通知。
- 告警触发后能生成投递记录并尝试发送通知。
- 外部通道失败时主告警流程不受影响，失败记录可见且可重试。
- 前端可管理通知通道、策略和投递历史。
- 系统诊断可展示通知模块摘要和失败 warning。
- 新增 Alembic 迁移可从空库升级到 head。
- 后端全量 pytest 通过。
- 前端 Vitest 通过。
- 前端 build 通过。
- README、API、部署、前端手工测试和 Postman 同步更新。

## 10. 风险与约束

- 外部通知通道最容易引入敏感信息泄露，必须优先处理 URL、Header、SMTP 密码脱敏。
- Webhook 目标不可控，超时和失败必须隔离，不能拖慢告警创建 API。
- 如果通知策略默认过宽，测试环境可能产生大量噪音；默认应偏保守。
- SQLite 单实例适合轻量投递记录，不适合高吞吐通知队列。
- SMTP 在不同服务商上差异较大，若本轮引入邮件，需要接受部署复杂度上升。
- 当前平台仍是管理员单账号基线，通知订阅只能做平台级策略，不做用户级偏好。

## 11. 待确认问题

1. Wave 20 是否按“告警外部通知”推进，优先支持 Webhook？
2. 本轮是否同时支持邮件 SMTP，还是先只做 Webhook？
3. 通知配置入口放在“告警中心”内，还是新增一级“通知配置”导航？
4. 敏感配置是否必须复用 `CREDENTIAL_ENCRYPTION_KEY` 加密保存；未配置时是否允许保存但诊断提示风险？
5. 删除通知通道时，如果已有策略引用，是返回 `409` 要求先删除策略，还是自动停用相关策略？
6. 默认通知策略是否只通知 `critical` 的 `triggered` 事件？
7. 测试完成后是否继续统一提交并推送到 `origin/main`？

## 12. 已确认决策

根据用户确认，本轮冻结以下决策：

1. Wave 20 按“告警外部通知”推进，优先支持 Webhook。
2. 本轮只实现 Webhook 通知通道，不实现 SMTP 邮件通道。
3. 通知配置入口放在“告警中心”内，不新增一级导航。
4. Webhook Header、Token 等敏感配置必须复用 `CREDENTIAL_ENCRYPTION_KEY` 加密保存；未配置加密密钥时应拒绝保存敏感配置或给出明确阻断提示，避免新增明文秘密。
5. 删除通知通道前必须先删除或解除关联通知策略；若仍有策略引用，接口返回 `409`。
6. 默认通知策略只通知 `critical` 级别的 `triggered` 事件。
7. 需求确认后生成执行计划，计划批准后实现；测试完成后统一提交并推送到 `origin/main`。
