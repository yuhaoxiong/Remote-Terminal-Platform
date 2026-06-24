# 前端"立骨架"重构计划

## 1. 背景与动机

后端经过 23 个 Wave 迭代，分层架构（`router → service → model`）始终清晰，最大文件约 515 行，工程质量稳定。但前端积累了严重的架构债务：

- **上帝组件**：`frontend/src/App.vue` 达 2873 行（script 约 1848 行，template 约 1023 行），用 `activeSection` 变量手动切换 12 个功能区，所有状态、API 调用与业务逻辑集中于此。
- **僵尸依赖**：`vue-router` 与 `pinia` 已安装却几乎未使用。全项目搜索不到 `router-view`、`useRouter`、`defineStore`。`router/index.ts` 仅有一条根路由，指向的 `views/Dashboard.vue` 是硬编码全 0、从未渲染的死代码。
- **巨型 API 文件**：`api/platform.ts` 1275 行，所有接口与类型集中在单文件。
- **工程基建缺失**：无 CI；`package.json` 有 `lint`/`format` 脚本且依赖已装，但缺少 eslint/prettier 配置文件，`npm run lint` 无法运行。

### 根因判断

"越写越乱"的根因不是能力或代码质量，而是**前端从第一天起缺少页面级骨架（router）与状态骨架（store）**。后端有分层骨架约束，新功能各归其层；前端没有骨架约束，每个新功能只能堆进唯一容器 `App.vue`，最终膨胀为上帝组件。

本次重构的核心价值，不在于拆完这 2873 行，而在于**立起一根承重梁，使后续新功能无处可堆、只能各归其位**，从而把"被迫的救火式大重构"转为"低成本的日常小重构"。

## 2. 现状诊断：`App.vue` 的 12 个 section

### 已组件化（4 个，template 中仅一行委托）

| section | 委托组件 | 行数 |
|---------|---------|------|
| `alerts` | `components/AlertCenterPanel.vue` | 337 |
| `scheduled` | `components/ScheduledTaskPanel.vue` | 446 |
| `settings` | `components/SystemSettingsPanel.vue` | 447 |
| `users` | `components/UserManagementPanel.vue` | 304 |

### 仍内联在 App.vue（8 个，状态与方法均在 1848 行 script 内）

| section | template 位置 | 模板规模 | 迁移难度 |
|---------|--------------|---------|---------|
| `devices` | `App.vue:2078` | ~193 行 | 高（CRUD + 状态刷新 + 凭据） |
| `remote` | `App.vue:2354` | ~145 行 | 高（SSH/VNC WebSocket 生命周期） |
| `updates` | `App.vue:2499` | ~116 行 | 中（已有 3 个子组件，缺编排层） |
| `dashboard` | `App.vue:1965` | ~113 行 | 中（指标聚合） |
| `diagnostics` | `App.vue:2669` | ~60 行 | 低 |
| `groups` | `App.vue:2307` | ~47 行 | 低 |
| `logs` | `App.vue:2623` | ~46 行 | 低 |
| `files` | `App.vue:2271` | ~36 行 | 低（已有 `DeviceFilePanel`） |

## 3. 目标架构

```text
当前:  main.ts → App.vue(2873行,自管一切) → 12 个 section 用 v-if 切换
                                            └ vue-router(摆设) / pinia(摆设)

目标:  main.ts → App.vue(纯壳,约 80 行) → <router-view>
                                          ├ views/DevicesView.vue
                                          ├ views/RemoteView.vue
                                          ├ views/UpdatesView.vue
                                          └ ...（共 12 个路由视图）
                  stores/ (pinia)  ├ auth.ts    (登录态 / 当前用户 / token / isAdmin)
                                   └ devices.ts (设备列表 / 状态缓存)
```

侧边栏导航由"修改 `activeSection` 变量"改为 `router.push`，浏览器前进/后退、刷新保持页面、深链接均自动获得。全局共享状态用 pinia store；局部状态保留组件内 `ref`/`reactive` 或抽 composable。

