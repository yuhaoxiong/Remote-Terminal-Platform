# Wave 19 执行计划：告警中心与设备健康事件闭环

> 阶段：`xl_plan`  
> 状态：待确认，确认后进入实现  
> 冻结需求：`docs/requirements/2026-05-22-wave-19-alert-center-and-device-health-closure.md`

## 1. 执行目标

Wave 19 将当前分散在仪表盘、设备指标、批量任务、定时任务和操作日志中的异常事实，收敛为统一“告警中心”。

完成后应达到：

- 新增告警数据模型、规则模型和 Alembic 迁移。
- 设备状态异常、指标超阈值、指标过期、定时任务失败、批量任务失败可形成告警。
- 同一活跃异常按 `dedupe_key` 聚合，不重复刷屏。
- 告警支持 `open`、`acknowledged`、`resolved` 状态流转。
- 定时任务后续成功后自动恢复上一轮失败告警。
- 支持告警规则启停和阈值编辑，默认阈值为 CPU `85%`、内存 `85%`、磁盘 `90%`、指标过期 `10` 分钟。
- 从未上报指标的设备只提示“暂无指标”，不直接生成告警。
- 前端新增“告警中心”入口，支持摘要、筛选、确认、恢复和规则配置。
- 仪表盘和系统诊断展示告警摘要。
- README、API、部署文档和 Postman Collection 同步更新。
- 测试完成后统一提交并推送到 `origin/main`。

## 2. 冻结决策

1. Wave 19 只做平台内告警中心，不接入 Webhook、邮件、短信或第三方通知。
2. 默认指标阈值固定为 CPU `85%`、内存 `85%`、磁盘 `90%`，指标过期窗口为 `10` 分钟。
3. 从未上报指标的设备不直接生成告警，只在前端保持“暂无指标”提示。
4. 同一定时任务后续成功执行后，自动恢复上一轮仍活跃的失败告警。
5. 本轮开放规则启停和阈值编辑 API/前端，但不做复杂规则表达式、脚本规则或插件规则。
6. 需求、计划和实现测试完成后统一提交并推送。

## 3. 总体执行策略

本轮是横切能力，风险在于触发点散落到多个业务模块。执行时应先建立统一服务边界，再让各业务模块只调用少量稳定入口。

推荐顺序：

1. 审计设备、指标、批量任务、定时任务和诊断现有路径。
2. 新增枚举、模型、迁移和默认规则初始化。
3. 实现告警服务：触发、去重、自动恢复、确认、手动恢复、摘要和规则管理。
4. 接入后端触发点：指标写入、设备状态变化、批量任务执行收口、定时任务执行结果、周期扫描。
5. 新增告警 API 与诊断摘要。
6. 扩展前端 API、告警中心页面、仪表盘摘要和诊断页摘要。
7. 更新文档和 Postman。
8. 跑完整验证，清理临时文件，统一提交推送。

任何阶段连续 3 次失败，应停止并报告失败点、根因和替代方案。

## 4. 工作拆分

### Step 1：基线审计与影响面确认

阅读并确认当前模式：

- `backend/app/enums.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/models/device.py`
- `backend/app/models/metric.py`
- `backend/app/models/update_task.py`
- `backend/app/models/scheduled_task.py`
- `backend/app/models/log.py`
- `backend/app/services/monitoring_service.py`
- `backend/app/services/device_service.py`
- `backend/app/services/update_task_service.py`
- `backend/app/services/scheduled_task_service.py`
- `backend/app/services/scheduler_service.py`
- `backend/app/services/operation_log.py`
- `backend/app/routers/devices.py`
- `backend/app/routers/update_tasks.py`
- `backend/app/routers/scheduled_tasks.py`
- `backend/app/routers/monitoring.py`
- `backend/app/routers/diagnostics.py`
- `frontend/src/api/platform.ts`
- `frontend/src/App.vue`
- `frontend/src/components/ScheduledTaskPanel.vue`
- `frontend/src/components/UpdateTaskResultTable.vue`
- `frontend/src/__tests__/app.spec.ts`

