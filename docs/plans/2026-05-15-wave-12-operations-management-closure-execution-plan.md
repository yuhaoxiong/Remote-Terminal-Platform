# Wave 12 运维管理闭环执行计划

## 目标

在 Wave 11 的凭据加固和运维 UX 基础上，补齐管理员日常使用中已经有后端能力但前端缺少入口的功能，形成登录后可直接完成的运维闭环。

## 范围

1. 管理员密码修改
   - 顶栏增加“修改密码”入口。
   - 调用 `PUT /api/auth/password`。
   - 修改成功后清理本地 Token，并回到登录页。

2. 分组管理闭环
   - 分组页支持创建、编辑、删除。
   - 分组卡片显示设备数量。
   - 点击分组可进入设备页并按分组过滤。
   - 设备创建和编辑支持选择 `group_id`。

3. 操作日志闭环
   - 日志页支持按 `action`、`target_type`、`status` 筛选。
   - 日志列表接入 `offset`、`limit` 分页参数。
   - “导出 CSV”调用 `GET /api/logs/export` 并下载 `operation_logs.csv`。
   - 后端 CSV 导出增加 `Content-Disposition`、`X-Content-Type-Options`，并对危险前缀字段做 CSV 注入防护。

4. 设备同步配置入口
   - 设备表增加“同步配置”按钮。
   - 调用 `POST /api/devices/{id}/sync-config`。
   - 展示生成的 frpc 配置并支持复制。

5. 系统诊断页
   - 导航新增“系统诊断”。
   - 调用 `GET /api/diagnostics/config`。
   - 展示服务、数据库、文件后端、远程网关、默认 SSH 用户和 Wave 11 安全摘要。
   - 只展示非敏感摘要，不展示密码、Token、私钥或密钥内容。

## 验证计划

- 后端：更新日志 CSV 导出回归测试，覆盖危险前缀字段和下载响应头。
- 前端：Vitest 覆盖改密、分组 CRUD、分组筛选、日志筛选导出、同步配置和诊断页。
- 构建：运行 `npm.cmd run build`。
- 全量：运行后端 pytest、前端 Vitest、Postman JSON 解析和 `git diff --check`。

## 非目标

- 不实现多用户 RBAC。
- 不实现完整系统设置页。
- 不实现图表报表、告警中心、xterm.js 或 noVNC 嵌入式终端体验。
- 不引入数据库迁移框架。