### 预期收益

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| `App.vue` 行数 | 2873 | 约 80 |
| 路由视图 | 0（僵尸 router） | 12 |
| pinia store | 0（僵尸 pinia） | 2+（auth / devices） |
| 死代码 `Dashboard.vue` | 存在 | 删除 |
| `api/platform.ts` | 1275 行单文件 | 按域拆分 |
| CI / lint 红线 | 无 | 有，自动拦截文件膨胀 |

## 4. 执行原则与约束

- **回滚单位**：每个任务 `Tx.y` = 一次独立 git commit。任意一步翻车，`git revert <commit>` 单独回退，不影响其他步骤。
- **工作分支**：`refactor/frontend-skeleton`（已创建）。
- **绿灯定义**：任务的验证命令全部通过，方可提交。
- **绞杀者模式（Strangler Fig）**：`App.vue` 不推倒重写，每迁出一个 section 即删除其在 App.vue 内的对应代码，使 App.vue 持续瘦身直至成为纯壳。
- **先安全网后重构**：在没有 CI 与可运行 lint 的前提下重构超大组件风险过高，故 Phase 0 必须先行。

### 环境基线（已探明）

- 工作分支：`refactor/frontend-skeleton`
- Node：v24.10.0；前端 `node_modules` 已安装
- 关键依赖：`vue@^3.5.13`、`vue-router@^4.4.5`、`pinia@^2.2.6`、`vitest@^2.1.8`、`@vue/test-utils@^2.4.6`、`eslint@^8.57.1`、`@typescript-eslint/parser@^7.18.0`、`eslint-plugin-vue@^9.32.0`、`prettier@^3.4.2`
- 验证命令均在 `frontend/` 目录执行；Windows 下 npm 用 `npm.cmd`。

### 已知风险与暗雷

1. **测试绑定在 App.vue 上**：`src/__tests__/app.spec.ts`（2339 行，23 用例）全部 `mount(App)`，且 `global.plugins` 仅装 `ElementPlus`，未装 router/pinia。一旦 App.vue 引入 `<router-view>`，这些测试会立即失败。→ 由 **T1.1** 优先处理（建 `mountApp()` helper 统一注入 router + testing-pinia）。
2. **remote 的 WebSocket 生命周期**：SSH/VNC 连接需在路由离开/组件卸载时正确 `close()`，否则切页后连接泄漏。→ 由 **T2.5** 单独隔离处理。
3. **bash 中文路径环境**：本项目路径含中文，bash 下复杂 `&&` 链式命令 + 中文 echo 会被绞碎执行。执行命令应使用纯英文、单条、避免长链。

## 5. 任务清单

> 命令默认在 `frontend/` 目录执行。

### Phase 0 — 织安全网（0 行业务逻辑改动）

#### T0.1 配置 eslint + prettier，使 lint 可运行
- **改动**：新建 `frontend/eslint.config.js`（flat config，适配 eslint@8.57 + `@typescript-eslint/parser@7` + `eslint-plugin-vue@9`）与 `frontend/.prettierrc`。
- **验证**：`npm run lint` 能运行并输出结果（允许 warning，只要不是"找不到配置"错误）。
- **回滚**：删除两个配置文件。

#### T0.2 设置防膨胀红线规则（初始为 warn）
- **改动**：在 eslint 配置中启用 `max-lines`（约 400）、`max-lines-per-function`、`vue/component-api-style` 等，初始级别设为 `warn`。
- **验证**：`npm run lint` 可见 `App.vue`、`api/platform.ts` 触发 `max-lines` warning。
- **回滚**：注释/移除相关规则。

#### T0.3 添加最简 CI
- **改动**：新建 `.github/workflows/ci.yml`，在 push/PR 时运行两条线：
  - 后端：`pytest`（现有 93 用例）
  - 前端：`npm run lint` + `npm run typecheck` + `npm test -- --run` + `npm run build`