需要确认：

- 指标创建路径是否集中在 `MonitoringService`。
- 设备状态更新路径是否集中在 `DeviceService` 和设备 router。
- 批量任务完成状态在何处最终落库。
- 定时任务运行成功/失败在何处更新 run 记录。
- 当前诊断响应是否适合追加 `alerts` 摘要。
- 前端是否继续在 `App.vue` 内挂一级页面，还是拆出 `AlertCenterPanel.vue`。

产出：

- 不单独生成审计文档。
- 若发现某个触发点无法稳定挂接，应在实现前调整本计划并说明。

阶段验证：

```powershell
git status --short
```

### Step 2：枚举、模型和迁移

新增枚举建议：

- `AlertSeverity`
  - `warning`
  - `critical`
- `AlertStatus`
  - `open`
  - `acknowledged`
  - `resolved`
- `AlertSourceType`
  - `device`
  - `metric`
  - `scheduled_task`
  - `update_task`
- `AlertRuleType`
  - `device_status`
  - `cpu_high`
  - `memory_high`
  - `disk_high`
  - `metrics_stale`
  - `scheduled_task_failed`
  - `update_task_failed`

新增模型文件建议：

- `backend/app/models/alert.py`

新增模型：

- `Alert`
- `AlertRule`

新增迁移：

- `backend/alembic/versions/<revision>_wave19_alert_center.py`

迁移内容：

- 新增 `alerts` 表。
- 新增 `alert_rules` 表。
- 增加必要索引：
  - `alerts.dedupe_key`
  - `alerts.status`
  - `alerts.severity`
  - `alerts.source_type/source_id`
  - `alerts.device_id`
  - `alerts.last_triggered_at`
  - `alert_rules.rule_type`

默认规则：

| rule_type | enabled | severity | threshold_value | window_minutes |
| --- | --- | --- | --- | --- |
| `device_status` | true | `warning` | null | null |
| `cpu_high` | true | `warning` | 85 | null |
| `memory_high` | true | `warning` | 85 | null |
| `disk_high` | true | `critical` | 90 | null |
| `metrics_stale` | true | `warning` | null | 10 |
| `scheduled_task_failed` | true | `critical` | null | null |
| `update_task_failed` | true | `critical` | null | null |

要求：

- 空库升级到 head 后规则表有默认规则。
- 旧库升级不会破坏已有数据。
- `create_all` 兼容兜底仍可运行。
- 默认规则初始化应幂等，避免重启重复插入。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_migrations.py tests/test_database_migrations.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-migration'
```

### Step 3：Schema 和服务接口

新增 Schema 文件建议：

- `backend/app/schemas/alert.py`

核心 Schema：

- `AlertRead`
- `AlertListResponse`
- `AlertSummaryResponse`
- `AlertAcknowledgeRequest`
- `AlertResolveRequest`
- `AlertRuleRead`
- `AlertRuleUpdate`
- `AlertRuleListResponse`

新增服务文件：

- `backend/app/services/alert_service.py`

服务方法建议：

- `ensure_default_rules(session)`
- `trigger_alert(session, *, alert_type, severity, source_type, source_id, dedupe_key, title, summary, detail=None, device_id=None)`
- `resolve_by_dedupe_key(session, dedupe_key, resolved_by="system", note=None)`
- `resolve_matching(session, *, alert_type, source_type, source_id, device_id=None)`
- `list_alerts(session, filters, offset, limit)`
- `summary(session)`
- `acknowledge(session, alert_id, note, user_id)`
- `resolve(session, alert_id, note, user_id)`
- `list_rules(session)`
- `update_rule(session, rule_id, payload)`
- `evaluate_device_metrics(session, device, latest_metric)`
- `evaluate_device_status(session, device)`
- `evaluate_metrics_staleness(session, now=None)`
- `handle_scheduled_task_run(session, task, run)`
- `handle_update_task_completed(session, task)`

去重语义：

- 活跃告警查找范围为 `open` 和 `acknowledged`。
- 重复触发同一 `dedupe_key` 时更新：
  - `last_triggered_at`
  - `trigger_count`
  - `summary`
  - `detail`
  - `severity`
- 已 `resolved` 的旧告警不复用，新的异常周期新建告警。

恢复语义：

- 指标恢复正常后，自动恢复对应指标告警。
- 设备恢复在线后，自动恢复设备状态告警。
- 定时任务成功后，自动恢复同一任务的失败告警。
- 批量任务失败默认不自动恢复，由管理员确认或手动恢复。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave19_alerts.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-service'
```

