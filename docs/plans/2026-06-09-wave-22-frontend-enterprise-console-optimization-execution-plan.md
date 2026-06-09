# Wave 22 执行计划：前端企业级运维后台重构与体验统一

> 阶段：`xl_plan`
> 状态：待批准，执行前冻结
> 冻结需求：`docs/requirements/2026-06-09-wave-22-frontend-enterprise-console-optimization.md`

## 1. 执行目标

Wave 22 在 Wave 21 多用户与权限基础上，继续完成前端企业级运维后台化改造。核心目标是保留现有 API 和鉴权逻辑，统一页面结构、视觉层级、组件拆分、交互反馈和权限感知体验。

完成后应达到：

- 登录页、主布局、仪表盘、设备管理、远程连接、文件管理、批量更新、定时任务、告警中心、系统诊断、操作日志、用户管理风格统一。
- `App.vue` 从“大型页面容器”收敛为登录态、导航、健康状态和页面分发入口。
- 主要页面拆为独立视图组件，远程连接、批量任务、诊断卡片等拆为可维护业务组件。
- 继续使用 Vue 3 Composition API、TypeScript 和 Element Plus。
- 不改写后端 API、JWT、refresh token 和权限判断。
- operator 高风险入口隐藏或禁用，后端 `403` 仍是最终权限兜底。
- 所有错误、空状态、禁用原因和危险操作确认使用中文。
- 前端测试、类型检查、构建和浏览器冒烟通过。

## 2. 冻结决策

执行前建议冻结：

1. 本轮命名为 Wave 22，主题为“前端企业级运维后台重构与体验统一”。
2. 本轮优先前端实现，不修改后端 API、数据库和权限矩阵。
3. 保留现有测试用 `data-testid`，不得为视觉优化删除测试。
4. 允许引入 ECharts，但只用于仪表盘、告警、任务进度等关键图表。
5. operator 继续按 Wave 21 边界隐藏或禁用高风险入口。
6. 远程连接、文件管理、任务、告警通知等失败只做局部错误提示，除 `401` 外不清登录态。
7. 响应式验收覆盖 1366x768、1920x1080 和窄屏。
8. 测试通过后是否提交推送按用户后续确认执行。

## 3. 总体执行策略

本轮主要风险在“前端大文件拆分”和“视觉优化引入行为回归”。执行时应先固定现有测试基线，再按页面逐步拆分和验证。

推荐顺序：

1. 审计当前未提交前端改动、现有 API 类型、测试和样式覆盖。
2. 确认并保留已经完成的布局基线组件。
3. 从低风险页面开始拆分视图组件，再处理远程连接和批量更新这类强交互页面。
4. 统一状态组件、空状态、错误提示、权限提示和危险确认。
5. 补齐 operator 权限可见性和 `403` 不退出登录测试。
6. 做响应式样式修正和浏览器截图验收。
7. 更新前端手工测试文档和 README 相关说明。
8. 运行前端全量测试、类型检查、构建、`git diff --check`。
9. 清理临时文件，按用户确认提交或保留待审。

连续 3 次同类失败时停止实现并报告失败点、已尝试方案、当前判断和所需输入。

## 4. 工作拆分

### Step 1：基线审计与范围确认

阅读并确认当前模式：

- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `frontend/src/__tests__/app.spec.ts`
- `frontend/src/api/platform.ts`
- `frontend/src/api/health.ts`
- `frontend/src/components/LayoutShell.vue`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/AppTopbar.vue`
- `frontend/src/components/StatusBadge.vue`
- `frontend/src/components/MetricCard.vue`
- `frontend/src/components/DeviceDetailDrawer.vue`
- `frontend/src/components/AlertCenterPanel.vue`
- `frontend/src/components/ScheduledTaskPanel.vue`
- `frontend/src/components/UserManagementPanel.vue`
- `frontend/src/components/DeviceFilePanel.vue`

需要确认：

- 当前未提交改动是否全部属于前端优化范围。
- 登录态、`401`、`403`、refresh 和当前用户角色状态的调用链。
- 设备、远程连接、文件管理、批量更新、定时任务、告警和用户管理的 API mock 覆盖情况。
- 现有 `data-testid` 是否已覆盖关键入口。

阶段验证：

```powershell
git status --short
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run typecheck
```

### Step 2：布局基线与样式变量收敛

处理内容：

- 保留 `LayoutShell`、`AppSidebar`、`AppTopbar` 作为唯一主框架。
- 收敛 `styles.css` 中重复或旧版 `.app-shell`、`.sidebar` 等遗留样式影响。
- 固定主题变量：
  - 科技蓝主色。
  - 成功、警告、危险、信息状态色。
  - 浅灰背景和白色面板。
  - 表格、抽屉、弹窗和工具栏统一圆角、阴影、间距。
- 保证顶部状态栏在不同宽度下不重叠。
- 保证左侧导航分组、激活态和 admin-only 入口一致。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run typecheck
```