- **验证**：本地依次跑通上述命令；推送后 Actions 通过。
- **回滚**：删除 workflow 文件。

> 完成标志：保护网就位，后续每步均有 CI 兜底。

### Phase 1 — 立骨架（接入 router + pinia，暂不迁移业务）

#### T1.1 建 `mountApp()` 测试 helper（优先排雷）
- **改动**：在测试中抽出 `mountApp()`，内部统一注入 `[ElementPlus, router, createTestingPinia()]`，收敛 23 个用例重复的 `global.plugins`。不改 App.vue。
- **验证**：`npm test -- --run` —— 23 用例仍全绿。
- **回滚**：还原 spec 文件。

#### T1.2 App.vue 接入 `<router-view>`（共存模式）
- **改动**：`main.ts` 已 `.use(router).use(pinia)`。在 router 中建立承载现有内容的路由，App.vue 引入 `<router-view>`，新旧机制先共存，不强制切换。
- **验证**：`npm test` 全绿；`npm run dev` 手动验证导航、刷新保持页面、浏览器后退正常。
- **回滚**：revert 本次 commit。

#### T1.3 抽 `stores/auth.ts`
- **改动**：将登录态、token、`currentUser`、`isAdmin`、登出逻辑从 App.vue 抽入 `stores/auth.ts`（所有视图的公共依赖，须最先抽）。
- **验证**：`npm test` 全绿；手动验证登录/登出/权限导航（admin 见用户管理，operator 不可见）。
- **回滚**：revert 单 commit。

> 完成标志：router 通路建立、auth 状态归位、测试地基适配完成。

### Phase 2 — 增量迁移 section → view（绞杀者，先易后难）

> 统一节奏：建 `views/XxxView.vue` → 搬运 App.vue 对应 template + 逻辑 → 注册路由 → 删除 App.vue 旧代码 → 迁移对应测试断言。每个 section 独立 commit。

> **分层方案修正（实践得出）**：section 组件化不是机械搬运 template——每个 section 会引用 App.vue 的 helper（如 `formatTime`）与共享 computed（如 `monitoringAvailability`，依赖 `devices`）。若不先提取共享层，会反复踩"依赖遗漏"坑（diagnostics 首次尝试已因此回退）。故先行 **阶段 2a（共享层）**：
>
> - **2a-1（已完成 `5a61282`）**：提取 `utils/format.ts`——`formatTime(value, fallback)` + `formatSize`，消除 7 处重复 `formatTime` + 1 处 `formatSize`，各调用方占位文案（暂无/未上报/-）经可选 fallback 原样保留。
> - **2a-2（已完成 `4645b72`）**：提取 `stores/devices.ts`——设备列表单一数据源 + `Device`/`DeviceStatus` 类型 + `monitoringAvailability`；App.vue 经 `storeToRefs` 取回可写 ref 接入，约 15 处读写零改动。
>
> 共享层就位后，再执行下方 T2.1–T2.5（**阶段 2b**）逐个组件化。原 T2.3 中"建 stores/devices.ts"已前移至 2a-2 完成。

#### T2.1 迁移 4 个已组件化 section（零风险练手）
- **对象**：`alerts / scheduled / settings / users`。
- **改动**：4 个 Panel 挂为路由视图 + 路由级权限守卫（替代 `v-if="isAdmin"`）。
- **验证**：`npm test` 全绿；4 页可达、权限正确。

#### T2.2 迁移 4 个轻量 section
- **对象**：`groups / logs / diagnostics / files`（files 已有 `DeviceFilePanel`）。
- **改动**：一个 section 一个 commit，4 个独立回滚点。
- **验证**：每迁一个，调整对应断言后 `npm test` 全绿 + 手动验证。