### Step 4：触发点接入

#### 4.1 指标写入触发

接入位置：

- `backend/app/services/monitoring_service.py`
- 或 `backend/app/routers/devices.py` 的指标创建路径

行为：

- 指标写入成功后，对该设备最新指标执行规则判断。
- CPU、内存、磁盘超过阈值时触发对应告警。
- 指标恢复正常时自动恢复对应活跃告警。
- 从未上报指标的设备不告警。

#### 4.2 设备状态触发

接入位置：

- `backend/app/services/device_service.py`
- 设备创建/更新/状态变更路径

行为：

- `offline` 触发 `critical` 告警。
- `unknown`、`degraded` 触发 `warning` 告警。
- 恢复 `online` 后自动恢复设备状态告警。

#### 4.3 指标过期扫描

接入位置：

- 可复用 Wave 18 `SchedulerService.scan_due_tasks()` 的周期扫描思路。
- 也可新增 `AlertEvaluationService` 并在调度器扫描中调用。

行为：

- 最近指标超过规则窗口时触发 `metrics_stale`。
- 从未上报指标的设备只在前端显示“暂无指标”，不触发告警。
- 后续指标更新且未过期时自动恢复过期告警。

#### 4.4 定时任务执行结果触发

接入位置：

- `backend/app/services/scheduled_task_service.py`

行为：

- run `failed` 时触发 `scheduled_task_failed`。
- 同一任务后续 run `success` 时自动恢复上一轮失败告警。
- `skipped` 是否告警按实现阶段判断，默认不作为失败告警。

#### 4.5 批量任务结果触发

接入位置：

- `backend/app/services/update_task_service.py`

行为：

- 任务最终为 `partial_failed` 或存在失败设备结果时触发 `update_task_failed`。
- detail 记录失败设备数量和错误摘要，不复制完整 stdout/stderr。
- 不自动恢复，由管理员确认或手动恢复。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_monitoring_api.py tests/test_wave18_scheduler.py tests/test_wave10_update_task_ssh_execution.py tests/test_wave19_alerts.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-triggers'
```

### Step 5：API Router

新增 router：

- `backend/app/routers/alerts.py`

新增接口：

```http
GET /api/alerts
GET /api/alerts/summary
POST /api/alerts/{alert_id}/acknowledge
POST /api/alerts/{alert_id}/resolve
GET /api/alert-rules
PUT /api/alert-rules/{rule_id}
```

列表筛选：

- `status`
- `severity`
- `source_type`
- `device_id`
- `alert_type`
- `offset`
- `limit`

操作日志：

- 确认告警：
  - `alert.acknowledge`
- 手动恢复告警：
  - `alert.resolve`
- 更新规则：
  - `alert_rule.update`

要求：

- 所有接口需要登录鉴权。
- 未找到告警或规则返回 `404`。
- 非法状态/级别/规则类型返回 `422`。
- 响应不返回敏感凭据。

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave19_alerts_api.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-api'
```

### Step 6：诊断和仪表盘后端摘要

诊断扩展：

- `backend/app/schemas/diagnostics.py`
- `backend/app/routers/diagnostics.py`

新增 `alerts` 摘要：

```json
{
  "alerts": {
    "enabled": true,
    "active_count": 2,
    "critical_count": 1,
    "last_evaluated_at": "2026-05-25T10:00:00",
    "last_error": null,
    "warnings": []
  }
}
```

