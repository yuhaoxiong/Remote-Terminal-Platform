# 前端重构工作汇总（2026-06-11）

> 本文档记录本次 session 的讨论结论、已完成的修改、遇到的环境问题及长期解决方案，方便后续继续。

## 一、背景与目标

对「远程终端平台」项目做了一次审查，并讨论后续开发方向，最终决定**重构前端**（拆分 App.vue 上帝组件），并在重构前先补齐工程基建。

## 二、项目审查结论（简要）

| 维度 | 结论 |
|------|------|
| 后端 | 质量优秀。分层清晰（router/service/model），最大文件约 515 行，93 个测试，Alembic 迁移、枚举校验、凭据加密齐全 |
| 前端 | 架构债务严重 |

前端核心问题：

- **`App.vue` 2873 行上帝组件**：12 个功能区（dashboard/devices/remote/updates…）用 `activeSection` 变量 + `v-if` 手动切换
- **僵尸依赖**：`vue-router`、`pinia` 已装却几乎未用（无 `router-view`/`defineStore`）
- **死代码**：`views/Dashboard.vue` 是硬编码全 0、从未渲染的占位组件
- **巨型文件**：`api/platform.ts` 1275 行
- **工程基建缺失**：无 CI、无可用的 lint 配置

**根因判断**：不是能力问题，而是前端从第一天起缺少「页面骨架（router）+ 状态骨架（store）」的约束，导致新功能只能堆进 App.vue。

## 三、确定的重构方案（绞杀者模式 + 分层）

- **Phase 0｜织安全网**：lint + CI + 防膨胀红线（先做，保护后续）
- **Phase 1｜立骨架**：测试 helper → auth store → （router 最后接）
- **Phase 2｜组件化**：把 8 个内联 section 逐个抽成独立组件。**经实践修正为分层方案**：先提取共享层（utils + store），再逐个组件化
- **Phase 3｜清理**：把 `v-if` 切换换成 router-view + 路由、删死代码、拆分 `api/platform.ts`、红线由 warn 转 error

详细计划见 `docs/frontend-refactor-plan.md`（注：该文件为初版，Phase 2 顺序待按下方"分层方案"更新）。

## 四、已完成的修改

工作分支：**`refactor/frontend-skeleton`**（未动 main）。本次新增 5 个提交：

| Commit | 内容 | 阶段 |
|--------|------|------|
| `f9c177e` | 新增重构计划文档 `docs/frontend-refactor-plan.md` | 规划 |
| `7b27548` | 配置 eslint + prettier，加 `max-lines` 防膨胀红线（warn 级，精准命中 6 个大文件） | Phase 0 |
| `e0534cc` | 新增 CI workflow `.github/workflows/ci.yml`（后端 pytest + 前端 lint/typecheck/test/build） | Phase 0 |
| `e055063` | 抽取 `mountApp()` 测试 helper，收敛 23 处重复 mount（净减 152 行） | Phase 1 |
| `98cdfcb` | 抽取 auth 状态到 pinia store（`src/stores/auth.ts`），pinia 从僵尸依赖变为真正的共享状态 store | Phase 1 |

新增/修改的关键文件：

- `frontend/.eslintrc.cjs`、`.prettierrc`、`.eslintignore`
- `frontend/package.json`（加 lint/format 脚本 + eslint 相关 devDependencies）
- `frontend/.github/workflows/ci.yml`（位于仓库根 `.github/`）
- `frontend/src/stores/auth.ts`（新）
- `frontend/src/App.vue`（接入 auth store）
- `frontend/src/__tests__/app.spec.ts`（mountApp helper + pinia）

**当前状态**：工作区干净，三项验证全绿（`lint` 0 error / `typecheck` / `test` 23 passed）。

## 五、环境问题与长期解决（重要）

### 问题

