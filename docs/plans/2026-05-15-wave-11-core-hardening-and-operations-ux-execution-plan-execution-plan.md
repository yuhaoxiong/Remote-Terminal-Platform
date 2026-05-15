# Wave 11 核心加固与运维体验补全执行计划

> **For Codex:** REQUIRED SUB-SKILL: Use governed `$vibe` execution discipline and follow this plan task by task.

**Goal:** 在不扩大产品范围的前提下，完成设备 SSH 凭据加密、弱配置诊断、前端设备运维操作补全和批量任务安全确认。

**Architecture:** 后端先建立凭据加密边界，再把设备服务、SSH 服务、文件后端和 frps 导入统一接到该边界；前端在现有 `App.vue` 单页结构内补齐设备编辑、删除、刷新和更新任务确认。所有新增行为都通过现有 FastAPI、SQLAlchemy、Vue 3、Element Plus、Vitest 和 pytest 测试体系验证。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, cryptography/Fernet, Paramiko, Vue 3, TypeScript, Element Plus, Vitest, pytest, Postman Collection JSON.

---

## Scope Guard

- 本计划只执行 Wave 11 需求文档中批准的范围。
- 不引入 Alembic、RBAC、告警系统、ECharts、完整 xterm.js/noVNC、文件管理完整前端页、定时任务完整前端页。
- 不回滚或暂存未跟踪的 `docs/02-优化建议文档.md`，除非用户明确要求。
- 真实 SSH 任务相关 UI 必须默认防误触。

## Task 1: 后端凭据加密服务

**Files:**
- Create: `backend/app/services/encryption.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_wave11_credentials_encryption.py`

**Step 1: 写失败测试**

覆盖：
- 有 `credential_encryption_key` 时，明文密码加密后不等于原文。
- 解密返回原文。
- 空密码保持 `None` 或空值语义。
- 无密钥时，开发环境仍能兼容旧明文读取，但诊断应能标记风险。

Run:

```powershell
cd C:\01_work\02_program\远程终端平台\backend
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests/test_wave11_credentials_encryption.py -q
```

Expected: 新服务未实现时失败。

**Step 2: 实现最小加密服务**

新增 `EncryptionService`：
- `encrypt_optional(value: str | None) -> str | None`
- `decrypt_optional(value: str | None) -> str | None`
- 支持识别 Fernet token。
- 兼容历史明文：无法按 Fernet 解密且未显式要求严格模式时，返回原文。

配置新增：
- `credential_encryption_key: str | None = None`
- 可选辅助方法或属性判断是否已配置凭据加密。

**Step 3: 运行测试**

Run:

```powershell
py -3.12 -m pytest tests/test_wave11_credentials_encryption.py -q
```

Expected: PASS。

## Task 2: 接入设备创建、更新、frps 导入和 SSH 解密

**Files:**
- Modify: `backend/app/services/device_service.py`
- Modify: `backend/app/services/frps_import_service.py`
- Modify: `backend/app/services/ssh_service.py`
- Modify: `backend/app/services/file_service.py` 或实际 SFTP 服务文件
- Test: `backend/tests/test_wave11_credentials_encryption.py`
- Test: existing Wave 8/Wave 9/Wave 10 tests

**Step 1: 扩展失败测试**

覆盖：
- 创建设备时数据库保存的 `ssh_password_encrypted` 不等于明文。
- 更新设备时，传入新密码会重新加密。
- 更新设备时，不传密码不会清空已有凭据。
- `SshService` 调用 Paramiko 前使用解密后的设备密码。
- frps 导入默认 `ztl` / `123456` 也按加密路径写入。
- 旧数据库中的明文 `123456` 仍可被 SSH 服务读取。

Run:

```powershell
py -3.12 -m pytest tests/test_wave11_credentials_encryption.py tests/test_wave9_diagnostics_frps.py tests/test_wave10_update_task_ssh_execution.py -q
```

Expected: 未接入前失败。

**Step 2: 实现接入**

- `DeviceService` 负责写入前加密，不在 schema 层加密。
- `ssh_password_encrypted` 字段继续沿用现有字段名，避免本轮做迁移。
- `SshService` 只接收解密后的密码用于连接，不记录明文。
- SFTP 文件后端与 Web SSH 如果复用 `SshService` 则自然继承；如果单独建连接，也必须走同一解密函数。
- frps 导入新设备时调用设备服务或共享加密 helper，避免重复逻辑。