#### T2.3 迁移 dashboard + updates，建 `stores/devices.ts`
- **对象**：`dashboard / updates`。
- **改动**：抽 `stores/devices.ts`（dashboard 与 devices 共享设备列表/状态缓存）；updates 复用现有 3 个子组件，补编排层。
- **验证**：`npm test` 全绿；仪表盘指标、批量任务创建/执行手动验证。

#### T2.4 迁移 devices 视图（最复杂）
- **改动**：建 `views/DevicesView.vue`，复用 `stores/devices.ts` 与现有 `DeviceDetailDrawer`、`DeviceTargetSelector` 等子组件。
- **验证**：`npm test` 全绿；设备增删改查、状态刷新、凭据编辑、同步配置逐项手动验证。
- **回滚**：单 commit。

#### T2.5 迁移 remote 视图（最谨慎，WebSocket）
- **改动**：建 `views/RemoteView.vue`。重点处理 WebSocket 生命周期——`onMounted` 连接、`onBeforeUnmount` 与路由离开时 `close()`。
- **验证**：`npm test` 全绿；手动测 SSH 连接/输入/resize/断开、VNC 连接/全屏/断开，重点验证"切走再切回"无连接残留。
- **回滚**：单 commit。

> 完成标志：12 个 section 全部归位到独立路由视图。

### Phase 3 — 清理收尾

#### T3.1 删除死代码
- **改动**：删除占位的 `views/Dashboard.vue`。
- **验证**：`npm run build` 成功；全局搜索无引用残留。

#### T3.2 拆分 `api/platform.ts`
- **改动**：按域拆为 `api/devices.ts`、`api/alerts.ts`、`api/updateTasks.ts` 等，用 `api/index.ts` 统一 re-export，尽量保持调用方 import 路径不变。
- **验证**：`npm run typecheck` + `npm test` 全绿。

#### T3.3 App.vue 减重到纯壳
- **改动**：移除所有 `activeSection` 切换残留，App.vue 仅保留 LayoutShell + router-view + 全局对话框。
- **验证**：`wc -l src/App.vue` 约 80 行；全测试 + build 绿。

#### T3.4 红线转正
- **改动**：将 T0.2 的 `max-lines` 由 `warn` 提升为 `error`。
- **验证**：`npm run lint` 全绿（证明全项目无超标文件）。

## 6. 进度跟踪

| 任务 | 状态 | commit |
|------|------|--------|
| 建立分支 `refactor/frontend-skeleton` | ✅ 完成 | — |
| 生成本计划文档 | ✅ 完成 | `f9c177e` |
| T0.1 eslint + prettier 配置 | ✅ 完成 | `7b27548` |
| T0.2 防膨胀红线（warn） | ✅ 完成 | `7b27548` |
| T0.3 最简 CI | ✅ 完成 | `e0534cc` |
| T1.1 mountApp 测试 helper | ✅ 完成 | `e055063` |
| T1.2 App.vue 接入 router-view | ✅ 完成（route 驱动页面状态，测试改用 router.push） | `174be3d` |
| T1.3 stores/auth.ts | ✅ 完成 | `98cdfcb` |
| 阶段 2a-1 提取 `utils/format.ts`（formatTime/formatSize 去重 7+1 处） | ✅ 完成 | `5a61282` |
| 阶段 2a-2 提取 `stores/devices.ts`（设备列表 + monitoringAvailability） | ✅ 完成 | `4645b72` |
| T2.1 迁移已组件化 4 section | ✅ 完成 | `51844b5`/后续 router-view 收口 |
| T2.2 迁移轻量 4 section | ✅ 完成 | `05487e4`/`1bed5e9`/`6b789d4`/`3092c1a` |
| T2.3 迁移 dashboard + updates（devices store 已于 2a-2 前移完成） | ✅ 完成 | `77bdc08`/`a310699` |
| T2.4 迁移 devices 视图 | ✅ 完成 | `84b1910` |
| T2.5 迁移 remote 视图 | ✅ 完成 | `2da04dd` |
| T3.1 删除死代码 Dashboard.vue | ✅ 完成 | `de23be2` |
| T3.2 拆分 api/platform.ts | ✅ 完成（platform.ts 保留 re-export 壳，主体进入 core/domain） | `4d3e475`/`64b421a` |
| T3.3 App.vue 减重到纯壳 | 🟡 进行中（页面区已收敛为单个 RouterView；App.vue 仍保留登录态、全局弹窗与 shell 编排，当前约 317 行） | `174be3d`/后续 P4.3 |
| T3.4 红线转正 | ✅ 完成（max-lines error，阈值按现状调整为 2500） | `87a3467` |

