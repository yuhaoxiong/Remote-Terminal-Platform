# Wave 13 执行计划：监控指标与仪表盘可观测性

> Vibe run id: `20260518T070354Z-884f4164`  
> 阶段：`xl_plan`  
> 状态：待确认，确认后进入执行与清理阶段  
> 冻结需求：`docs/requirements/2026-05-18-continue-vibe-wave-13-wave-13-17-deliverable-governed-implementa.md`

## 1. 执行目标

Wave 13 以“真实指标可见、无指标不误导、异常设备可定位、诊断可确认”为交付边界。实现后，管理员在登录后的仪表盘和系统诊断页中可以看到设备最新 CPU、内存、磁盘指标、指标过期状态、异常设备摘要和监控可用性摘要。

## 2. 冻结决策

- 允许引入 ECharts。
- 指标过期阈值固定为 10 分钟。
- 最新指标沿用每台设备 `GET /api/devices/{id}/metrics?limit=1` 查询，不新增批量最新指标接口。
- Postman 需要提供一条示例指标上报请求，默认写入当前 `device_id`。
- 指标加载失败只做局部降级，不得把用户踢回登录页，除非接口明确返回 401/403。

## 3. 工作拆分

### Step 1：基线核验与失败用例

负责人：主线程  
范围：`backend/tests`、`frontend/src/__tests__`

- 先运行现有后端监控测试，确认 `limit=1`、空指标、未登录、设备不存在等行为是否已有覆盖。
- 在前端测试中补齐失败优先用例：
  - 有指标时显示真实 CPU / 内存 / 磁盘。
  - 无指标时显示“暂无指标”，不能显示假 `0%`。
  - 指标超过 10 分钟显示“指标过期”。
  - 资源高负载进入“异常设备”区域。
  - 指标接口失败后仍停留在登录后的页面。
  - 诊断页展示有指标设备数、无指标设备数、最近指标时间。

验收：目标测试在实现前能暴露缺口，或明确记录已有覆盖无需新增后端失败用例。

### Step 2：前端 API 与数据模型

负责人：主线程  
范围：`frontend/src/api/platform.ts`、`frontend/src/App.vue`

- 新增 `DeviceMetricRead`、`DeviceMetricListResponse` 类型。
- 新增 `listDeviceMetrics(deviceId, limit = 20)` 方法。
- 扩展前端设备 UI 模型：
  - `cpu`
  - `memory`
  - `disk`
  - `metricRecordedAt`
  - `metricStale`
  - `metricLoadFailed`
- 在 `loadPlatformData()` 中加载设备后，对每台设备并发请求 `limit=1` 最新指标。
- 单设备指标失败只标记该设备 `metricLoadFailed`，整体失败显示局部提示。
- 只有 401/403 走登录失效处理。

验收：前端状态中不再把缺失指标映射为 `0`。

### Step 3：仪表盘监控展示

负责人：主线程  
范围：`frontend/src/App.vue`、样式文件

- 改造“资源快照”，显示 CPU / 内存 / 磁盘三项。
- 有指标显示百分比和进度条；无指标显示“暂无指标”；过期显示“指标过期”；失败显示“指标加载失败”。
- 新增“异常设备”区域，最多显示 8 条，异常来源包括离线、未知、高 CPU、高内存、高磁盘、指标过期。
- 保留跳转设备管理和筛选入口。

验收：仪表盘关键数字和异常说明均为中文，状态清晰且不互相遮挡。

### Step 4：ECharts 基础可视化

负责人：主线程  
范围：`frontend/package.json`、`frontend/src/App.vue`

- 引入 `echarts`。
- 新增设备状态分布图或资源风险分布图，至少覆盖：
  - 在线、离线、未知、异常。
  - 正常、CPU 高、内存高、磁盘高、无指标。
- 无数据时显示中文空状态。
- 构建后记录产物大小变化以及是否出现 chunk warning。

验收：图表是辅助信息，文字摘要仍完整可读。

### Step 5：诊断页监控可用性

负责人：主线程  
范围：`frontend/src/App.vue`

- 在系统诊断页增加监控可用性摘要：
  - 有指标设备数。
  - 无指标设备数。
  - 最近指标时间。
- 数据优先来自前端已加载的最新指标，不新增复杂后端诊断接口。

验收：部署后可以通过诊断页判断是否已有设备上报指标。

### Step 6：文档与 Postman

负责人：主线程  
范围：`README.md`、`docs/api.md`、`docs/deployment.md`、`docs/postman/edge-platform.postman_collection.json`

- README 增加 Wave 13 监控可观测性说明。
- API 文档补充指标上报、最新指标查询、监控总览和前端展示规则。
- 部署文档补充服务器测试时如何写入示例指标并验证前端展示。
- Postman 增加：
  - 示例指标上报。
  - 查询设备最新指标。
  - 查询监控总览。
- 示例指标上报默认使用当前环境中的 `device_id`。

验收：Postman 可直接用于手动写入指标并验证仪表盘。

## 4. 验证计划

后端：

```powershell
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp-wave13'
```

前端：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

文档与格式：

```powershell
git diff --check
```

手动验收：

- 登录平台，确认仪表盘不再显示无指标设备的假 `0%`。
- 通过 Postman 上报一条指标，刷新仪表盘确认真实指标显示。
- 修改上报时间或测试数据，确认 10 分钟过期提示。
- 模拟指标接口失败，确认页面不闪退回登录页。

## 5. 风险与回滚

- ECharts 可能增加 bundle 体积；若构建出现 chunk warning，本轮接受但必须记录。
- 每台设备一个最新指标请求会随设备数增长；本轮按冻结决策实现，后续 Wave 再评估批量接口。
- 指标接口失败处理必须限定在监控区域，避免破坏 Wave 8 已修复的登录态稳定性。
- 若实现失败，回滚范围限定在 Wave 13 改动文件，不回滚已有 Wave 12 交付。

## 6. 完成定义

- 需求中的新增前端文案全部为中文。
- 后端测试、前端测试、前端构建通过。
- 文档和 Postman 更新完成。
- 最终说明记录 ECharts 构建影响。
- Vibe 后续阶段完成 phase cleanup，并留下执行与清理证明。