告警摘要接口：

- `GET /api/alerts/summary`

响应建议包含：

- `active_count`
- `critical_count`
- `unacknowledged_count`
- `latest_alert_at`
- `by_source`
- `by_severity`

阶段验证：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_diagnostics_api.py tests/test_wave19_alerts_api.py --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-diagnostics'
```

### Step 7：前端 API 类型和客户端

修改：

- `frontend/src/api/platform.ts`

新增类型：

- `AlertSeverity`
- `AlertStatus`
- `AlertSourceType`
- `AlertRead`
- `AlertListResponse`
- `AlertSummaryResponse`
- `AlertRuleRead`
- `AlertRuleUpdateRequest`
- `AlertRuleListResponse`

新增 API：

- `listAlerts(params)`
- `getAlertSummary()`
- `acknowledgeAlert(id, payload)`
- `resolveAlert(id, payload)`
- `listAlertRules()`
- `updateAlertRule(id, payload)`

要求：

- 类型字段与后端 snake_case 保持一致。
- API 错误由页面局部处理，不触发登录态清理，除非后端返回真实 `401/403`。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
```

### Step 8：前端告警中心页面

建议新增组件：

- `frontend/src/components/AlertCenterPanel.vue`

修改：

- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `frontend/src/__tests__/app.spec.ts`

页面结构：

- 顶部摘要条：
  - 活跃告警
  - 严重告警
  - 未确认告警
  - 最近告警时间
- 筛选工具条：
  - 状态
  - 级别
  - 来源
  - 设备
  - 刷新按钮
- 告警表格：
  - 级别
  - 标题
  - 来源
  - 关联对象
  - 触发次数
  - 首次触发
  - 最近触发
  - 状态
  - 操作
- 规则配置区：
  - 规则名称
  - 启用开关
  - 级别
  - 阈值
  - 窗口
  - 保存

交互：

- 点击“确认”弹出说明输入或轻量表单。
- 点击“恢复”弹出确认。
- 点击关联设备/任务时切换到对应页面或保留为可追踪 ID，执行阶段按现有导航能力决定。
- 保存规则后刷新规则列表和摘要。

设计约束：

- 不使用营销式卡片堆叠。
- 告警中心应偏运维工作台风格，信息密度高、布局清晰。
- 文案全部中文。
- 表格内容不得挤压到不可读，移动端至少保证横向滚动或合理折行。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

### Step 9：仪表盘和系统诊断前端增强

仪表盘：

- 在现有概览区加入告警摘要。
- 保留现有异常设备摘要，但可增加“查看告警中心”入口。
- 无告警时显示“暂无活跃告警”。

系统诊断：

- 展示告警模块状态：
  - 是否启用。
  - 活跃告警数。
  - 严重告警数。
  - 最近评估时间。
  - 最近错误。

测试：

- mock `getAlertSummary()`。
- mock `diagnostics.alerts`。
- 覆盖告警摘要展示和局部失败状态。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
```

### Step 10：文档和 Postman

更新：

- `README.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/postman/edge-platform.postman_collection.json`

README：

- 当前能力增加告警中心。
- API 概览增加 `/api/alerts` 和 `/api/alert-rules`。
- Wave 19 补充说明。
- 最近验证记录更新。

API 文档：

- 告警接口。
- 告警规则接口。
- 诊断响应新增 `alerts`。
- 告警状态、级别、来源枚举说明。

部署文档：

- 默认阈值。
- 告警评估边界。
- SQLite 单实例说明。
- 没有外部通知通道的限制。

Postman：

- 新增 “Wave 19 告警中心” 分组：
  - 查询告警摘要。
  - 查询告警列表。
  - 确认告警。
  - 手动恢复告警。
  - 查询告警规则。
  - 更新告警规则。

阶段验证：

```powershell
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman json ok')"
git diff --check
```

### Step 11：完整验证与浏览器冒烟

后端全量：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave19-full'
```