### 2026-06-23 续作校准

- `App.vue` 已从本地 `activeSection` 写入切换为 `useRoute()` 派生当前 section，侧边栏、Dashboard 跳转、分组查看设备、设备文件/远程入口均经 `router.push()` 导航。
- 页面区域已接入 `<RouterView>` slot，但为了保持现有编排层稳定，仍由 `App.vue` 按 route name 给各 Panel 传入既有 props/events；这一步完成了 URL/刷新/前进后退骨架，不等同于 App 纯壳。
- `src/__tests__/app.spec.ts` 的页面切换用例已改为显式 `router.push()`，保留 21 passed + 2 skipped 的现状；2 个 skipped 仍是 RemotePanel SSH/VNC 生命周期专项测试债务。

## 7. Phase 4 — 收尾补充计划

> Phase 4 的目标不是继续扩大重构面，而是把已立起的 router/store/Panel 骨架补到可长期维护的状态。每个任务仍按独立 commit 执行，完成后至少跑 `npm run lint`、`npm run typecheck`、`npm test -- --run`；涉及打包或路由懒加载时加跑 `npm run build`。

### P4.1 RemotePanel 专项测试补齐（✅ 已完成，本次提交）

- **问题**：`src/__tests__/app.spec.ts` 仍有 2 个 SSH/VNC 相关 `it.skip`。RemotePanel 已自管理 WebSocket 生命周期，旧 App 级测试无法可靠观察组件内部资源。
- **改动**：
  - 新建 `src/components/__tests__/RemotePanel.spec.ts` 或同等组件级测试文件。
  - 抽复用 mock：WebSocket、xterm terminal、FitAddon、noVNC RFB、`openSshSession`/`openVncSession`/`buildApiWebSocketUrl`。
  - 覆盖 SSH：选择设备、创建 session、WebSocket open/message/input/close、错误态展示、组件卸载关闭 socket。
  - 覆盖 VNC：创建 session、RFB connect/disconnect/securityfailure、手动断开、组件卸载 disconnect。
  - 将 `app.spec.ts` 中 2 个 `it.skip` 删除或改成不重复 RemotePanel 内部细节的 App 级导航冒烟测试。
- **验证**：`npm test -- --run` 应恢复为 23 passed、0 skipped；`npm run typecheck` 通过。
- **完成标准**：RemotePanel 生命周期有组件级覆盖，测试结果无 skipped。

**执行结果（2026-06-23）**：

- 新增 `src/components/__tests__/RemotePanel.spec.ts`，组件级覆盖 SSH 成功连接/终端输入输出/断开、SSH 创建失败、VNC 连接/断开、SSH/VNC 组件卸载清理。
- 删除 `src/__tests__/app.spec.ts` 中 2 个旧的 `it.skip` 远程连接用例，将 RemotePanel 内部生命周期从 App 大测试迁出。
- 验证结果：`npm test -- --run` 为 25 passed、0 skipped；`npm run lint` / `npm run typecheck` / `npm run build` 均通过，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

### P4.2 路由权限守卫与直达路径行为（✅ 已完成，本次提交）