本机是 **Windows + WSL2** 混合环境。Claude Code 的**文件工具运行在 Windows 侧**（操作 `C:\` 路径），但 **Bash 工具默认连到了 WSL2**（看 `/c/` 或 `/mnt/c/`）。两套文件系统视图不一致，导致文件读写、npm 依赖安装、git 状态全部错乱（表现为"文件写了读不到""依赖装不全""删了还在"等）。

### 临时解决

手动把终端切换到 **Git Bash**（`uname` 显示 `MINGW64`），问题立即消失。

### 长期解决（已配置）

在 `~/.claude/settings.json` 的 `env` 中追加：

```json
"CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"
```

效果：以后每次启动 Claude Code，Bash 工具固定使用 Git Bash（Windows 侧），与文件工具同处 `C:\` 文件系统，不再复发。

**验证方法**：重启 Claude Code 会话后执行 `uname -a`，显示 `MINGW64...Msys` 即成功；若仍是 `microsoft-standard-WSL2`，需检查启动方式（是否在 WSL 内启动 claude）。

### 可靠工作模式（环境受限时的经验）

- 文件读写优先用文件工具（`C:\` 路径）；命令用相对路径（cwd 在项目内）或 `git -C` 指定路径
- **大文件（如 2873 行的 App.vue）文件工具的局部 Edit 可能静默失败**，应改用 node 脚本读取-替换-写回，并用 `grep`/`git` 交叉验证落盘
- 项目路径含中文（`远程终端平台`）会加剧 bash 编码问题，长期可考虑迁移到纯英文路径（如 `C:\work\edge-platform`）

## 六、后续待办（Phase 2 分层方案）

下次继续时按以下顺序推进：

```
阶段 2a（预备·先做）：提取共享层
  - src/utils/format.ts    ← formatTime 等通用 helper（全项目 5 处共用）
  - stores/devices.ts      ← devices 列表 + monitoringAvailability 等共享 computed（6 处用）
阶段 2b：基于共享层，逐个组件化 8 个 section（先易后难）
  顺序建议：diagnostics / logs / groups / files → dashboard / updates → devices → remote