前端：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

Postman JSON：

```powershell
node -e "JSON.parse(require('fs').readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman json ok')"
```

浏览器冒烟：

- 启动后端 `127.0.0.1:8000`。
- 使用现有前端 dev server 或启动 `127.0.0.1:5177`。
- 登录。
- 打开“告警中心”。
- 确认摘要、列表、规则区可见。
- 打开“系统诊断”，确认告警摘要可见。
- 控制台无前端错误。

### Step 12：清理、提交和推送

清理：

- 删除 `.pytest-tmp-wave19-*`。
- 确认无临时数据库、构建产物或本地日志被误暂存。

最终检查：

```powershell
git status --short
git diff --check
```

提交：

```powershell
git add README.md backend docs frontend
git commit -m "Implement Wave 19 alert center"
git push origin main
```

## 5. 风险控制

### 风险 1：告警触发点散落导致重复或遗漏

控制：

- 所有触发点只调用 `AlertService`。
- `AlertService` 统一负责 dedupe、状态流转和恢复。
- 测试覆盖同一异常重复触发不重复创建。

### 风险 2：指标类告警噪音过多

控制：

- 默认阈值按冻结决策实现。
- 从未上报指标不告警。
- 规则可禁用，可调整阈值。

### 风险 3：定时任务失败和批量任务失败重复告警

控制：

- 定时任务失败告警按 `scheduled_task:{id}` 维度去重。
- 批量任务失败告警按 `update_task:{id}` 维度去重。
- 若定时任务创建的批量任务失败，执行阶段需明确是否只保留定时任务失败告警或同时保留关联批量任务告警；默认策略建议保留定时任务告警，批量任务详情用于追踪。

### 风险 4：规则编辑影响系统稳定性

控制：

- 规则编辑只允许启停、级别、阈值和窗口。
- 不开放表达式和脚本。
- 阈值必须有范围校验。
- 禁用规则不删除历史告警。

### 风险 5：前端页面继续挤压 `App.vue`

控制：

- 告警中心独立为 `AlertCenterPanel.vue`。
- `App.vue` 只负责导航、摘要接入和页面切换。

## 6. 验收清单

- [ ] 新增 `alerts` 和 `alert_rules` 表迁移。
- [ ] 默认规则可幂等初始化。
- [ ] CPU/内存/磁盘超阈值可触发告警。
- [ ] 指标恢复正常可自动恢复指标告警。
- [ ] 指标过期可触发告警。
- [ ] 从未上报指标的设备不直接告警。
- [ ] 设备离线/未知/降级可触发告警。
- [ ] 设备恢复在线可自动恢复设备状态告警。
- [ ] 定时任务失败可触发告警。
- [ ] 定时任务后续成功可自动恢复失败告警。
- [ ] 批量任务失败可触发告警。
- [ ] 同一活跃异常重复触发不重复创建告警。
- [ ] 告警列表筛选和分页可用。
- [ ] 告警摘要接口可用。
- [ ] 告警确认可用并写操作日志。
- [ ] 告警手动恢复可用并写操作日志。
- [ ] 告警规则读取、启停和阈值更新可用。
- [ ] 诊断接口展示告警摘要。
- [ ] 前端“告警中心”一级入口可用。
- [ ] 前端告警列表、筛选、确认、恢复可用。
- [ ] 前端规则配置区可用。
- [ ] 仪表盘展示告警摘要。
- [ ] 系统诊断页展示告警摘要。
- [ ] README/API/部署文档更新。
- [ ] Postman 新增 Wave 19 分组且 JSON 可解析。
- [ ] 后端全量 pytest 通过。
- [ ] 前端 Vitest 通过。
- [ ] 前端 build 通过。
- [ ] 浏览器冒烟通过。
- [ ] `git diff --check` 通过。
- [ ] 测试完成后提交并推送。

## 7. 待批准

本计划等待用户批准后进入实现阶段。