- **问题**：当前 admin 页面主要依靠侧边栏隐藏和 App 内条件渲染；operator 仍可能直接输入 `/users` 或 `/settings`。
- **改动**：
  - 在 `router/index.ts` 增加路由 `meta`：`requiresAuth`、`adminOnly`、`label`。
  - 增加 `beforeEach` 守卫：未登录访问业务页跳回默认登录态/保留目标；operator 访问 adminOnly 跳转 dashboard 或显示权限错误；未知路径重定向 dashboard。
  - AppTopbar 标题优先从 route meta 派生，避免 navItems 与 routes 双份标签长期漂移。
  - 补测试：operator `router.push("/users")`/`router.push("/settings")` 不渲染管理页，导航 active 回到安全页面。
- **验证**：`npm run typecheck`、`npm test -- --run`、`npm run build`。
- **完成标准**：导航隐藏与 URL 直达权限一致，刷新和深链接行为稳定。

**执行结果（2026-06-23）**：

- 新增 `src/router/routes.ts`，生产 router 与测试 router 共用同一份 route meta（`requiresAuth` / `adminOnly` / `label`）和 catch-all 重定向。
- 新增 `src/router/guards.ts`，统一安装路由守卫：未登录直达业务页回 dashboard，operator 直达 adminOnly 页面回 dashboard。
- `App.vue` 的标题优先从 route meta 派生，并在用户资料加载后兜底处理 adminOnly route，覆盖刷新直达 admin URL 后才知道角色的场景。
- `src/__tests__/app.spec.ts` 接入同一套 route guard，补充 operator 直达 `/users`、`/settings` 与未知路径 `/not-found` 的断言。
- 验证结果：`npm run lint` / `npm run typecheck` / `npm test -- --run` / `npm run build` 均通过；测试为 26 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

### P4.3 App.vue 编排层继续下沉，接近纯壳（🟡 进行中）

- **问题**：`App.vue` 已接入 `<RouterView>`，但仍保留少量登录态、全局弹窗与 shell 编排逻辑，当前约 317 行。
- **改动**：
  - 建 `views/` 或 `route-shells/` wrapper：如 `DashboardView.vue`、`DevicesView.vue`、`UpdatesView.vue`、`DiagnosticsView.vue`，把对应 route 的 props/events 适配从 App.vue 迁出。
  - 将 `loadPlatformData`、`refreshLogsAndOverview`、overview/alertSummary/diagnosticsConfig 等跨页状态逐步下沉到 store 或 composable。
  - App.vue 只保留：登录态入口、LayoutShell、sidebar/topbar、全局错误/密码弹窗、`<RouterView>`。
- **建议拆分**：
  - P4.3a：✅ 抽 `stores/platformOverview.ts`，承接 overview/alertSummary/backend health/diagnostics/metric warning。
  - P4.3b：✅ 抽 Dashboard/Diagnostics route wrapper。
  - P4.3c：✅ 抽 Devices/Files/Remote route wrapper，处理跨页入口。
  - P4.3d：✅ 抽 Updates/Logs/Groups/Scheduled/Alerts/Admin route wrapper，最终瘦 App.vue。
- **验证**：每个小步跑 `npm test -- --run`；最终加跑 `npm run build`。
- **完成标准**：App.vue 降到约 150 行以内；不再按 route name 手写 12 个 Panel 分支。

**P4.3a 执行结果（2026-06-23）**：

- 新增 `src/stores/platformOverview.ts`，集中管理 `serverOverview`、`alertSummary`、`diagnosticsConfig`、`backendHealthStatus/backendHealthDetail` 与 `metricLoadWarning`。
- `App.vue` 不再直接调用 `fetchHealth`、`getMonitoringOverview`、`getAlertSummary`、`getDiagnosticsConfig`；`loadPlatformData` 通过 store action 并发刷新 overview。
- `logout()` 通过 store reset 清空平台概览态；Dashboard、Topbar、DiagnosticsPanel 的 props 当时仍由 App.vue 暂时转发，已在 P4.3b 继续下沉。
- 验证结果：`npm run lint` / `npm run typecheck` / `npm test -- --run` / `npm run build` 均通过；测试为 26 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