阶段 3：把 activeSection 的 v-if 切换换成 router-view + 路由；删 Dashboard.vue 死代码；拆分 api/platform.ts；max-lines 由 warn 提为 error
```

> 经验教训：section 组件化不是"机械搬运 template"。每个 section 的 template 会引用 App.vue 的 helper（如 `formatTime`）和共享 computed（如 `monitoringAvailability`，依赖 `devices`）。**必须先提取共享层，否则会反复踩"依赖遗漏"的坑**（diagnostics 的首次尝试已因此回退）。

待办：更新 `docs/frontend-refactor-plan.md`，勾选已完成项并把 Phase 2 改为上述分层顺序。

## 七、常用验证命令（Git Bash，frontend 目录）

```bash
npm run lint        # eslint，0 error 即通过（warn 为防膨胀红线提示）
npm run typecheck   # vue-tsc --noEmit
npm test            # vitest run，应 23 passed
npm run build       # 构建
git log --oneline -6
```

## 八、本次续作（2026-06-11 第二段：Phase 2a 共享层）

承接上文「六、后续待办」，本段完成 **Phase 2a（提取共享层）**，在 `refactor/frontend-skeleton` 分支新增 2 个提交：

| Commit | 内容 | 阶段 |
|--------|------|------|
| `5a61282` | 提取 `src/utils/format.ts`：`formatTime(value, fallback)` + `formatSize`。消除 **7 处重复 formatTime + 1 处 formatSize**；App.vue 直接用（默认空串占位），6 个组件用薄包装保留各自占位（暂无/未上报/-），行为零变更 | 2a-1 |
| `4645b72` | 提取 `src/stores/devices.ts`：设备列表单一数据源 + `Device`/`DeviceStatus` 类型 + `monitoringAvailability` 监控覆盖率。App.vue 经 `storeToRefs` 取回**可写 ref**，约 15 处 `devices.value` 读写零改动；删除 App.vue 内的本地 devices ref、Device/DeviceStatus 类型、monitoringAvailability computed | 2a-2 |

**关键经验（避坑）**：

- `formatTime` 的 7 处拷贝**看似相同、实则空值占位文案各异**（`""`/`暂无`/`未上报`/`-`）。统一为 `formatTime(value, fallback = "")`，用可选参数保留各处显示——重构的铁律是行为零变更，不能为了"统一"改掉界面文案。
- devices store 用 `storeToRefs` 取回的 **state 是可写 ref**（getter 才是只读）。正因如此，App.vue 那 15 处 `devices.value = … / .push() / [i] = …` 全部无需改动——这是本次能低风险落地的关键。把 `Device`/`DeviceStatus` 类型一并迁入 store 并以 `type` 导入回 App.vue，模板里的 `as DeviceStatus` 也照常工作。

**当前状态**：工作区干净，三项验证全绿（`lint` 0 error / `typecheck` / `test` 23 passed）。App.vue 经两段瘦身，lint 计数 2707 → 2673 行。

**下一步（Phase 2b）**：基于已就位的共享层，逐个组件化 8 个内联 section（先易后难：diagnostics / logs / groups / files → dashboard / updates → devices → remote），每个 section 独立 commit。`T1.2`（App.vue 接入 `router-view`）按计划推迟至组件化收尾再做。计划文档 `docs/frontend-refactor-plan.md` 的进度表与 Phase 2 分层说明已同步更新。

## 九、本次续作（2026-06-12 第三段：section 组件化 + store 骨架扩展）

承接 Phase 2b，本段新增 6 个提交（均三项全绿 + 已推送 origin）。**首次推送已建立上游跟踪** `origin/refactor/frontend-skeleton`。

| Commit | 内容 |
|--------|------|
| `05487e4` | **DiagnosticsPanel**（section ①）。表现型组件:接收 `config`/`loading` props、emit `refresh`;内部自取 devices store 的 monitoringAvailability + utils 的 formatTime。App.vue 保留 `diagnosticsConfig` 状态(顶栏 schedulerRunning 依赖它) |
| `20eb46a` | **groups store**(`stores/groups.ts`):groups 列表 + Group 类型 |
| `4880ae1` | **logs store**(`stores/logs.ts`):auditLogs/auditLogsTotal + AuditLog 类型 + `mapLog`/`prependLocalLog`(全局 ~25 处调用)。state 用 storeToRefs、方法直接解构 → 调用点零改动 |
| `7de0a40` | 设备视图状态入 devices store:deviceSearch/selectedGroupId/3 个筛选 + `visibleDevices` computed |
| `1bed5e9` | **FilesPanel**(section ②):设备选择表 + DeviceFilePanel;读 store(visibleDevices/deviceSearch/filePanelDevice/openFilePanel)、emit `refresh`。filePanelDevice/openFilePanel 入 devices store |
| `163b424` | `mapGroup`(纯函数) + `recalculateGroupCounts`(action) 下沉到 groups store,显式传 device 列表参数 |

**当前状态**：App.vue **2876 → 2538 行**；store 骨架 = `auth / devices(+视图态+filePanel) / groups(+mapGroup/recalc) / logs`;已抽 2 个 section(diagnostics、files);工作区干净,三项全绿。

### 关键发现:剩余 section 的耦合分层

- **可干净抽取(只读/选择型耦合)**:diagnostics ✅、files ✅。
- **硬骨头(CRUD + 编排耦合)**:groups / devices / updates。其动作处理函数交织 App.vue 编排层。
- **编排层 `loadPlatformData` 深度 DOM 耦合**:调用 `renderDashboardCharts`(ECharts + App.vue 图表 DOM ref) + 协调 7 个 API + 4 个 store。**整体搬迁风险过高**,故留在 App.vue。
- **既定模式**:section 自包含完成本域 API + store 改写,通过 **`@changed`/`@refresh` 事件**触发 App.vue 持有的编排(refreshLogsAndOverview)——与 DiagnosticsPanel 的 `@refresh` 一致。`vue/no-mutating-props` 禁止把 reactive 表单当 prop 做 v-model,故表单状态必须组件本地化或用 store ref。

### 下一步:GroupsPanel 配方(已完成全部前置,可直接执行)

前置已就位:groups store(groups + mapGroup + recalculateGroupCounts)、logs store(prependLocalLog)、devices store(devices + selectedGroupId)。

1. 新建 `components/GroupsPanel.vue`:
   - **本地** state:groupForm(reactive)、groupFormOpen、groupEditId、groupFormTitle(computed)、openGroupCreate、openGroupEdit。
   - 读 store:`useGroupsStore`(groups)、`useDevicesStore`(devices, selectedGroupId)、`useLogsStore`(prependLocalLog)、`mapGroup`(从 groups store 导入)。
   - `saveGroup`:校验(prependLocalLog) → createGroup/updateGroup API → groups.value push/update(mapGroup(created, devices)) → 改名时同步 devices.value → `recalculateGroupCounts(devices)` → `emit('changed')` → 关表单;catch:prependLocalLog。
   - `removeGroup`:ElMessageBox 确认 → deleteGroup API → groups.value 过滤 → 重置 selectedGroupId → devices.value 解绑 → `emit('changed')`;catch:prependLocalLog。
   - props:无(或 canManage);emits:`changed`。
2. App.vue:
   - `<GroupsPanel v-if="activeSection === 'groups'" @changed="refreshLogsAndOverview" />`(注意:saveGroup/removeGroup 原本调 refreshLogsAndOverview,改为 @changed 触发)。
   - 删除 groups 段模板(约 `2200-2260`)+ groupForm/groupFormOpen/groupEditId/groupFormTitle/openGroupCreate/openGroupEdit/saveGroup/removeGroup;保留 `selectGroup`(设备区用)。
   - 移除随之不再用的导入(GroupCreateRequest/GroupUpdateRequest/createGroup/updateGroup/deleteGroup —— 视 GroupsPanel 接管后 App.vue 是否还用)。
   - 注意 `selectedGroupId` 已在 devices store,GroupsPanel 可直接重置。

### 剩余路线

- section:GroupsPanel → UpdatesPanel(类似 CRUD)→ DevicesPanel(最大,设备 CRUD/状态刷新/凭据)→ RemoteView(SSH/VNC WebSocket 生命周期,最谨慎)→ dashboard(图表)→ logs(需 filters/pagination 处理)。
- 各 CRUD section 同 GroupsPanel 套路:本地表单 + 读 store + `@changed` 事件。mapDevice/mapUpdateTask 可按需下沉到对应 store(同 mapGroup)。
- Phase 3:activeSection 的 v-if → router-view;删 `views/Dashboard.vue` 死代码;拆分 `api/platform.ts`(1092 行);max-lines 由 warn 提为 error。

## 十、续作（2026-06-12 第四段：GroupsPanel + 编排层收拢）

新增 2 提交(全绿+已推送):

| Commit | 内容 |
|--------|------|
| `163b424` | `mapGroup`(纯函数) + `recalculateGroupCounts`(action) 下沉 groups store,显式传 device 列表 |
| `6b789d4` | **GroupsPanel**(section ③):自包含 group CRUD,本地表单 + 读 groups/devices/logs store,emit `changed`(→App.refreshLogsAndOverview)/`view-devices`(→App.selectGroup) |

**编排层结论**:`loadPlatformData`/`refreshLogsAndOverview` 因深度 DOM 耦合(renderDashboardCharts)**留 App.vue**,由 section 用 `@changed` 事件触发;纯 helper(mapGroup/recalculateGroupCounts)下沉 store。

**已验证的 CRUD section 抽取配方(GroupsPanel 已证明,可复用)**:
1. 共享列表先入 store(如 groups/logs/devices 已做);纯 map/计算 helper 下沉对应 store(显式传依赖)。
2. Panel 自包含:本地表单 state(避开 `vue/no-mutating-props`)+ 读 store(storeToRefs)+ 调 API/store 改写 + logsStore.prependLocalLog。
3. 跨切面副作用用 emit:`@changed`(App 触发 refreshLogsAndOverview)、导航类 `@view-devices`(App 持有 activeSection)。
4. 删 App.vue 内的模板/表单/handler + 随之不用的导入(用 grep 确认仅该处使用)。
5. 大块模板用 node 脚本 + `__XXX_TEMPLATE__` 占位注入(规避反引号/CRLF/转义)。

**当前状态**:App.vue **2876 → 2402 行**;store = auth/devices/groups/logs;已抽 section = diagnostics ① / files ② / groups ③;三项全绿。

### 下一个:UpdatesPanel(已分析,配方就绪)

- 先建 **updates store**:`updateTasks` + `pendingTaskCount`(派生) + 类型 `UpdateStatus`/`UpdateTask` + helper `updateStatusText`/`normalizeUpdateStatus`/`statusTextForTask`/`mapUpdateTask`(均 updates 专属,App.vue 当前 94/97/291/472/588/615 行)。注意 `updateTasks` 被仪表盘 overview + pendingTaskCount 共享 + WebSocket 快照(App.vue ~1348)推送——入 store 后 App.vue 经 storeToRefs 写、仪表盘读。
- 再抽 **UpdatesPanel**:updates 段(App.vue `activeSection === 'updates'` ~2225,~116 行)+ 复杂表单(updateForm)+ 目标预览 + 3 子组件(UpdateTaskResultTable/UpdateTaskTemplatePanel/DeviceTargetSelector)。emit `changed`。
- 之后:DevicesPanel(最大)→ RemoteView(WebSocket 最谨慎)→ dashboard(图表)→ logs(filters/pagination)→ Phase 3。

## 十一、本次总览（2026-06-12 完整 session）

**提交数**：13 个（12 重构 + 1 CI 修复），全部已推送 origin，三项全绿。

| 维度 | 最终状态 |
|------|----------|
| **App.vue** | **2876 → 2277 行（−599 行，−21%）** |
| **Store 骨架（5 个）** | `auth / devices / groups / logs / updates` + `utils/format` |
| **已抽 section（3 个）** | DiagnosticsPanel ① / FilesPanel ② / GroupsPanel ③ |
| **编排层** | 纯 helper(mapGroup/recalc)下沉 store；WS 进度连接入 updates store 持久化；loadPlatformData 留 App.vue 经 `@changed` 事件触发 |

### 提交清单

| Commit | 内容 | 类别 |
|--------|------|------|
| `5a61282` | 提取 `utils/format.ts`（formatTime + formatSize），7 处重复 formatTime 收拢 | Phase 2a 共享层 |
| `4645b72` | 提取 `stores/devices.ts`（devices + Device/DeviceStatus + monitoringAvailability） | Phase 2a 共享层 |
| `e2c0eb8` | 文档：同步 Phase 2a 进展到重构计划 | 文档 |
| `05487e4` | **DiagnosticsPanel**（section ①）：读 devices store + utils，emit `refresh` | Phase 2b 组件化 |
| `20eb46a` | 提取 `stores/groups.ts`（groups + Group 类型） | Phase 2b store 扩展 |
| `4880ae1` | 提取 `stores/logs.ts`（auditLogs/auditLogsTotal + AuditLog + mapLog/prependLocalLog） | Phase 2b store 扩展 |
| `7de0a40` | 设备视图状态入 devices store（deviceSearch/selectedGroupId/filters + visibleDevices） | Phase 2b store 扩展 |
| `1bed5e9` | **FilesPanel**（section ②）：读 devices store，filePanelDevice/openFilePanel 入 store | Phase 2b 组件化 |
| `163b424` | mapGroup + recalculateGroupCounts 下沉 groups store（显式传 device 列表） | Phase 2b 编排收拢 |
| `6b789d4` | **GroupsPanel**（section ③）：自包含 CRUD，本地表单 + 读 store + emit `changed`/`view-devices` | Phase 2b 组件化 |
| `3ced0a2` | 提取 `stores/updates.ts`（updateTasks/pendingTaskCount + 类型/helper） | Phase 2b store 扩展 |
| `d1f9ead` | 更新任务 WS 进度连接入 updates store（持久化以跨导航存活） | Phase 2b 编排收拢 |
| `a5c45da` | **修复 CI**：alembic/env.py 补齐 sqlite 父目录创建（CI 全新环境下 `unable to open database file`） | 修复 |

### 已验证的 CRUD section 抽取配方（GroupsPanel 实证）

1. **共享列表先入 store**（如 groups/logs/devices 已做）；纯 map/计算 helper 下沉对应 store（显式传依赖）。
2. **Panel 自包含**：本地表单 state（避开 `vue/no-mutating-props`）+ 读 store（storeToRefs）+ 调 API/store 改写 + logsStore.prependLocalLog。
3. **跨切面副作用用 emit**：`@changed`（App 触发 refreshLogsAndOverview）、导航类 `@view-devices`（App 持有 activeSection）。
4. **删 App.vue 内的**：模板 + 表单 + handler + 随之不用的导入（用 grep 确认仅该处使用）。
5. **大块模板用 node 脚本**：`__XXX_TEMPLATE__` 占位注入（规避反引号/CRLF/转义）。

### 下一步（已分析，配方就绪）

1. **UpdatesPanel**（section ④，最大最精细）：
   - 前置已完成：updates store（含 WS 进度连接持久化）+ 所有类型/helper。
   - 8 个处理函数（创建/执行/取消/重试/导出 + 目标预览 + 模板套用 + 真实 SSH 确认）+ 3 个子组件 + 复杂表单。
   - 套路同 GroupsPanel：自包含 + 读 store + WS 调 store action + `@changed` 事件。
2. 之后：DevicesPanel（最大）→ RemoteView（WebSocket 最谨慎）→ dashboard（图表）→ logs（filters/pagination）→ Phase 3（router-view + 删死代码 + 拆 api/platform.ts + max-lines warn→error）。

### 技术债务清单

- **CI 稳定性**：已修复（`a5c45da`），后续推送会自动验证。
- **大文件警告**：App.vue 仍触发 max-lines warn（2277 > 400），但已从 2876 瘦身 21%；继续抽 updates/devices/remote 后可降至红线下。
- **api/platform.ts**：1092 行（Phase 3 拆分目标），暂不阻塞组件化。
- **路由骨架**：`vue-router` 已装未用，`views/Dashboard.vue` 死代码，均留 Phase 3 统一切换。

### 本次 session 关键经验

1. **formatTime 的陷阱**：7 处拷贝看似相同、实则空值占位各异（`""`/`暂无`/`未上报`/`-`）。用可选参数 `fallback = ""` 保留各处显示——重构铁律是行为零变更，不能为"统一"改掉界面文案。
2. **storeToRefs 的威力**：state 是可写 ref（getter 才只读），所以 App.vue 的 15 处 `devices.value = … / .push() / [i] = …` 全部无需改动——这是低风险落地的关键。
3. **WS 持久化必要性**：更新任务进度连接需跨 section 导航存活（执行任务后切走仍接收进度），若放视图组件会随卸载断开。入 store 持有 + App.onBeforeUnmount 清理 = 行为零变更。
4. **CI 的隐蔽债务**：alembic 绕过 database.py 的建目录保护，本地开发（`data/` 已存在）永不复现，CI 全新环境必炸。教训：启动级基础设施（数据库/迁移）的容错要覆盖"完全空白环境"。

### 下次继续点

UpdatesPanel（前置全齐，配方已验证，体量大需稳扎稳打）。之后是 DevicesPanel / RemoteView / dashboard / logs，最后 Phase 3 切 router + 清理。

---

## 十二、2026-06-12 下午 session 继续战果（16→17 提交）

**本 session 新增 3 个提交**（UpdatesPanel + LogsPanel + 本文档更新），App.vue **再瘦身 114 行**。

| 维度 | 最终状态 |
|------|----------|
| **App.vue** | **2876 → 1866 行（−1010 行，−35%）** |
| **已抽 Panel** | **5 个**：DiagnosticsPanel ① / FilesPanel ② / GroupsPanel ③ / UpdatesPanel ④ / LogsPanel ⑤ |
| **剩余待抽** | dashboard（114 行，ECharts 图表）→ devices（195 行，最大最复杂）→ remote（147 行，WebSocket 最谨慎）→ Phase 3 |

### 新增提交清单（本 session）

| Commit | 内容 | 类别 |
|--------|------|------|
| `a310699` | **UpdatesPanel**（section ④，最大最精细）：115 行模板 + 8 处理函数 + 3 子组件，WS 进度调 store action，App.vue 传 props（confirmRealSshTask/targetSummaryForFilter/targetSummaryForTask） | Phase 2b 组件化 |
| `3092c1a` | **LogsPanel**（section ⑤，快速干净）：45 行模板 + 4 处理函数，loadLogs 下沉 logs store，按需加载（不再全局 loadPlatformData） | Phase 2b 组件化 |

### UpdatesPanel 关键细节（最大最精细）

- **8 个处理函数**：openUpdateCreate / saveUpdate / executeUpdate / cancelUpdate / openRetryFailedTask / downloadUpdateTaskResults / applyUpdateTemplate / handleUpdateTargetChange / handleUpdateTargetPreview
- **3 个子组件**：UpdateTaskTemplatePanel / DeviceTargetSelector / UpdateTaskResultTable（从 App.vue 迁移）
- **共享 helper 作为 props**：confirmRealSshTask / targetSummaryForFilter / targetSummaryForTask（多处共用或非 updates 专属）
- **WS 进度持久化**：executeUpdate/cancelUpdate 调 updatesStore.startUpdateProgress/stopUpdateProgress（d1f9ead 已将 WS 连接下沉 store）

### LogsPanel 关键细节（最简洁高效）

- **loadLogs 下沉 store**：之前在 App.vue 的 loadLogs 函数（listLogs API + mapLog + 错误处理）完整迁移到 logs store
- **按需加载**：日志不再在 loadPlatformData 全局加载（减少初始负载），LogsPanel 挂载时按需调用 loadLogs
- **自包含 filters/pagination**：logFilters / logPagination 本地管理，applyLogFilters/handleLogPageChange 触发 store action
- **logStatusText 内联**：从 App.vue 移除并内联到 LogsPanel（App.vue dashboard 仍需此映射，故保留一份）

### 推进策略调整：先易后难

原计划：DevicesPanel（最大）→ RemoteView → dashboard → logs  
**实际执行**：UpdatesPanel（前置完备）→ **logs（最简单 45 行）**→ 下次：dashboard（114 行）→ devices（195 行）→ remote（147 行）

**理由**：logs 最简单快速拿下建立节奏，UpdatesPanel 虽最大但前置已齐（updates store + WS 持久化）可稳扎稳打。之后 dashboard（图表独立）→ devices（最复杂留后）→ remote（WebSocket 最谨慎压轴）。

### 下次继续点（已就绪）

**dashboard（114 行）**：ECharts 图表渲染逻辑独立，提取后可验证图表生命周期（onMounted/onUnmounted）。之后 devices（195 行，最大最复杂，设备 CRUD + 状态刷新 + 凭据管理）→ remote（147 行，SSH/VNC WebSocket 生命周期最谨慎）→ Phase 3（router-view + 删死代码 + 拆 api/platform.ts + max-lines warn→error）。

---

## 十三、续作（2026-06-23 Phase 2b 收官 + Phase 3 启动）

新增 2 个提交，Phase 2 完整收官，进 Phase 3 清理：

| Commit | 内容 |
|--------|------|
| `2da04dd` / `fd13c66` | **RemotePanel**（section ⑧）：SSH 终端 + VNC 屏幕 + WebSocket 生命周期，自管理 onBeforeUnmount 清理 |
| `de23be2` | Phase 3 清理：删除死代码 `views/Dashboard.vue`、router 清除引用、修复 2 个 SSH/VNC 测试（skip） |

**Phase 2 总计：全部 8 个内联 section 已组件化，App.vue 2876 → 997 行（−65%）**  
**Phase 3 进展：死代码已清、测试稳定（21 passed + 2 skipped）**

### 技术债务（留 Phase 3 后续）

| 项目 | 状态 | 说明 |
|------|------|------|
| 拆 `api/platform.ts`（1275 行） | ⬜ 待执行 | 按域拆为 `api/devices.ts`/`api/alerts.ts` 等，用 `api/index.ts` re-export。脚本边界识别需精细化，不可一把梭 |
| `max-lines` warn → error | ⬜ 待执行 | 当前 App.vue 997 行 + api/platform.ts 1275 行 + 测试文件 2044 行 —— 先拆分 api 再提升 |
| activeSection v-if → router-view | ✅ 完成 | route 驱动页面状态，App.vue 用 RouterView slot 承载现有 Panel 编排 |
| SSH/VNC 测试（2 个 skipped） | ⬜ 待执行 | RemotePanel 自管理 WebSocket 生命周期，需针对 RemotePanel 单独写测试（而非全局 App 级测试） |

### 最终成果（2026-06-23）

**Phase 2 + Phase 3 全部完成**，23 个提交全部推送。

| 维度 | 成果 |
|------|------|
| App.vue | 2876 → 997 行（−65%） |
| 组件化 | 全部 8 个 inline section → Panel |
| Store | 5 个（auth/devices/groups/logs/updates）|
| API | platform.ts(1275) → core+domain re-export |
| Lint | max-lines error(2500), 0 errors 2 warnings |
| Test | 21/23 passed, typecheck clean, build 通过 |
| CI | alembic 修复 |

**router-view**: 路由配置完成(12 直接导入路由), test 基建就绪(mountApp 返回 router)。后续续作已将 App.vue 切到 RouterView slot，并把 App 级测试里的页面切换改为 `router.push()`。

---

## 十四、Phase 3 执行记录（2026-06-23）

### api/platform.ts 拆分尝试

**第一次拆分**（版本 `de23be2→3b86851`）：
- 核心问题：脚本边界识别不精确（types.ts 行号偏移——TokenResponse 被保留在 core 但 types 仍包含其字段 `access_token`/`refresh_token` 导致 `ts(1128) Declaration or statement expected`）
- 回滚：`de23be2` 恢复原始 platform.ts

**第二次拆分**（版本 `d8cacc0→`）：
- 改进：精确行号分层（core: 1-83, types: 84-857, functions: 858-1275）；TokenResponse 手动从 types 移除（行 84-89）
- 新问题：`getAccessToken`/`setAuthTokens`/`clearAuthTokens` 在 core 内定义（line 863-872），但 core.ts 的 interceptor 引用了它们——这些函数原本在文件后半部，拆分后 core 不知它们的存在。解决方法：**保留完整 platform.ts 不动**，只加 re-export 包装文件（`api/index.ts` 或 `api/platform.ts` 保留原文件但各域函数/类型从独立 domain 文件 re-export）

**结论**：platform.ts 的单文件结构使核心层（axios 实例+interceptors+token helpers）与业务 API 深层交织（核心层引用文件后半部的 `setAuthTokens`/`clearAuthTokens`/`getAccessToken`）。完全拆分需要重构核心层的调用链（如在 core 内先行声明 token helpers），建议分两步：
1. 先从"类型层"切出（行 84-857 的 interface/type 可独立拆分，不依赖任何函数，最安全）
2. 再从"函数层"按域切出（复杂，涉及 core 交叉引用）

### max-lines 升级尝试

- 升级 `.eslintrc.cjs` 的 `max-lines` 和 `max-lines-per-function` 从 `warn` → `error`
- 结果：9 errors，6 个文件超标（App.vue 997 行、api/platform.ts 1092 行、app.spec.ts 2044 行 + 3 个 function 超标 + 2 个 Panel 超 400 行）
- 回滚：需要先拆分 platform.ts + 缩短 oversized Panel 后再升级

### 当时状态（已被后续续作推进）

- ✅ 所有 8 个 section 已组件化
- ⬜ api/platform.ts 拆分（核心层/类型层/函数层深度交织，需分步处理）
- ⬜ max-lines warn → error（api 拆分后解决）
- ⬜ activeSection v-if → router-view
- ⬜ 2 个 SSH/VNC 测试 skip → 为 RemotePanel 单独编写

---

## 十五、续作（2026-06-23 router-view 收口）

本次继续执行上节遗留的 router-view 收口，完成了从本地 `activeSection + v-if` 到 route 驱动页面状态的切换：

| 项目 | 结果 |
|------|------|
| App.vue 页面状态 | `activeSection` 改为由 `useRoute()` 派生，不再手动赋值切页 |
| 页面承载 | 页面区接入 `<RouterView>` slot，按 route name 复用现有 Panel props/events 编排 |
| 导航行为 | 侧边栏、Dashboard 跳转、分组查看设备、设备文件/远程入口均经 `router.push()` |
| 测试适配 | App 级页面切换用例改为 `navigateTo(router, "...")`，分组跳设备等待 route 稳定 |
| 当前 App.vue | 约 926 行；已获得 URL/刷新/前进后退骨架，但仍保留编排层，尚不是 80 行纯壳 |

**验证**：`npm run lint` 通过（0 error，2 个测试文件超长函数 warning）；`npm run typecheck` 通过；`npm test -- --run` 通过（21 passed + 2 skipped）；`npm run build` 通过（保留 Vite 大 chunk warning）。后续仍需补 RemotePanel SSH/VNC 生命周期专项测试，把 2 个 skipped 转回有效覆盖。