**Step 3: 运行目标测试**

Run:

```powershell
py -3.12 -m pytest tests/test_wave11_credentials_encryption.py tests/test_wave8_remote_access.py tests/test_wave9_diagnostics_frps.py tests/test_wave10_update_task_ssh_execution.py -q
```

Expected: PASS。

## Task 3: 弱配置诊断增强

**Files:**
- Modify: `backend/app/routers/diagnostics.py`
- Modify: `backend/app/schemas/diagnostics.py` if present
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_wave9_diagnostics_frps.py` 或新增 `backend/tests/test_wave11_diagnostics_security.py`

**Step 1: 写失败测试**

覆盖：
- `GET /api/diagnostics/config` 返回 `security_warnings` 或等价字段。
- 默认 JWT secret、默认管理员密码、默认设备 SSH 密码、未配置凭据加密密钥时出现 warning。
- 响应中不包含真实 JWT secret、设备 SSH 密码、加密密钥、Token、私钥内容。

**Step 2: 实现摘要**

建议响应结构：

```json
{
  "security": {
    "credential_encryption_configured": true,
    "default_admin_password_in_use": false,
    "default_device_ssh_password_in_use": true,
    "jwt_secret_configured": true,
    "warnings": []
  }
}
```

**Step 3: 运行诊断测试**

Run:

```powershell
py -3.12 -m pytest tests/test_wave11_diagnostics_security.py tests/test_wave9_diagnostics_frps.py -q
```

Expected: PASS。

## Task 4: 前端 API 封装补全

**Files:**
- Modify: `frontend/src/api/platform.ts`
- Test: `frontend/src/__tests__/app.spec.ts`

**Step 1: 写失败测试或扩展 mock 断言**

覆盖：
- 调用设备更新 API。
- 调用删除设备 API。
- 调用单设备状态 API。
- 调用取消更新任务 API。
- 真实 SSH 执行创建前有确认路径。

**Step 2: 实现 API**

新增或补齐：
- `updateDevice(deviceId, payload)`
- `deleteDevice(deviceId)`
- `getDeviceStatus(deviceId)`
- `cancelUpdateTask(taskId)`
- 如已有函数则只补类型和调用点。

**Step 3: 运行前端测试**

Run:

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
```

Expected: PASS。

## Task 5: 前端设备编辑、删除、状态刷新

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/__tests__/app.spec.ts`

**Step 1: 写失败测试**

覆盖：
- 点击“编辑”打开设备表单，保存后调用 `updateDevice`。
- 密码字段为空时不发送 `ssh_password`。
- 输入新密码时发送 `ssh_password`。
- 点击“删除”确认后调用 `deleteDevice` 并刷新列表。
- 点击“刷新状态”后调用 `getDeviceStatus` 并更新当前行状态。

**Step 2: 实现 UI**

- 在设备表格操作列加入“编辑”“删除”“刷新状态”。
- 复用当前创建设备表单，但需要区分 create/edit。
- 表单中文提示：
  - “SSH 密码留空表示不修改已有凭据”
  - “API 不会回显已有密码”
- 删除使用 Element Plus 确认弹窗。
- 操作完成后展示中文成功/失败消息，避免重复消息。

**Step 3: 运行前端测试**

Run:

```powershell
npm.cmd test -- --run
```

Expected: PASS。

## Task 6: 批量更新任务防误触与取消

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/api/platform.ts`
- Modify: `frontend/src/__tests__/app.spec.ts`
- Optionally modify: `backend/tests/test_wave4_update_tasks_api.py`

**Step 1: 写失败测试**

覆盖：
- `execution_mode=ssh_command` 时，点击创建或执行前出现确认。
- 确认文案展示命令、模式、筛选范围。
- 用户取消确认时不调用 API。
- 点击取消任务调用 `cancelUpdateTask`。
- 已完成任务不展示取消按钮，运行中或待执行任务展示取消按钮。

**Step 2: 实现 UI**