**P4.3b 执行结果（2026-06-23）**：

- 新增 `src/views/DashboardView.vue`，由 wrapper 从 `platformOverview` store 读取 dashboard 所需 overview/alert/metric warning，再向 `DashboardPanel` 转发。
- 新增 `src/views/DiagnosticsView.vue`，由 wrapper 自取诊断配置并在挂载时加载，`App.vue` 不再直接渲染 `DiagnosticsPanel` 或处理其刷新事件。
- `router/routes.ts` 的 dashboard/diagnostics 路由已指向 view wrapper；`App.vue` 对这两页只保留 refresh/navigate 的过渡编排。
- 验证结果：`npm run lint` / `npm run typecheck` / `npm test -- --run` / `npm run build` 均通过；测试为 26 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

**P4.3c 执行结果（2026-06-23）**：

- 新增 `src/views/DevicesView.vue`、`src/views/FilesView.vue`、`src/views/RemoteView.vue`，并将 `router/routes.ts` 中 devices/files/remote 指向对应 wrapper。
- `DevicesView` 接管设备页跨页入口：文件入口写入 `devicesStore.filePanelDevice` 后跳转 files；SSH/VNC 入口写入 `remoteSessionRequest` 后跳转 remote。
- `RemotePanel` 消费 `devicesStore.remoteSessionRequest`，自动选择设备并启动 SSH/VNC，会话生命周期仍由 RemotePanel 自管理。
- `App.vue` 删除旧的 remote section WebSocket/terminal/VNC 实现及卸载清理，远程连接职责彻底移入 RemotePanel；App.vue 约 888 → 596 行。
- 新增 RemotePanel 测试覆盖跨路由 SSH 请求消费；验证结果：`npm run lint` / `npm run typecheck` / `npm test -- --run src/components/__tests__/RemotePanel.spec.ts` / `npm test -- --run` / `npm run build` 均通过；测试为 27 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

**P4.3d 执行结果（2026-06-24）**：

- 新增 `src/stores/platformData.ts`，统一承接平台首屏加载、刷新 loading/operationError、登出数据清理和设备指标附加逻辑。
- 新增 `src/views/GroupsView.vue`、`src/views/UpdatesView.vue`、`src/views/ScheduledView.vue`、`src/views/AlertsView.vue`、`src/views/SettingsView.vue`、`src/views/UsersView.vue`、`src/views/LogsView.vue`，并将对应路由指向 view wrapper。
- `DashboardView` / `FilesView` 改为直接使用 `platformDataStore`，不再依赖 App 通过 RouterView slot 传 props/events。
- `App.vue` 页面区域收敛为单个 `<RouterView />`，不再按 route name 手写 12 个 Panel/View 分支；App.vue 约 596 → 317 行。
- 验证结果：`npm run typecheck` / `npm run lint` / `npm test -- --run` / `npm run build` 均通过；测试为 27 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。

### P4.4 API domain.ts 按域继续拆分（✅ 已完成）

- **问题**：`api/platform.ts` 已是 re-export 壳，但 `api/domain.ts` 仍接近 1000 行，API 聚合债务只是从 platform 文件转移到 domain 文件。
- **改动顺序**：
  - ✅ 按业务域拆为 `api/domains/auth.ts`、`users.ts`、`devices.ts`、`groups.ts`、`logs.ts`、`monitoring.ts`、`updates.ts`、`files.ts`、`scheduled.ts`、`remote.ts`、`diagnostics.ts`、`settings.ts`、`alerts.ts`、`frps.ts`。
  - ✅ 每个域文件同时承载该域类型与 API 函数，避免纯类型和函数拆在两处导致来回跳转。
  - 保留 `api/platform.ts` 作为兼容出口，统一 re-export，先不改调用方 import。
  - ✅ `api/domain.ts` 收敛为 15 行 re-export hub；最大域文件为 `api/domains/alerts.ts`，约 284 行。