### Step 3：页面级组件拆分

建议新增：

- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/DeviceManagementView.vue`
- `frontend/src/views/FileManagementView.vue`
- `frontend/src/views/RemoteConnectionView.vue`
- `frontend/src/views/BatchUpdateView.vue`
- `frontend/src/views/OperationLogsView.vue`
- `frontend/src/views/DiagnosticsView.vue`

拆分要求：

- `App.vue` 继续持有认证状态、当前用户、全局健康、导航和页面切换。
- 页面组件通过 props 接收数据和操作函数，先不引入全局 store。
- 保留现有测试入口和 `data-testid`。
- 每拆出一个页面后运行前端 targeted test 或 typecheck。

推荐顺序：

1. `DashboardView`，风险低。
2. `OperationLogsView` 和 `DiagnosticsView`，主要展示型页面。
3. `FileManagementView`，保留设备选择和 `DeviceFilePanel`。
4. `DeviceManagementView`，注意详情抽屉和设备操作事件。
5. `RemoteConnectionView`，注意 xterm/noVNC DOM ref 生命周期。
6. `BatchUpdateView`，注意 WebSocket 快照、风险确认和任务详情。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
npm.cmd run typecheck
```

### Step 4：设备管理与文件管理体验补齐

设备管理：

- 统一筛选面板样式，关键词、分组、状态、标签、项目号均有中文占位。
- 表格列保持：设备名称、状态、项目号、分组、部署位置、SSH 端口、VNC 端口、最近指标时间、操作。
- 操作区在窄屏下可换行或收敛到更多按钮。
- 设备详情抽屉补齐 frpc 配置、SSH 凭据、最近指标、快捷操作和禁用原因。
- 删除设备必须确认。

文件管理：

- 无设备选择时显示空状态。
- 设备列表和设备管理状态标签一致。
- 文件上传、下载、删除失败局部提示。
- 文件删除或覆盖操作确认。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
```

### Step 5：远程连接工作区强化

处理内容：

- 继续使用左侧设备列表和右侧 Tabs。
- 抽出 `RemoteWorkspace.vue`、`SshTerminalPanel.vue`、`VncPanel.vue`。
- 搜索支持名称、序列号、项目号、位置。
- SSH/VNC 按钮根据端口和凭据状态禁用并显示原因。
- SSH 黑色终端区域固定最小高度，xterm 容器不被卡片挤压。
- VNC 区域提供连接、断开、全屏，空状态明确。
- 连接日志记录创建、成功、失败、断开和禁用原因。
- 连接失败局部显示，不触发登录态清理。

重点测试：

- SSH 创建失败后仍在远程连接页。
- VNC 创建失败后仍在远程连接页。
- 没有选择设备时不访问 session API。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
npm.cmd run typecheck
```

### Step 6：批量更新、定时任务和告警中心权限体验

批量更新：

- 抽出 `UpdateTaskForm.vue`、`UpdateTaskResultTable.vue`。
- `dry_run` 和 `ssh_command` 视觉区分。
- operator 不显示或不能提交 `ssh_command`。
- admin 提交 `ssh_command` 前必须二次确认。
- 任务详情展示实时进度、单设备结果、stdout/stderr 摘要、失败原因、失败重试和 CSV 导出。

定时任务：

- `ScheduledTaskPanel` 继续通过 `canManage` 控制创建、编辑、启停、删除。
- operator 对真实 SSH 手动执行显示无权限原因。
- 执行记录和日志区空状态清晰。

告警中心：

- 抽出 `AlertSummaryCards.vue`、`AlertRulePanel.vue`、`NotificationPanel.vue` 或整理现有组件职责。
- operator 可确认/恢复告警，但规则和通知配置只读或隐藏。
- 未配置凭据加密密钥时展示安全风险，不显示敏感明文。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
npm.cmd run typecheck
```

### Step 7：系统诊断、操作日志和用户管理统一

系统诊断：

- 抽出 `DiagnosticCard.vue`。
- 将 API、数据库、迁移、调度器、认证配置、SSH 主机密钥、文件后端、告警摘要、通知摘要、用户摘要统一为诊断卡片。
- 安全风险使用 `el-alert` 或统一风险条展示。
- 不展示密码、Token、私钥、Webhook 明文密钥。

操作日志：

- 统一筛选：action、target_type、status、用户、时间范围。
- 统一表格、分页、CSV 导出和详情抽屉样式。
- 请求/响应/执行日志详情脱敏展示。

用户管理：

- 仅 admin 可见。
- 保留新增、编辑、重置密码、启停。
- 最后一个 admin 限制错误使用中文提示。
- 不回显旧密码和 hash。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run src/__tests__/app.spec.ts
```

### Step 8：测试补强

新增或扩展 `frontend/src/__tests__/app.spec.ts`：