- 使用 Element Plus `ElMessageBox.confirm`。
- 真实执行确认文案必须中文明确：
  - “将通过 SSH 在目标设备上真实执行命令”
  - “建议先使用演练模式确认范围”
- 任务列表操作列补“取消”。
- 设备结果展示强化：
  - `exit_code=0` 显示“成功”
  - `exit_code!=0` 显示“退出码 N”
  - `skipped` 显示“已跳过”
  - `error_message` 优先显示但不展示敏感信息。

**Step 3: 运行测试**

Run:

```powershell
npm.cmd test -- --run
```

Expected: PASS。

## Task 7: Postman、README、API、部署文档同步

**Files:**
- Modify: `docs/postman/edge-platform.postman_collection.json`
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `docs/deployment.md`

**Step 1: 更新 Postman**

新增请求：
- 诊断安全摘要
- 编辑设备
- 删除设备
- 刷新设备状态
- 取消更新任务

要求：
- JSON 可解析。
- 继续继承集合级 Bearer Token。
- 保存动态 ID 的脚本必须在 Tests 中，不放 Pre-request Script。

**Step 2: 更新文档**

- README 增加 Wave 11 行为说明。
- API 文档补充诊断安全摘要和凭据加密行为。
- 部署文档补充 `CREDENTIAL_ENCRYPTION_KEY` 生成和配置方式。
- 明确旧明文兼容策略和后续轮换计划。

**Step 3: 校验 JSON**

Run:

```powershell
node -e "const fs=require('fs'); JSON.parse(fs.readFileSync('docs/postman/edge-platform.postman_collection.json','utf8')); console.log('postman json ok')"
```

Expected: `postman json ok`。

## Task 8: 全量验证与提交

**Files:**
- All touched files

**Step 1: 后端全量测试**

Run:

```powershell
cd C:\01_work\02_program\远程终端平台\backend
$env:PYTHONPATH='C:\01_work\02_program\远程终端平台\backend'
py -3.12 -m pytest tests --basetemp 'C:\01_work\02_program\远程终端平台\.pytest-tmp'
```

Expected: 全部通过；若仍有 `.pytest_cache` 权限警告，记录为已知非阻断警告。

**Step 2: 前端测试和构建**

Run:

```powershell
cd C:\01_work\02_program\远程终端平台\frontend
npm.cmd test -- --run
npm.cmd run build
```

Expected:
- Vitest 全部通过。
- 构建成功；如果仍有 Vite chunk size 警告，记录为既有非阻断警告。

**Step 3: 差异检查**

Run:

```powershell
cd C:\01_work\02_program\远程终端平台
git diff --check
git status --short --branch
```

Expected:
- `git diff --check` 无错误。
- 只暂存 Wave 11 相关文件，不暂存无关未跟踪文件。

**Step 4: 提交**

Run:

```powershell
git add <Wave 11 touched files>
git commit -m "Implement Wave 11 credential hardening and operations UX"
```

Expected:
- 生成一个本地提交。
- 如果需要推送，单独运行 `git push origin main`，网络失败时如实报告。

## Verification Matrix

| Area | Required evidence |
| --- | --- |
| 凭据加密 | pytest 覆盖加密、解密、旧明文兼容、不回显明文 |
| SSH 执行 | Wave 10 SSH 任务测试继续通过 |
| frps 导入 | Wave 9 frps 导入测试继续通过 |
| 诊断接口 | pytest 覆盖 warning 和敏感信息不泄露 |
| 设备编辑/删除 | Vitest 覆盖 API 调用和中文 UI |
| 批量任务确认/取消 | Vitest 覆盖确认、取消确认、取消任务 |
| 文档/Postman | JSON parse、README/API/deployment 与代码一致 |
| 全量回归 | 后端 pytest、前端 test/build、git diff check |

## Rollback Plan

- 若凭据加密导致 SSH/SFTP 回归，先保留旧明文兼容读取并修复写入路径，不做数据破坏性迁移。
- 若前端编辑表单引入较大回归，先拆分为编辑基础字段和密码更新两步提交。
- 若 Postman 或文档更新不影响代码测试，可独立修复，不回滚代码实现。

## Plan Approval Gate

本计划处于 Vibe `xl_plan` 阶段。执行前需要用户明确批准计划；批准后再进入 Wave 11 实现阶段。