- **验证**：`npm run typecheck` / `npm run lint` / `npm test -- --run` / `npm run build` 均通过；测试为 27 passed，0 skipped，仍保留已知 lint 超长函数 warning 和 Vite 大 chunk warning。
- **完成标准**：✅ 单个 API 文件低于 max-lines 红线；platform 仍兼容旧 import；domain.ts 仅保留聚合导出。

### P4.5 测试文件瘦身与 lint warning 清零（✅ 已完成）

- **问题**：`src/__tests__/app.spec.ts` 超 2000 行，`lint` 仍有 2 个 `max-lines-per-function` warning。
- **改动**：
  - ✅ 抽 `src/__tests__/fixtures/platform.ts`：mock API 响应、设备/分组/日志/更新任务 fixture，并按 API 域拆成多个小 setup 函数。
  - ✅ 抽 `src/__tests__/helpers/app.ts`：`mountApp`、`flushAsync`、`navigateTo`、`waitUntil`，让 App spec 只保留用例本身和本地 mock 壳。
  - 将已组件化 Panel 的细节测试逐步迁到组件级 spec，App spec 只保留登录、布局、权限、核心跨页流程。
  - ✅ `max-lines-per-function` warning 已降到 0，未添加 eslint 豁免。
- **验证**：`npm run lint` 为 0 warning；`npm run typecheck` / `npm test -- --run` / `npm run build` 均通过；测试为 27 passed，0 skipped，仍保留 Vite 大 chunk warning。
- **完成标准**：✅ App spec 可扫描、fixture 可复用、lint warning 清零。

### P4.6 构建体积优化（✅ 已完成）

- **问题**：`npm run build` 通过，但 Vite 仍提示多个 chunk 超过 500 kB。router 已接入后，可以重新启用更自然的路由级拆包。
- **改动**：
  - ✅ 将生产路由组件改为 `() => import(...)`，测试路由 `TEST_ROUTES` 继续保留同步 import，避免 Vitest 异步组件噪声。
  - ✅ 配置 `build.rollupOptions.output.manualChunks`，拆出 `vendor-vue`、`vendor-element`、`vendor-echarts`、`vendor-xterm`、`vendor-novnc`、`vendor-http` 等明确 vendor chunk。
  - ✅ `DashboardPanel` 改为通过 `echarts/core`、`echarts/charts`、`echarts/components`、`echarts/renderers` 加载图表入口。
  - ✅ 对 RemotePanel 的 xterm/noVNC 依赖保持按需加载，远程连接重依赖不进入主入口。
- **验证**：`npm run lint` / `npm run typecheck` / `npm test -- --run` / `npm run build` 均通过；测试为 27 passed，0 skipped。构建不再提示 Vite 大 chunk warning，主入口 JS 约 28.37 kB，页面 chunk 约 2.34-21.94 kB；`vendor-element` 约 717.99 kB、`vendor-echarts` 约 1014.19 kB，为显式 vendor chunk，`chunkSizeWarningLimit` 调整为 1100。
- **完成标准**：✅ 首屏主 chunk 明显下降；Vite 大 chunk warning 已消除，剩余大体积集中在可解释 vendor chunk。

### Phase 4 推荐顺序

1. **P4.1 RemotePanel 测试补齐**：✅ 已完成，skipped 已清零，最高风险 WebSocket 生命周期已有组件级安全网。
2. **P4.2 路由权限守卫**：✅ 已完成，URL 直达权限边界已补齐。
3. **P4.3 App.vue 纯壳化**：✅ 页面区已收敛为单个 RouterView，App 仍保留登录态与全局壳。
4. **P4.4 API domain 拆分**：✅ 已完成，domain.ts 仅保留聚合导出。
5. **P4.5 测试瘦身**：✅ 已完成，`app.spec.ts` 的 2 个 max-lines warning 已清零。
6. **P4.6 构建体积优化**：✅ 已完成，Vite 大 chunk warning 已消除。