- 登录页空用户名/空密码只显示一条错误。
- 错误密码只显示一条错误。
- admin 登录可见用户管理。
- operator 登录不可见用户管理。
- operator 不可提交真实 SSH 批量任务。
- operator 不可编辑告警规则和通知配置。
- 设备缺 SSH/VNC 端口或凭据时按钮禁用。
- SSH/VNC 创建失败不回登录页。
- `403` 不清登录态。
- 文件管理未选择设备显示空状态。
- 危险操作触发确认弹窗。

阶段验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
```

### Step 9：响应式与浏览器冒烟

启动本地前端：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5177
```

冒烟路径：

1. 登录页。
2. 仪表盘。
3. 设备管理和设备详情抽屉。
4. 文件管理。
5. 远程连接 SSH/VNC Tabs。
6. 批量更新任务创建和详情。
7. 定时任务列表和执行记录。
8. 告警中心、规则和通知配置。
9. 系统诊断。
10. 操作日志。
11. 用户管理。

尺寸检查：

- 1366x768。
- 1920x1080。
- 窄屏。

检查项：

- 无明显遮挡、重叠、按钮文字溢出。
- 抽屉宽度合理。
- 表格操作列可用。
- 顶栏状态不挤压。
- 远程终端和 VNC 区域非空且可见。

### Step 10：文档、验证和收尾

文档更新：

- `README.md`
- `docs/frontend-manual-test-guide.md`

如本轮没有后端 API 变化，不更新 API 文档；如发现现有字段说明缺失，可补充说明。

最终验证：

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd run test -- --run
npm.cmd run typecheck
npm.cmd run build

cd C:\01_work\02_program\远程终端平台
git diff --check
git status --short
```

收尾要求：

- 不提交 `frontend/dist`、临时截图、日志、本地数据库或缓存。
- 如引入 ECharts，确认 `package.json` 和 lockfile 更新合理。
- 记录 Vite 大 chunk 警告，如未新增明显劣化可作为非阻塞项。
- 按用户确认决定是否提交和推送。

## 5. 关键实现约束

- 不重写后端接口。
- 不改变认证、refresh token 和权限判断语义。
- 不删除现有测试。
- 不移除已有 `data-testid`。
- 不用前端隐藏替代后端权限。
- 不在 UI、日志或文档中展示敏感信息。
- 不为了视觉效果引入大面积不可维护 CSS 覆盖。
- 不把 landing page 当成应用首页；登录后直接进入真实仪表盘。

## 6. 风险与回退

| 风险 | 处理 |
| --- | --- |
| 页面拆分导致大量 prop 传递混乱 | 先拆展示型页面，再拆强交互页面；必要时保留局部逻辑在 App 中 |
| xterm/noVNC 容器生命周期被破坏 | 远程连接页面最后拆，拆完立即运行远程连接测试 |
| 视觉样式影响 Element Plus 弹窗/抽屉 | 使用页面级 class 限定，不做全局深度覆盖 |
| 现有测试因结构变化失败 | 保留 `data-testid`，按用户可见行为修正测试 |
| operator 权限 UI 与后端不一致 | 前端隐藏加后端 `403` 双保险，测试覆盖两层 |
| ECharts 增加包体 | 仅用于必要图表，构建记录 chunk warning |

## 7. 验收清单

- [ ] Wave 22 需求文档和执行计划已确认。
- [ ] 主布局统一使用 `LayoutShell`、`AppSidebar`、`AppTopbar`。
- [ ] `App.vue` 页面逻辑明显收敛。
- [ ] 登录页错误提示不重复。
- [ ] 仪表盘指标、状态分布、告警、任务和日志展示稳定。
- [ ] 设备管理筛选、表格、详情抽屉和 SSH/VNC/文件入口可用。
- [ ] 文件管理一级入口和无设备空状态可用。
- [ ] 远程连接 SSH/VNC/日志 Tabs 可用，失败不退出登录。
- [ ] 批量更新真实 SSH 操作有权限控制和二次确认。
- [ ] 定时任务管理入口按角色控制。
- [ ] 告警规则和通知配置按角色控制。
- [ ] 系统诊断不展示敏感信息。
- [ ] 操作日志筛选、详情和导出入口可用。
- [ ] 用户管理仅 admin 可见。
- [ ] 1366x768、1920x1080 和窄屏无明显遮挡或溢出。
- [ ] 前端 Vitest 通过。
- [ ] 前端 typecheck 通过。
- [ ] 前端 build 通过。
- [ ] `git diff --check` 通过。
- [ ] 文档更新完成。

## 8. 建议提交策略

如果用户确认本轮实现后需要提交，建议提交信息：

```text
feat: polish frontend operations console
```

提交前必须确认：

- 只包含 Wave 22 前端优化和对应文档。
- 不包含临时运行文件、截图、数据库、日志或构建产物。
- 验证命令结果已记录。
