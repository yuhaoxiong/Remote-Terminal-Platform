# 接口文档

本文档基于当前代码生成和人工核对,覆盖 FastAPI 应用实际暴露的接口。默认服务地址为 `http://127.0.0.1:8000`,所有 REST 接口默认使用 `/api` 前缀。

## 通用约定

### 认证

除 `GET /api/health`、`POST /api/auth/login`、`POST /api/auth/refresh` 外,其余 REST 接口均需要请求头:

```http
Authorization: Bearer <access_token>
```

更新任务进度 WebSocket 使用查询参数传递 access token:

```text
/api/ws/update-tasks/{task_id}?token=<access_token>
```

### 请求与响应格式

- 普通请求体为 JSON,推荐请求头 `Content-Type: application/json`。
- 普通响应体为 JSON。
- 时间字段为 ISO 8601 字符串。
- 文件下载接口返回二进制响应,`Content-Type` 会按文件名推断,无法推断时为 `application/octet-stream`。
- 日志导出接口返回 `text/csv`。

### 常见状态码

| 状态码 | 含义 |
| --- | --- |
| `200` | 请求成功 |
| `201` | 创建成功 |
| `204` | 删除或无响应体操作成功 |
| `400` | 请求业务参数错误,例如旧密码错误、文件路径不安全 |
| `401` | token 无效、用户名密码错误、refresh token 无效 |
| `403` | 未提供 Bearer token,或已认证但角色无权限执行该操作 |
| `404` | 资源不存在 |
| `409` | 资源冲突或任务状态不允许操作 |
| `422` | Pydantic 参数校验失败 |

通用错误响应:

```json
{
  "detail": "错误信息"
}
```

## 数据模型

### TokenResponse

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `access_token` | string | 访问 token,默认有效期 30 分钟 |
| `refresh_token` | string | 刷新 token,默认有效期 24 小时 |
| `token_type` | string | 固定为 `bearer` |

### DeviceCreate

| 字段 | 类型 | 必填 | 约束/默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | 1-120 字符 | 设备名称 |
| `device_sn` | string | 是 | 1-120 字符,唯一 | 设备序列号 |
| `project_id` | string | 是 | 1-120 字符 | 项目号 |
| `location` | string/null | 否 | 最大 255 字符 | 部署位置 |
| `hardware_model` | string/null | 否 | 最大 120 字符 | 硬件型号 |
| `ssh_user` | string | 否 | 默认 `ztl`,1-64 字符 | SSH 用户 |
| `ssh_port` | integer/null | 否 | 1-65535 | 指定 SSH 远程端口;省略或 `null` 时自动分配 |
| `vnc_port` | integer/null | 否 | 1-65535 | 指定 VNC 远程端口;省略或 `null` 时自动分配 |
| `local_ip` | string/null | 否 | 最大 64 字符 | 内网 IP |
| `os_version` | string/null | 否 | 最大 120 字符 | 系统版本 |
| `description` | string/null | 否 | 无 | 备注 |
| `tags` | string[]/null | 否 | 无 | 标签列表 |
| `group_id` | integer/null | 否 | 无 | 分组 ID |

### DeviceRead

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 设备 ID |
| `name` | string | 设备名称 |
| `device_sn` | string | 设备序列号 |
| `project_id` | string | 项目号 |
| `location` | string/null | 部署位置 |
| `hardware_model` | string/null | 硬件型号 |
| `ssh_port` | integer/null | 分配的 SSH 远程端口 |
| `vnc_port` | integer/null | 分配的 VNC 远程端口 |
| `ssh_user` | string | SSH 用户 |
| `local_ip` | string/null | 内网 IP |
| `os_version` | string/null | 系统版本 |
| `description` | string/null | 备注 |
| `tags` | string[]/null | 标签列表 |
| `group_id` | integer/null | 分组 ID |
| `status` | string | 设备状态,当前常见值为 `unknown`、`online`、`offline` |
| `last_seen` | datetime/null | 最后上报时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### DeviceMetricCreate

| 字段 | 类型 | 必填 | 约束/默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | string | 否 | 默认 `online`,1-32 字符 | 上报后的设备状态 |
| `cpu_percent` | number/null | 否 | 0-100 | CPU 使用率 |
| `memory_percent` | number/null | 否 | 0-100 | 内存使用率 |
| `disk_percent` | number/null | 否 | 0-100 | 磁盘使用率 |
| `temperature_celsius` | number/null | 否 | 无 | 温度 |
| `load_average` | number/null | 否 | 大于等于 0 | 负载 |

### Group

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 分组 ID |
| `name` | string | 分组名称,1-120 字符 |
| `parent_id` | integer/null | 父分组 ID |
| `description` | string/null | 描述,最大 500 字符 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### UpdateTask

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 更新任务 ID |
| `name` | string | 任务名称,1-120 字符 |
| `task_type` | string | 任务类型,1-32 字符 |
| `command` | string | 执行命令 |
| `rollback_command` | string/null | 回滚命令 |
| `target_filter` | object/null | 目标筛选条件 |
| `execution_mode` | string | `dry_run` 或 `ssh_command` |
| `failure_strategy` | string | `continue`、`pause` 或 `rollback` |
| `concurrency_limit` | integer | 并发限制,1-50,默认 5 |
| `status` | string | `pending`、`running`、`completed`、`partial_failed`、`canceled` 等 |
| `device_count` | integer | 任务关联设备数 |
| `devices` | object[] | 每台设备的执行状态 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

`target_filter` 当前支持:

```json
{
  "project_id": "factory-a",
  "group_id": 1,
  "status": "online",
  "device_ids": [1, 2, 3],
  "tags": ["vision", "prod"]
}
```

### ScheduledTask

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 定时任务 ID |
| `name` | string | 任务名称,1-120 字符 |
| `task_type` | string | 任务类型,1-32 字符 |
| `schedule` | string | 调度表达式,必须以 `cron:` 或 `interval:` 开头 |
| `command` | string/null | 执行命令 |
| `target_filter` | object/null | 目标筛选条件 |
| `enabled` | boolean | 是否启用 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### OperationLog

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 日志 ID |
| `user_id` | integer/null | 操作用户 ID |
| `action` | string | 动作名称 |
| `target_type` | string/null | 目标类型 |
| `target_id` | integer/null | 目标 ID |
| `status` | string | 操作状态 |
| `detail` | string/null | 详情 |
| `created_at` | datetime | 创建时间 |

### Alert

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 告警 ID |
| `title` | string | 告警标题 |
| `message` | string | 告警描述 |
| `severity` | string | `warning` 或 `critical` |
| `status` | string | `open`、`acknowledged` 或 `resolved` |
| `source_type` | string | `device`、`metric`、`scheduled_task` 或 `update_task` |
| `alert_type` | string | 规则类型,例如 `cpu_high`、`metrics_stale` |
| `device_id` | integer/null | 关联设备 ID |
| `scheduled_task_id` | integer/null | 关联定时任务 ID |
| `update_task_id` | integer/null | 关联批量任务 ID |
| `metric_name` | string/null | 关联指标名 |
| `metric_value` | number/null | 触发时指标值 |
| `threshold_value` | number/null | 触发阈值 |
| `dedupe_key` | string | 去重键 |
| `acknowledged_by_user_id` | integer/null | 确认人 |
| `acknowledged_at` | datetime/null | 确认时间 |
| `resolved_at` | datetime/null | 恢复时间 |
| `note` | string/null | 确认或恢复备注 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### AlertRule

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 规则 ID |
| `rule_type` | string | 规则类型 |
| `enabled` | boolean | 是否启用 |
| `severity` | string | `warning` 或 `critical` |
| `threshold_value` | number/null | 阈值,用于 CPU/内存/磁盘等指标规则 |
| `window_minutes` | integer/null | 时间窗口,用于指标冻结等规则 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

## 系统接口

### 健康检查

```http
GET /api/health
```

认证:不需要。

响应 `200`:

```json
{
  "status": "ok",
  "service": "edge-platform",
  "version": "0.1.0"
}
```

### 系统设置

系统设置接口用于读取后端注册表白名单、查看当前有效配置、保存数据库覆盖值、恢复默认值、查看变更历史和触发 systemd 托管场景下的后端重启。

认证:仅 `admin`。`operator` 调用会返回 `403`。接口不会返回密码、Token、私钥、Webhook 密钥或凭据加密密钥明文。

配置读取顺序:

```text
数据库覆盖值 > 系统配置/环境变量 > 代码默认值
```

#### 获取系统设置注册表

```http
GET /api/system-settings/schema
```

响应 `200`:

```json
{
  "groups": {
    "remote_connection": "远程连接",
    "file_storage": "文件存储"
  },
  "items": [
    {
      "key": "REMOTE_GATEWAY_HOST",
      "name": "SSH 网关主机",
      "description": "用于远程 SSH 连接的网关地址",
      "category": "remote_connection",
      "value_type": "string",
      "editable": true,
      "secret": false,
      "requires_restart": false,
      "runtime_effective": true,
      "options": null,
      "min_value": null,
      "max_value": null
    },
    {
      "key": "DEFAULT_VNC_PASSWORD",
      "name": "默认 VNC 密码",
      "description": "远程 VNC 连接默认使用的密码，可在连接页临时覆盖",
      "category": "remote_connection",
      "value_type": "string",
      "editable": true,
      "secret": true,
      "requires_restart": false,
      "runtime_effective": true,
      "options": null,
      "min_value": null,
      "max_value": null
    }
  ]
}
```

#### 获取当前有效设置

```http
GET /api/system-settings/effective
```

响应 `200`:

```json
{
  "items": [
    {
      "key": "FILE_BACKEND",
      "name": "文件后端",
      "category": "file_storage",
      "value_type": "select",
      "value": "local",
      "configured": true,
      "source": "database",
      "editable": true,
      "secret": false,
      "requires_restart": true,
      "pending_restart": true,
      "is_valid": true,
      "invalid_reason": null,
      "updated_at": "2026-06-10T10:00:00"
    }
  ],
  "pending_restart_count": 1,
  "database_override_count": 1,
  "credential_encryption_configured": true,
  "systemd_managed": false
}
```

`source` 可能为 `database`、`env` 或 `default`。敏感项只返回是否已配置,`value` 不返回明文。

#### 保存分组设置

```http
PUT /api/system-settings/groups/{group_key}
Content-Type: application/json
```

请求体:

```json
{
  "values": {
    "REMOTE_GATEWAY_HOST": "124.70.177.226",
    "SSH_TIMEOUT_SECONDS": 30
  }
}
```

响应 `200`:`SystemSettingGroupUpdateResponse`。

错误:

- `400`:分组不存在、key 不属于该分组、配置项不可编辑、敏感配置未配置加密密钥或取值非法。
- `403`:非管理员。

保存可运行时生效的配置后,当前后端进程会刷新内存缓存。保存 `requires_restart=true` 的配置会标记待重启,重启后才作为有效配置参与运行。

#### 恢复默认值

```http
POST /api/system-settings/{key}/reset
```

响应 `200`:

```json
{
  "key": "REMOTE_GATEWAY_HOST",
  "source": "system",
  "requires_restart": false,
  "pending_restart_count": 0
}
```

该接口删除数据库覆盖值,使配置回退到系统配置/环境变量或代码默认值。

#### 变更历史

```http
GET /api/system-settings/changes?limit=50&offset=0
```

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "setting_key": "REMOTE_GATEWAY_HOST",
      "category": "remote_connection",
      "action": "update",
      "old_source": "default",
      "new_source": "database",
      "old_value_snapshot": "-",
      "new_value_snapshot": "124.70.177.226",
      "is_secret": false,
      "requires_restart": false,
      "pending_restart_after_change": false,
      "actor_user_id": 1,
      "actor_username": "admin",
      "client_ip": "127.0.0.1",
      "created_at": "2026-06-10T10:00:00"
    }
  ]
}
```

敏感配置的 `old_value_snapshot` 和 `new_value_snapshot` 只保存脱敏文本。

#### 重启后端服务

```http
POST /api/system-settings/restart
Content-Type: application/json
```

请求体:

```json
{
  "confirm_text": "确认重启"
}
```

成功响应 `202`:

```json
{
  "status": "accepted",
  "message": "已提交重启请求，服务将由 systemd 自动拉起"
}
```

错误:

- `400`:确认文本不正确。
- `409`:后端未检测到 systemd 托管,拒绝退出进程。

## 认证接口

### 登录

```http
POST /api/auth/login
```

认证:不需要。

请求体:

```json
{
  "username": "admin",
  "password": "admin"
}
```

响应 `200`:`TokenResponse`。

错误:

- `401`:用户名或密码错误。
- `422`:用户名或密码为空。

### 刷新 Token

```http
POST /api/auth/refresh
```

认证:不需要 Bearer token,但请求体必须提供 refresh token。

请求体:

```json
{
  "refresh_token": "<refresh_token>"
}
```

响应 `200`:新的 `TokenResponse`。

错误:

- `401`:refresh token 无效、过期或用户不存在。
- `422`:请求体校验失败。

### 当前用户

```http
GET /api/auth/me
```

认证:需要。

响应 `200`:

```json
{
  "id": 1,
  "username": "admin",
  "role": "admin",
  "is_active": true
}
```

### 修改密码

```http
PUT /api/auth/password
```

认证:需要。

请求体:

```json
{
  "old_password": "admin",
  "new_password": "new-password"
}
```

响应 `204`:无响应体。

错误:

- `400`:旧密码错误。
- `422`:新密码少于 8 个字符或请求体校验失败。

## 设备接口

### 创建设备

```http
POST /api/devices
```

认证:需要。

请求体:`DeviceCreate`。

响应 `201`:`DeviceRead`。未指定端口或端口为 `null` 时会自动分配 `ssh_port` 和 `vnc_port`;提供整数时会预留指定端口。

错误:

- `409`:`device_sn` 重复、端口池耗尽或指定端口已被其他设备占用。
- `422`:请求体校验失败。

### 查询设备列表

```http
GET /api/devices
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 | 分页偏移 |
| `limit` | integer | `50` | 1-200 | 分页大小 |
| `search` | string | 无 | 无 | 按名称或序列号模糊搜索 |
| `project_id` | string | 无 | 无 | 按项目号筛选 |
| `group_id` | integer | 无 | 无 | 按分组筛选 |
| `tag` | string | 无 | 无 | 按单个标签筛选 |
| `status` | string | 无 | 无 | 按设备状态筛选 |

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "name": "edge-01",
      "device_sn": "SN001",
      "project_id": "factory-a",
      "location": "beijing",
      "hardware_model": "jetson",
      "ssh_port": 10000,
      "vnc_port": 10500,
      "ssh_user": "root",
      "local_ip": "192.168.1.10",
      "os_version": "Debian 11",
      "description": null,
      "tags": ["vision"],
      "group_id": null,
      "status": "unknown",
      "last_seen": null,
      "created_at": "2026-05-12T01:00:00",
      "updated_at": "2026-05-12T01:00:00"
    }
  ]
}
```

### 查询设备详情

```http
GET /api/devices/{device_id}
```

认证:需要。

响应 `200`:`DeviceRead`。

错误:

- `404`:设备不存在。

### 更新设备

```http
PUT /api/devices/{device_id}
```

认证:需要。

请求体:`DeviceCreate` 的可选字段子集,额外支持 `status`。端口字段省略表示保持不变,显式传 `null` 表示释放并清空,传整数表示切换并预留指定端口。SSH/VNC 同时更新时在同一事务内完成,任一冲突都会整体回滚。

响应 `200`:`DeviceRead`。

错误:

- `404`:设备不存在。
- `409`:指定 SSH/VNC 端口已被其他设备占用。
- `422`:请求体校验失败。

### 删除设备

```http
DELETE /api/devices/{device_id}
```

认证:需要。

响应 `204`:无响应体。删除时会释放已分配的 SSH/VNC 端口。

错误:

- `404`:设备不存在。

### 查询设备状态

```http
GET /api/devices/{device_id}/status
```

认证:需要。

响应 `200`:

```json
{
  "id": 1,
  "status": "online",
  "last_seen": "2026-05-12T01:00:00"
}
```

### 生成 frpc 配置

```http
POST /api/devices/{device_id}/sync-config
```

认证:需要。

响应 `200`:

```json
{
  "device_id": 1,
  "status": "generated",
  "config": "[SN001-ssh]\ntype = tcp\n..."
}
```

当前实现只生成配置内容并记录日志,不会真实 SSH 写入设备。

### 上报设备指标

```http
POST /api/devices/{device_id}/metrics
```

认证:需要。

请求体:`DeviceMetricCreate`。

响应 `201`:

```json
{
  "id": 1,
  "device_id": 1,
  "status": "online",
  "cpu_percent": 42.5,
  "memory_percent": 60.1,
  "disk_percent": 75.0,
  "temperature_celsius": 54.2,
  "load_average": 1.2,
  "recorded_at": "2026-05-12T01:00:00"
}
```

### 查询设备指标

```http
GET /api/devices/{device_id}/metrics
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `limit` | integer | `50` | 1-200 | 最多返回条数 |

响应 `200`:

```json
{
  "total": 10,
  "items": []
}
```

### 创建 SSH 会话描述

```http
POST /api/devices/{device_id}/remote/ssh
```

认证:需要。

响应 `200`:

```json
{
  "device_id": 1,
  "session_type": "ssh",
  "status": "ready",
  "remote_port": 10000,
  "websocket_url": "/api/ws/devices/1/ssh",
  "proxy_url": null
}
```

返回会话描述后,前端需要把 `websocket_url` 与 access token 拼成 WebSocket 地址:

```text
/api/ws/devices/{device_id}/ssh?token=<access_token>
```

Web SSH 消息格式:

```json
{ "type": "input", "data": "whoami\n" }
```

```json
{ "type": "resize", "columns": 120, "rows": 32 }
```

```json
{ "type": "close" }
```

后端输出:

```json
{ "type": "output", "data": "shell-ready\n" }
```

客户端发送 `{ "type": "close" }` 后,后端会关闭 shell 并返回:

```json
{ "type": "status", "status": "closed" }
```

错误:

- `400`:设备没有分配 SSH 端口,或设备没有可用的 SSH 凭据。
- `404`:设备不存在。

### 创建 VNC 会话描述

```http
POST /api/devices/{device_id}/remote/vnc
```

认证:需要。

响应 `200`:

```json
{
  "device_id": 1,
  "session_type": "vnc",
  "status": "ready",
  "remote_port": 10500,
  "websocket_url": "/api/ws/devices/1/vnc",
  "proxy_url": "/novnc/vnc.html?device_id=1&port=10500",
  "vnc_password": "<DEFAULT_VNC_PASSWORD 或 null>"
}
```

返回会话描述后,前端 noVNC 客户端连接:

```text
/api/ws/devices/{device_id}/vnc?token=<access_token>
```

该 WebSocket 转发二进制 VNC 数据,目标为 `vnc_gateway_host` 和设备 `vnc_port`。若系统设置或环境变量配置了 `DEFAULT_VNC_PASSWORD`,VNC 会话描述会返回 `vnc_password` 供前端 noVNC 自动认证;连接页手动输入的密码优先于默认值。当前前端只支持内嵌连接、断开和浏览器全屏,不支持剪贴板同步、文件拖拽或远程分辨率高级控制。

错误:

- `400`:设备没有分配 VNC 端口。
- `404`:设备不存在。

## 设备文件接口

文件接口支持本地存储后端和 SFTP 后端。默认本地存储根目录来自 `file_storage_dir`,若未配置且使用 SQLite,则存储在数据库目录旁的 `device-files/{device_id}` 下;设置 `FILE_BACKEND=sftp` 后会通过设备 SSH 端口访问真实设备文件系统。

### 查询文件列表

```http
GET /api/devices/{device_id}/files
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `path` | string | `.` | 远端目录路径；`.` 表示 SFTP 登录目录 |

响应 `200`:

```json
{
  "device_id": 1,
  "path": "/opt/app",
  "items": [
    {
      "name": "config.yaml",
      "path": "/opt/app/config.yaml",
      "type": "file",
      "size": 12
    }
  ]
}
```

错误:

- `400`:路径包含 `..` 等不安全片段或逃逸设备存储目录。
- `404`:设备不存在，或远程目录不存在/无权访问。
- `502`:SSH/SFTP 连接或认证失败。

### 上传文件

```http
POST /api/devices/{device_id}/files/upload
```

认证:需要。

推荐请求体:`multipart/form-data`。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `remote_path` | string | 是 | 远程目标文件路径 |
| `file` | file | 是 | 上传文件,支持任意文件类型 |

兼容旧 JSON 文本上传格式:

```json
{
  "remote_path": "/opt/app/config.yaml",
  "content": "key: value"
}
```

响应 `201`:

```json
{
  "device_id": 1,
  "remote_path": "/opt/app/config.yaml",
  "status": "uploaded",
  "size": 10
}
```

### 下载文件

```http
GET /api/devices/{device_id}/files/download?remote_path=/opt/app/config.yaml
```

认证:需要。

响应 `200`:二进制文件内容。响应头包含:

```http
Content-Disposition: attachment; filename*=UTF-8''config.yaml
Content-Type: application/octet-stream
```

`Content-Type` 会按文件名推断,无法推断时为 `application/octet-stream`。

错误:

- `404`:设备或文件不存在。

### 删除文件

```http
DELETE /api/devices/{device_id}/files
```

认证:需要。

请求体:

```json
{
  "remote_path": "/opt/app/config.yaml"
}
```

响应 `200`:

```json
{
  "device_id": 1,
  "remote_path": "/opt/app/config.yaml",
  "status": "deleted",
  "size": null
}
```

## 分组接口

### 创建分组

```http
POST /api/groups
```

认证:需要。

请求体:

```json
{
  "name": "北京机房",
  "parent_id": null,
  "description": "核心站点"
}
```

响应 `201`:`Group`。

错误:

- `409`:分组名称冲突。

### 查询分组列表

```http
GET /api/groups
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 |
| `limit` | integer | `50` | 1-200 |

响应 `200`:

```json
{
  "total": 1,
  "items": []
}
```

### 更新分组

```http
PUT /api/groups/{group_id}
```

认证:需要。

请求体:`name`、`parent_id`、`description` 均可选。

响应 `200`:`Group`。

### 删除分组

```http
DELETE /api/groups/{group_id}
```

认证:需要。

响应 `204`:无响应体。

## 批量更新任务接口

### 创建更新任务

```http
POST /api/update-tasks
```

认证:需要。

请求体:

```json
{
  "name": "升级视觉服务",
  "task_type": "script",
  "command": "systemctl restart vision.service",
  "rollback_command": null,
  "target_filter": {
    "project_id": "factory-a",
    "tags": ["vision"]
  },
  "execution_mode": "dry_run",
  "failure_strategy": "continue",
  "concurrency_limit": 5
}
```

响应 `201`:`UpdateTask`。

校验规则:

- `execution_mode` 只能是 `dry_run` 或 `ssh_command`,默认 `dry_run`。
- `failure_strategy` 只能是 `continue`、`pause`、`rollback`。
- 当 `failure_strategy` 为 `rollback` 时,必须提供 `rollback_command`。

当前实现会按 `target_filter` 在创建时固化目标设备,并创建对应的 `update_task_devices` 记录。

### 预览更新任务目标

```http
POST /api/update-tasks/preview-targets
```

认证:需要。

请求体:

```json
{
  "target_filter": {
    "project_id": "factory-a",
    "group_id": 1,
    "status": "online",
    "tags": ["vision"]
  },
  "execution_mode": "ssh_command"
}
```

也可以传入手动设备集合:

```json
{
  "target_filter": {
    "device_ids": [1, 2, 3]
  },
  "execution_mode": "ssh_command"
}
```

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "name": "edge-01",
      "device_sn": "SN-EDGE-001",
      "project_id": "factory-a",
      "group_id": 1,
      "status": "online",
      "ssh_port": 12001,
      "ssh_credential_configured": true,
      "tags": ["vision"],
      "location": "shenzhen"
    }
  ],
  "warnings": []
}
```

说明:

- 预览接口不会写入数据库。
- `execution_mode=ssh_command` 时,若命中设备缺少 SSH 端口或 SSH 凭据,`warnings` 会返回中文提醒。
- 响应不包含设备 SSH 密码、私钥、Token 或其他敏感字段。

### 查询更新任务列表

```http
GET /api/update-tasks
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束/说明 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 |
| `limit` | integer | `50` | 1-200 |
| `status` | string | 无 | 按任务状态筛选 |

响应 `200`:

```json
{
  "total": 1,
  "items": []
}
```

### 查询更新任务详情

```http
GET /api/update-tasks/{task_id}
```

认证:需要。

响应 `200`:`UpdateTask`。

### 执行更新任务

```http
POST /api/update-tasks/{task_id}/execute
```

认证:需要。

响应 `200`:`UpdateTask`。

执行行为由 `execution_mode` 决定:

- `dry_run`:演练模式,不连接设备;待执行设备会标记为 `skipped`,并写入演练说明。
- `ssh_command`:真实 SSH 执行;后端通过设备的 frp SSH 端口连接设备,执行 `command`,并记录每台设备的 `exit_code`、`stdout_summary`、`stderr_summary` 和 `error_message`。

`failure_strategy=continue` 会继续执行后续设备;`pause` 和 `rollback` 会在首个失败后跳过后续待执行设备。本轮 `rollback` 不自动执行回滚命令,只会记录提示。

错误:

- `404`:任务不存在。
- `409`:任务已完成或已取消,不能再次执行。

### 取消更新任务

```http
POST /api/update-tasks/{task_id}/cancel
```

认证:需要。

响应 `200`:`UpdateTask`。

错误:

- `409`:已完成任务不能取消。

### 导出更新任务结果

```http
GET /api/update-tasks/{task_id}/export
```

认证:需要。

响应 `200`: `text/csv`。

导出字段:

| 字段 | 说明 |
| --- | --- |
| `task_id` | 更新任务 ID |
| `task_name` | 更新任务名称 |
| `device_id` | 设备 ID |
| `device_sn` | 设备序列号 |
| `status` | 单设备执行状态 |
| `exit_code` | SSH 命令退出码 |
| `stdout_summary` | 标准输出摘要 |
| `stderr_summary` | 错误输出摘要 |
| `error_message` | 失败原因 |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |

导出内容只包含执行摘要和错误原因,不包含设备 SSH 明文密码。以 `=`、`+`、`-`、`@`、制表符或换行开头的单元格会加前导制表符,降低 CSV 公式注入风险。

### 更新任务进度 WebSocket

```text
WS /api/ws/update-tasks/{task_id}?token=<access_token>
```

认证:查询参数 `token`。

连接成功后服务端发送一次快照并主动关闭:

```json
{
  "type": "task.snapshot",
  "task": {
    "id": 1,
    "name": "升级视觉服务",
    "status": "completed",
    "device_count": 2,
    "devices": []
  }
}
```

错误:

- token 缺失、无效、用户不存在或任务不存在时关闭连接,关闭码为 `1008`。

### 更新任务命令模板

模板只保存命令元数据,不保存设备目标、设备凭据或执行结果。

#### 查询模板列表

```http
GET /api/update-task-templates
```

认证:需要。

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "name": "查看主机名",
      "description": "只读检查",
      "command": "hostname",
      "task_type": "command",
      "default_execution_mode": "dry_run",
      "created_at": "2026-05-19T00:00:00",
      "updated_at": "2026-05-19T00:00:00"
    }
  ]
}
```

#### 创建模板

```http
POST /api/update-task-templates
```

请求体:

```json
{
  "name": "查看主机名",
  "description": "只读检查",
  "command": "hostname",
  "task_type": "command",
  "default_execution_mode": "dry_run"
}
```

响应 `201`:模板对象。

#### 更新模板

```http
PUT /api/update-task-templates/{template_id}
```

请求体字段均可选,支持完整编辑模板名称、说明、命令、任务类型和默认执行模式。

响应 `200`:模板对象。

#### 删除模板

```http
DELETE /api/update-task-templates/{template_id}
```

响应 `204`:无响应体。

## 定时任务接口

### 创建定时任务

```http
POST /api/scheduled-tasks
```

认证:需要。

请求体:

```json
{
  "name": "每日健康检查",
  "task_type": "command",
  "schedule": "cron:0 2 * * *",
  "command": "echo ok",
  "target_filter": {
    "project_id": "factory-a"
  },
  "enabled": true,
  "execution_mode": "dry_run",
  "failure_strategy": "continue",
  "concurrency_limit": 5
}
```

响应 `201`:`ScheduledTask`。

校验规则:

- `schedule` 仅支持 `interval:N` 和 5 位 `cron:` 表达式。
- `execution_mode` 支持 `dry_run` 和 `ssh_command`;只有 `ssh_command` 会连接设备执行真实 SSH 命令。
- `concurrency_limit` 范围为 `1-50`。

`ScheduledTask` 响应会包含 `last_run_at`、`last_status`、`last_error`、`next_run_at` 和 `running`。后台调度器启用时,到期任务会自动生成执行记录。

### 查询定时任务列表

```http
GET /api/scheduled-tasks
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 |
| `limit` | integer | `50` | 1-200 |

响应 `200`:

```json
{
  "total": 1,
  "items": []
}
```

### 更新定时任务

```http
PUT /api/scheduled-tasks/{task_id}
```

认证:需要。

请求体:`ScheduledTask` 的可选字段子集。

响应 `200`:`ScheduledTask`。

### 删除定时任务

```http
DELETE /api/scheduled-tasks/{task_id}
```

认证:需要。

响应 `204`:无响应体。

### 启停定时任务

```http
POST /api/scheduled-tasks/{task_id}/toggle
```

认证:需要。

响应 `200`:`ScheduledTask`,其中 `enabled` 会被取反。

### 手动执行定时任务

```http
POST /api/scheduled-tasks/{task_id}/execute
```

认证:需要。

响应 `200`:

```json
{
  "task_id": 1,
  "status": "success",
  "output_summary": "scheduled task dry-run created update task 7",
  "run_id": 3
}
```

该接口保留兼容入口,会写入一条手动执行记录。命令任务会复用批量更新任务执行链路:`dry_run` 只演练,`ssh_command` 执行真实 SSH 命令。

### 立即执行定时任务

```http
POST /api/scheduled-tasks/{task_id}/run-now
```

认证:需要。

响应 `200` 与 `POST /api/scheduled-tasks/{task_id}/execute` 一致。

### 查询定时任务执行记录

```http
GET /api/scheduled-tasks/{task_id}/runs
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 |
| `limit` | integer | `50` | 1-200 |

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 3,
      "scheduled_task_id": 1,
      "trigger_type": "manual",
      "status": "success",
      "started_at": "2026-05-21T10:00:00",
      "finished_at": "2026-05-21T10:00:01",
      "duration_ms": 1000,
      "output_summary": "scheduled task dry-run created update task 7",
      "error_message": null,
      "created_update_task_id": 7,
      "created_at": "2026-05-21T10:00:00"
    }
  ]
}
```

`trigger_type` 支持 `manual` 和 `scheduled`;`status` 支持 `running`、`success`、`failed` 和 `skipped`。

### 查询定时任务日志

```http
GET /api/scheduled-tasks/{task_id}/logs
```

认证:需要。

响应 `200`:`OperationLogListResponse`。

### 查询调度器状态

```http
GET /api/scheduler/status
```

认证:需要。

响应 `200`:

```json
{
  "enabled": true,
  "running": true,
  "poll_interval_seconds": 30,
  "last_scan_at": "2026-05-21T10:00:00",
  "last_error": null,
  "job_count": 1
}
```

## 监控接口

### 查询监控总览

```http
GET /api/monitoring/overview
```

认证:需要。

响应 `200`:

```json
{
  "total_devices": 10,
  "online_devices": 6,
  "offline_devices": 2,
  "unknown_devices": 2
}
```

## 告警接口

### 查询告警列表

```http
GET /api/alerts?status=open&severity=critical&source_type=metric&limit=50
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 分页偏移 |
| `limit` | integer | `50` | 每页数量,最大 200 |
| `status` | string | 无 | `open`、`acknowledged`、`resolved` |
| `severity` | string | 无 | `warning`、`critical` |
| `source_type` | string | 无 | `device`、`metric`、`scheduled_task`、`update_task` |
| `device_id` | integer | 无 | 按设备筛选 |
| `alert_type` | string | 无 | 按规则类型筛选 |

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "title": "CPU 高负载",
      "message": "设备 edge-01 CPU 94% 超过阈值 85%",
      "severity": "critical",
      "status": "open",
      "source_type": "metric",
      "alert_type": "cpu_high",
      "device_id": 1,
      "scheduled_task_id": null,
      "update_task_id": null,
      "metric_name": "cpu_percent",
      "metric_value": 94,
      "threshold_value": 85,
      "dedupe_key": "metric:cpu_high:1",
      "acknowledged_by_user_id": null,
      "acknowledged_at": null,
      "resolved_at": null,
      "note": null,
      "created_at": "2026-05-25T10:00:00",
      "updated_at": "2026-05-25T10:00:00"
    }
  ]
}
```

### 查询告警摘要

```http
GET /api/alerts/summary
```

认证:需要。

响应 `200`:

```json
{
  "active_count": 1,
  "critical_count": 1,
  "unacknowledged_count": 1,
  "latest_alert_at": "2026-05-25T10:00:00",
  "by_source": {
    "metric": 1
  },
  "by_severity": {
    "critical": 1
  }
}
```

### 确认告警

```http
POST /api/alerts/{alert_id}/acknowledge
Content-Type: application/json
```

认证:需要。

请求体:

```json
{
  "note": "已联系现场确认"
}
```

响应 `200`:`Alert`。该操作会写入操作日志 `alert.acknowledge`。

### 手动恢复告警

```http
POST /api/alerts/{alert_id}/resolve
Content-Type: application/json
```

认证:需要。

请求体:

```json
{
  "note": "现场恢复后手动关闭"
}
```

响应 `200`:`Alert`。该操作会写入操作日志 `alert.resolve`。

### 查询告警规则

```http
GET /api/alert-rules
```

认证:需要。

响应 `200`:

```json
{
  "total": 3,
  "items": [
    {
      "id": 1,
      "rule_type": "cpu_high",
      "enabled": true,
      "severity": "warning",
      "threshold_value": 85,
      "window_minutes": null,
      "created_at": "2026-05-25T09:00:00",
      "updated_at": "2026-05-25T09:00:00"
    }
  ]
}
```

默认规则:

| `rule_type` | 默认含义 |
| --- | --- |
| `device_status` | 设备离线或未知 |
| `cpu_high` | CPU 使用率超过阈值,默认 85 |
| `memory_high` | 内存使用率超过阈值,默认 85 |
| `disk_high` | 磁盘使用率超过阈值,默认 90 |
| `metrics_stale` | 最新指标超过窗口未更新,默认 10 分钟 |
| `scheduled_task_failed` | 定时任务执行失败 |
| `update_task_failed` | 批量更新任务失败或部分失败 |

### 更新告警规则

```http
PUT /api/alert-rules/{rule_id}
Content-Type: application/json
```

认证:需要。

请求体可包含以下字段中的一个或多个:

```json
{
  "enabled": true,
  "severity": "critical",
  "threshold_value": 90,
  "window_minutes": 10
}
```

响应 `200`:`AlertRule`。空请求体或无可更新字段会返回 `422`。

## 日志接口

### 查询操作日志

```http
GET /api/logs
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 约束/说明 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 大于等于 0 |
| `limit` | integer | `50` | 1-200 |
| `action` | string | 无 | 按动作精确筛选 |
| `target_type` | string | 无 | 按目标类型精确筛选 |
| `status` | string | 无 | 按状态精确筛选 |

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "action": "device.create",
      "target_type": "device",
      "target_id": 1,
      "status": "success",
      "detail": "SN001",
      "created_at": "2026-05-12T01:00:00"
    }
  ]
}
```

### 导出操作日志

```http
GET /api/logs/export
```

认证:需要。

查询参数:

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `action` | string | 无 | 按动作精确筛选 |
| `target_type` | string | 无 | 按目标类型精确筛选 |
| `status` | string | 无 | 按状态精确筛选 |

响应 `200`:`text/csv`。

CSV 列:

```text
id,user_id,action,target_type,target_id,status,detail,created_at
```

当前实现最多导出 1000 条记录。

## Wave 8 远程连接补充

### WebSocket 鉴权

设备远程 WebSocket 与更新任务 WebSocket 一样,通过查询参数传递 access token:

```text
/api/ws/devices/{device_id}/ssh?token=<access_token>
/api/ws/devices/{device_id}/vnc?token=<access_token>
```

缺少 token、token 无效、设备不存在或用户不可用时,连接会以 `1008` 关闭。

### Web SSH

`POST /api/devices/{device_id}/remote/ssh` 返回的 `websocket_url` 指向 Web SSH 端点。前端拼接 token 后建立 WebSocket。

浏览器发送:

```json
{"type":"input","data":"echo ok\n"}
{"type":"resize","columns":120,"rows":32}
{"type":"close"}
```

后端返回:

```json
{"type":"status","status":"connected"}
{"type":"output","data":"..."}
{"type":"error","message":"..."}
```

后端使用 `paramiko` 连接设备的 frp SSH 端口。目标主机由 `remote_gateway_host` 配置;凭据来自 `ssh_password`、`ssh_key_filename`、`ssh_key_passphrase` 等配置。

### VNC 代理

`POST /api/devices/{device_id}/remote/vnc` 返回的 `websocket_url` 指向 VNC WebSocket-to-TCP 代理。该端点转发二进制 VNC 数据,目标主机默认复用 `remote_gateway_host`,也可通过 `vnc_gateway_host` 单独配置。前端 noVNC 客户端应连接该 WebSocket。

### 文件后端

文件接口支持两种后端:

- `file_backend=local`:默认开发模式,继续使用本地目录模拟设备侧文件系统。
- `file_backend=sftp`:通过 `paramiko` SFTP 连接设备 frp SSH 端口,执行真实文件列表、上传、下载和删除。

SFTP 模式仍保留路径安全限制:禁止空文件路径、`.`、`..`、路径穿越和根路径删除。

## frps Dashboard 导入

### 预览 frps 代理

```http
POST /api/frps/discover
```

认证:需要。

请求体:

```json
{
  "dashboard_url": "124.70.177.226:7500",
  "username": "admin",
  "password": "admin",
  "ssh_port_start": 12001,
  "ssh_port_end": 17000,
  "vnc_port_start": 17001,
  "vnc_port_end": 22000,
  "project_id": "frps-import",
  "location": "frps"
}
```

行为:

- 后端读取 `http://<dashboard_url>/api/proxy/tcp`。
- 端口在 `ssh_port_start` 到 `ssh_port_end` 内的代理会作为 SSH 代理。
- VNC 端口按偏移匹配,默认 `vnc_port = ssh_port + 5000`。
- 预览接口不会写入数据库。

### 导入 frps 代理

```http
POST /api/frps/import
```

认证:需要。请求体与预览接口相同。

响应:

```json
{
  "total": 2,
  "created": 1,
  "skipped": 1,
  "items": [
    {
      "name": "frps-12008",
      "device_sn": "frps-12008",
      "project_id": "frps-import",
      "ssh_port": 12008,
      "vnc_port": 17008,
      "ssh_proxy_name": "ssh-12008",
      "vnc_proxy_name": "vnc-17008",
      "status": "online",
      "import_status": "created",
      "detail": "设备 1 已导入"
    }
  ]
}
```

导入接口会创建设备记录,并在端口池中预留对应 SSH/VNC 端口。若设备序列号或端口已存在,则跳过,不覆盖已有设备。
## Wave 9 诊断、凭据与 frps 同步补充

### 健康检查

```http
GET /api/health
```

响应新增 `database` 字段:

```json
{
  "status": "ok",
  "service": "edge-platform",
  "version": "0.1.0",
  "database": "ok"
}
```

### 诊断配置

```http
GET /api/diagnostics/config
```

认证:需要 Bearer Token。

该接口只返回非敏感配置摘要,例如 API 前缀、数据库摘要、文件后端、远程网关主机、VNC 网关主机、SSH/VNC 超时时间、默认设备 SSH 用户和安全摘要。接口不得返回密码、Token、私钥内容、passphrase 或凭据加密密钥。

安全摘要示例:

```json
{
  "security": {
    "credential_encryption_configured": true,
    "jwt_secret_configured": true,
    "default_admin_password_in_use": false,
    "default_device_ssh_password_in_use": true,
    "warnings": [
      "设备默认 SSH 密码仍为默认值,请按部署环境调整"
    ]
  }
}
```

`credential_encryption_configured=false` 表示后端未配置 `CREDENTIAL_ENCRYPTION_KEY`,新增设备凭据会按兼容模式保存。配置后,新写入的设备 SSH 密码会以 Fernet 密文保存;旧明文凭据仍兼容读取,避免升级后已有设备失联。

Wave 17 起,诊断响应额外包含治理和运维摘要:

```json
{
  "migration": {
    "current_revision": "20260511_0001_wave1_schema",
    "head_revision": "20260511_0001_wave1_schema",
    "has_pending_migrations": false,
    "last_error": null
  },
  "ssh_host_key": {
    "policy": "auto_add",
    "known_hosts_configured": false,
    "warnings": [
      "SSH 主机密钥策略为 auto_add，生产环境建议配置 known_hosts 并使用 warning 或 reject"
    ]
  },
  "auth_lifetime": {
    "access_expire_minutes": 30,
    "refresh_expire_minutes": 43200,
    "jwt_secret_configured": true
  },
  "database_status": {
    "summary": "sqlite:///platform.db",
    "sqlite_backup_recommended": true
  }
}
```

这些字段只暴露 revision、策略名、有效期和数据库摘要,不返回密码、Token、私钥、known_hosts 内容或密钥材料。

### 设备级 SSH 凭据

设备创建和更新请求支持:

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `ssh_user` | string | `ztl` | 设备 SSH 用户 |
| `ssh_auth_type` | string | `password` | 本轮默认密码模式 |
| `ssh_password` | string/null | `123456` | 写入用字段;本轮直接保存到数据库 |

设备读取响应不返回 `ssh_password`,只返回:

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ssh_user` | string | 当前 SSH 用户 |
| `ssh_auth_type` | string | 凭据类型 |
| `ssh_credential_configured` | boolean | 是否已配置 SSH 密码或密钥 |

Wave 11 起,配置 `CREDENTIAL_ENCRYPTION_KEY` 后,`ssh_password` 写入值会加密保存到数据库字段 `ssh_password_encrypted`。该字段不会通过 API 响应返回。未配置加密密钥时保持兼容模式,并由诊断接口给出 warning。

### frps 同步扩展

`POST /api/frps/discover` 和 `POST /api/frps/import` 请求体新增:

```json
{
  "overwrite_project_location": false
}
```

结果项 `import_status` 支持:

| 状态 | 说明 |
| --- | --- |
| `new` | 平台尚无该设备,可导入 |
| `existing` | 已有同 `device_sn` 的设备 |
| `created` | 导入时新建设备成功 |
| `synced` | 导入时同步已有设备成功 |
| `conflict` | SSH/VNC 端口被其他设备占用 |
| `missing_vnc` | 发现 SSH 代理但未发现对应 VNC 代理 |
| `offline` | frps Dashboard 返回代理非 online |
| `skipped` | 跳过处理 |

响应新增统计字段:

```json
{
  "total": 2,
  "created": 1,
  "synced": 1,
  "skipped": 0,
  "conflicts": 0,
  "items": []
}
```

导入新设备时默认 `ssh_user=ztl`、默认 SSH 密码为 `123456`。同步已有设备时不会覆盖凭据;只有 `overwrite_project_location=true` 时才覆盖项目号和部署位置。

### Postman Collection

仓库内提供:

```text
docs/postman/edge-platform.postman_collection.json
```

使用顺序:健康检查、登录、当前用户、设备列表、frps 预览、监控概览、日志列表。登录和刷新 Token 请求的保存脚本必须放在 Tests 中,不要放在 Pre-request Script 中。

## Wave 10 批量 SSH 命令执行补充

### 创建演练任务

```http
POST /api/update-tasks
```

请求体:

```json
{
  "name": "演练 hostname",
  "task_type": "command",
  "command": "hostname",
  "target_filter": {
    "project_id": "frps-import"
  },
  "execution_mode": "dry_run",
  "failure_strategy": "continue",
  "concurrency_limit": 5
}
```

演练任务执行后不会连接设备,设备结果会标记为 `skipped`。

### 创建真实 SSH 任务

```http
POST /api/update-tasks
```

请求体:

```json
{
  "name": "真实执行 hostname",
  "task_type": "command",
  "command": "hostname",
  "target_filter": {
    "project_id": "frps-import"
  },
  "execution_mode": "ssh_command",
  "failure_strategy": "continue",
  "concurrency_limit": 5
}
```

执行成功后的单设备结果示例:

```json
{
  "device_id": 1,
  "status": "success",
  "exit_code": 0,
  "stdout_summary": "edge-01",
  "stderr_summary": "",
  "error_message": null
}
```

执行失败时 `status` 为 `failed`,并根据失败类型写入 `exit_code`、`stderr_summary` 或 `error_message`。API 响应不会返回设备 SSH 明文密码。

## Wave 12 运维管理闭环补充

### 管理员修改密码

```http
PUT /api/auth/password
Authorization: Bearer <access_token>
Content-Type: application/json
```

请求体:

```json
{
  "old_password": "admin-pass",
  "new_password": "new-admin-pass"
}
```

成功返回 `204 No Content`。前端修改成功后会清理本地 Token,并要求重新登录。

### 分组前端闭环

后端分组接口保持不变:

- `POST /api/groups`
- `GET /api/groups`
- `PUT /api/groups/{group_id}`
- `DELETE /api/groups/{group_id}`

Wave 12 前端已接入创建、编辑、删除和设备数展示。设备创建和编辑请求会提交 `group_id`,设备列表支持按分组过滤本地列表。

### 日志筛选和导出

```http
GET /api/logs?offset=0&limit=50&action=device.create&target_type=device&status=success
```

查询参数:

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `offset` | integer | 分页偏移,默认 0 |
| `limit` | integer | 每页数量,默认 50,最大 200 |
| `action` | string | 可选,按操作名精确筛选 |
| `target_type` | string | 可选,按目标类型精确筛选 |
| `status` | string | 可选,按状态精确筛选 |

```http
GET /api/logs/export?action=device.create&target_type=device&status=success
```

导出返回 `text/csv`,并包含:

- `Content-Disposition: attachment; filename="operation_logs.csv"`
- `X-Content-Type-Options: nosniff`

CSV 导出会对以 `=`、`+`、`-`、`@`、制表符或换行开头的字符串增加前导制表符,降低电子表格公式注入风险。

### 设备同步配置

```http
POST /api/devices/{device_id}/sync-config
Authorization: Bearer <access_token>
```

当前实现返回生成后的 frpc 配置文本,并记录操作日志;前端设备表可直接查看和复制配置。

### 系统诊断页

```http
GET /api/diagnostics/config
Authorization: Bearer <access_token>
```

前端"系统诊断"页展示服务名、版本、API 前缀、数据库摘要、文件后端、远程网关、默认 SSH 用户、`security`、`migration`、`ssh_host_key`、`auth_lifetime` 和 `database_status` 摘要。该接口和页面只展示非敏感摘要,不返回密码、Token、私钥内容、密钥或解密后的设备凭据。

## Wave 17 治理约束

### 枚举字段

以下字段由后端枚举校验,未知值返回 `422`:

| 字段 | 允许值 |
| --- | --- |
| `DeviceCreate.ssh_auth_type` / `DeviceUpdate.ssh_auth_type` | `password`, `key` |
| `DeviceUpdate.status` / `DeviceMetricCreate.status` | `online`, `offline`, `degraded`, `unknown` |
| `UpdateTaskCreate.execution_mode` / 预览请求 `execution_mode` | `dry_run`, `ssh_command` |
| `UpdateTaskCreate.failure_strategy` | `continue`, `pause`, `rollback` |
| `UpdateTaskCreate.task_type` / 定时任务 `task_type` / 更新模板 `task_type` | `command`, `script`, `config`, `health_check` |

### 前端 Token 刷新

前端请求收到 `401` 后会使用本地 refresh token 调用 `POST /api/auth/refresh` 重试一次原请求。刷新成功后会更新本地 access/refresh token;刷新失败、refresh token 缺失或刷新接口返回 `401` 时,前端会清理本地登录态并回到登录页。

## Wave 13 监控指标与仪表盘展示规则

### 上报设备指标

```http
POST /api/devices/{device_id}/metrics
```

认证:需要 Bearer Token。

请求体示例:

```json
{
  "status": "online",
  "cpu_percent": 64,
  "memory_percent": 72,
  "disk_percent": 81
}
```

响应 `201` 返回写入的指标记录。该接口也会同步更新设备当前状态和 `last_seen`。

### 查询设备最新指标

```http
GET /api/devices/{device_id}/metrics?limit=1
```

认证:需要 Bearer Token。

前端 Wave 13 固定按每台设备 `limit=1` 查询最新指标。无指标时返回:

```json
{
  "total": 0,
  "items": []
}
```

### 查询监控总览

```http
GET /api/monitoring/overview
```

认证:需要 Bearer Token。

返回设备总数、在线数、离线数和未知数。前端仪表盘将该接口用于顶部统计卡片,将设备级指标接口用于资源快照和异常设备摘要。

### 前端展示约定

- 无指标设备显示"暂无指标",不得显示 `0%`。
- 指标超过 10 分钟未更新时显示"指标过期"。
- 指标接口返回 401 才视为登录失效;403 表示当前角色无权限,不会清理登录态。
- CPU >= 90% 显示高负载,内存 >= 85% 显示高内存,磁盘 >= 90% 显示磁盘紧张。

## Wave 14 远程连接产品化补充

### 前端连接状态

远程连接页按 SSH 和 VNC 分别维护状态:

| 状态 | 中文展示含义 |
| --- | --- |
| `idle` | 未连接 |
| `connecting` | 正在创建会话或连接 WebSocket |
| `ready` | 会话描述已创建 |
| `connected` | 已连接 |
| `failed` | 连接失败 |
| `disconnected` | 已断开 |

### 错误处理约定

- REST 会话接口和 WebSocket 使用同一个 access token。
- REST 返回 `401` 时,前端视为登录失效并清理 Token;返回 `403` 时只显示无权限提示。
- REST 返回 `400`、`502`、`503`、`504` 或 WebSocket 错误时,前端只在远程连接区域显示中文错误,不退出登录。
- 后端日志记录远程会话创建、连接成功、失败和断开摘要,但不得记录 SSH 密码、Token、私钥、完整终端输入或 VNC 画面内容。

### Postman 使用

Postman Collection 的"Wave 14 远程连接"分组提供创建 SSH/VNC 会话描述的请求。WebSocket 交互需要使用 Postman 的 WebSocket 客户端或浏览器前端手工验证,连接地址格式为:

```text
ws://<host>/api/ws/devices/{{device_id}}/ssh?token={{access_token}}
ws://<host>/api/ws/devices/{{device_id}}/vnc?token={{access_token}}
```

## Wave 19 告警中心与自动恢复规则

### 触发与恢复

- `device_status`:设备更新为 `offline` 或 `unknown` 时触发;设备恢复为 `online` 或 `degraded` 时自动恢复。
- `cpu_high`、`memory_high`、`disk_high`:设备指标上报超过启用规则阈值时触发;后续指标低于阈值时自动恢复。
- `metrics_stale`:调度扫描时发现设备最近指标早于规则窗口时触发;新指标上报后自动恢复。
- `scheduled_task_failed`:定时任务执行记录为 `failed` 时触发;后续同一任务执行成功时自动恢复。
- `update_task_failed`:批量任务状态为 `partial_failed` 或 `canceled` 时触发;后续同一任务完成成功时自动恢复。

### 诊断摘要

`GET /api/diagnostics/config` 的响应新增 `alerts` 字段:

```json
{
  "alerts": {
    "active_count": 1,
    "critical_count": 1,
    "latest_alert_at": "2026-05-25T10:00:00",
    "warnings": ["存在 1 条严重告警"]
  }
}
```

该字段只返回计数、最近时间和风险提示,不返回设备凭据、Token 或敏感配置。

## Wave 20 告警外部通知

本轮只支持 Webhook 通知。Webhook URL 和请求头属于敏感配置,创建或更新时后端必须能读取 `CREDENTIAL_ENCRYPTION_KEY`;未配置时返回 `400`。API 响应只返回脱敏后的 URL 预览、请求头 key 和配置状态,不返回完整 URL、请求头值或加密密文。

### 数据模型

#### AlertNotificationChannel

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 通道 ID |
| `name` | string | 通道名称 |
| `channel_type` | string | 当前固定为 `webhook` |
| `enabled` | boolean | 是否启用 |
| `webhook_url_preview` | string/null | 脱敏 URL 预览 |
| `timeout_seconds` | integer | Webhook 请求超时秒数 |
| `header_keys` | string[] | 已配置请求头 key 列表 |
| `secret_configured` | boolean | 是否已保存敏感配置 |
| `last_test_status` | string/null | 最近测试状态 |
| `last_test_at` | datetime/null | 最近测试时间 |
| `last_error` | string/null | 最近错误摘要 |
| `created_at` / `updated_at` | datetime | 创建和更新时间 |

#### AlertNotificationPolicy

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 策略 ID |
| `name` | string | 策略名称 |
| `enabled` | boolean | 是否启用 |
| `channel_id` | integer | 关联通知通道 ID |
| `min_severity` | string | `critical` 或 `warning` |
| `source_types` | string[] | 可选来源过滤,空数组表示不过滤 |
| `alert_statuses` | string[] | 可选告警状态过滤,空数组表示不过滤 |
| `event_types` | string[] | 通知事件,如 `triggered` |
| `created_at` / `updated_at` | datetime | 创建和更新时间 |

支持事件:

| 事件 | 说明 |
| --- | --- |
| `triggered` | 告警触发 |
| `acknowledged` | 告警被确认 |
| `resolved` | 告警手动恢复 |
| `auto_resolved` | 告警自动恢复 |

#### AlertNotificationDelivery

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 投递记录 ID |
| `alert_id` | integer | 告警 ID |
| `channel_id` | integer | 通道 ID |
| `policy_id` | integer | 策略 ID |
| `event_type` | string | 事件类型 |
| `status` | string | `pending`、`success`、`failed`、`retrying`、`skipped` |
| `attempt_count` | integer | 已尝试次数 |
| `last_attempt_at` | datetime/null | 最近尝试时间 |
| `next_retry_at` | datetime/null | 下次建议重试时间 |
| `response_status_code` | integer/null | Webhook 响应状态码 |
| `response_summary` | string/null | 响应摘要 |
| `error_message` | string/null | 错误原因 |
| `alert_title` / `channel_name` / `policy_name` | string/null | 展示用名称 |

### 查询通知通道

```http
GET /api/alert-notification-channels
```

认证:需要。响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "name": "生产告警 Webhook",
      "channel_type": "webhook",
      "enabled": true,
      "webhook_url_preview": "https://notify.example.com/***",
      "timeout_seconds": 5,
      "header_keys": ["Authorization"],
      "secret_configured": true,
      "last_test_status": "success",
      "last_test_at": "2026-06-01T10:00:00",
      "last_error": null,
      "created_at": "2026-06-01T09:00:00",
      "updated_at": "2026-06-01T10:00:00"
    }
  ]
}
```

### 创建通知通道

```http
POST /api/alert-notification-channels
Content-Type: application/json
```

请求体:

```json
{
  "name": "生产告警 Webhook",
  "channel_type": "webhook",
  "enabled": true,
  "webhook_url": "https://notify.example.com/webhook",
  "headers": {
    "Authorization": "Bearer example-token"
  },
  "timeout_seconds": 5
}
```

响应 `201`:`AlertNotificationChannel`。

错误:

- `400`:未配置 `CREDENTIAL_ENCRYPTION_KEY` 或敏感配置无法加密。
- `422`:URL 非 `http://` / `https://`、名称为空或超时越界。

### 更新通知通道

```http
PUT /api/alert-notification-channels/{channel_id}
Content-Type: application/json
```

请求体可包含 `name`、`enabled`、`webhook_url`、`headers`、`timeout_seconds` 中的一个或多个。更新 `webhook_url` 或 `headers` 时同样要求配置 `CREDENTIAL_ENCRYPTION_KEY`。

### 删除通知通道

```http
DELETE /api/alert-notification-channels/{channel_id}
```

响应 `204`。如果仍有通知策略引用该通道,返回 `409`;需要先删除策略再删除通道。

### 测试通知通道

```http
POST /api/alert-notification-channels/{channel_id}/test
```

后端会向通道 Webhook 发送一条测试 payload,并更新 `last_test_status`、`last_test_at` 和 `last_error`。响应 `200`:`AlertNotificationChannel`。

### 查询通知策略

```http
GET /api/alert-notification-policies
```

响应 `200`:

```json
{
  "total": 1,
  "items": [
    {
      "id": 1,
      "name": "严重告警触发通知",
      "enabled": true,
      "channel_id": 1,
      "min_severity": "critical",
      "source_types": [],
      "alert_statuses": ["open"],
      "event_types": ["triggered"],
      "created_at": "2026-06-01T09:00:00",
      "updated_at": "2026-06-01T09:00:00"
    }
  ]
}
```

### 创建通知策略

```http
POST /api/alert-notification-policies
Content-Type: application/json
```

请求体:

```json
{
  "name": "严重告警触发通知",
  "enabled": true,
  "channel_id": 1,
  "min_severity": "critical",
  "source_types": [],
  "alert_statuses": ["open"],
  "event_types": ["triggered"]
}
```

响应 `201`:`AlertNotificationPolicy`。默认建议只订阅 `critical` + `triggered`。

### 更新和删除通知策略

```http
PUT /api/alert-notification-policies/{policy_id}
DELETE /api/alert-notification-policies/{policy_id}
```

更新请求体可包含创建字段的任意子集。删除成功返回 `204`。

### 查询投递记录

```http
GET /api/alert-notification-deliveries?status=failed&limit=50
```

查询参数:

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `offset` | integer | `0` | 分页偏移 |
| `limit` | integer | `50` | 分页大小,最大 200 |
| `status` | string | 无 | 按投递状态筛选 |
| `channel_id` | integer | 无 | 按通道筛选 |
| `alert_id` | integer | 无 | 按告警筛选 |

### 重试投递

```http
POST /api/alert-notification-deliveries/{delivery_id}/retry
```

响应 `200`:`AlertNotificationDelivery`。成功后状态变为 `success`;失败会更新错误原因和重试建议时间。

### 查询通知摘要

```http
GET /api/alert-notification-summary
```

响应 `200`:

```json
{
  "enabled_channel_count": 1,
  "enabled_policy_count": 1,
  "failed_delivery_count": 0,
  "retrying_delivery_count": 0,
  "last_delivery_at": "2026-06-01T10:00:00",
  "warnings": []
}
```

### 诊断摘要扩展

`GET /api/diagnostics/config` 新增 `notifications` 字段:

```json
{
  "notifications": {
    "enabled_channel_count": 1,
    "enabled_policy_count": 1,
    "failed_delivery_count": 0,
    "retrying_delivery_count": 0,
    "warnings": []
  }
}
```

该字段只返回计数和风险提示,不返回 Webhook URL、请求头值或密钥材料。

## Wave 21 用户角色与会话审计

### 权限模型

当前内置角色:

| 角色 | 说明 |
| --- | --- |
| `admin` | 管理员,可执行用户管理、删除、真实 SSH 执行和告警通知配置等高风险操作 |
| `operator` | 运维人员,可查看数据、创建/编辑设备、执行演练任务,不能进入用户管理或执行真实 SSH 操作 |

受限操作返回:

```json
{
  "detail": "当前账号无权限执行该操作"
}
```

### UserRead

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 用户 ID |
| `username` | string | 用户名 |
| `role` | string | `admin` 或 `operator` |
| `is_active` | boolean | 是否启用 |
| `last_login_at` | datetime/null | 最近登录时间 |
| `last_login_ip` | string/null | 最近登录 IP |
| `password_changed_at` | datetime/null | 最近密码更新时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 查询用户

```http
GET /api/users?offset=0&limit=50
```

认证:仅 `admin`。

响应 `200`:

```json
{
  "total": 2,
  "items": [
    {
      "id": 1,
      "username": "admin",
      "role": "admin",
      "is_active": true,
      "last_login_at": "2026-06-04T10:00:00",
      "last_login_ip": "127.0.0.1",
      "password_changed_at": "2026-06-04T09:00:00",
      "created_at": "2026-05-11T00:00:00",
      "updated_at": "2026-06-04T10:00:00"
    }
  ]
}
```

### 创建用户

```http
POST /api/users
Content-Type: application/json
```

认证:仅 `admin`。

请求体:

```json
{
  "username": "operator",
  "password": "password123",
  "role": "operator",
  "is_active": true
}
```

响应 `201`:`UserRead`。

错误:

- `409`:用户名已存在。
- `422`:密码少于 8 位、角色不合法或请求体校验失败。

### 更新用户

```http
PUT /api/users/{user_id}
Content-Type: application/json
```

认证:仅 `admin`。

请求体可包含:

```json
{
  "role": "operator",
  "is_active": true
}
```

响应 `200`:`UserRead`。

错误:

- `404`:用户不存在。
- `409`:会导致没有启用管理员,例如降级或停用最后一个管理员。

### 重置密码

```http
POST /api/users/{user_id}/reset-password
Content-Type: application/json
```

认证:仅 `admin`。

请求体:

```json
{
  "new_password": "new-password123"
}
```

响应 `200`:`UserRead`。

### 启停和删除用户

```http
POST /api/users/{user_id}/toggle
DELETE /api/users/{user_id}
```

`toggle` 请求体:

```json
{
  "is_active": false
}
```

`DELETE` 为停用账号,不硬删除用户记录;成功返回 `204 No Content`。停用最后一个启用管理员会返回 `409`。

### 认证审计

以下动作会写入操作日志:

- `auth.login`:登录成功或失败,失败也会记录用户名和来源 IP 摘要。
- `auth.refresh`:刷新 token 成功、无效 token 或用户停用。
- `auth.password_change`:修改密码成功或失败。
- `auth.forbidden`:已认证用户访问无权限接口。
- `user.create`、`user.update`、`user.reset_password`、`user.toggle`、`user.disable`:用户管理操作。

日志不记录明文密码、token 或敏感凭据。

### 诊断摘要扩展

`GET /api/diagnostics/config` 新增 `users` 字段:

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

该字段只返回计数和风险提示,不返回密码哈希或 token。

## 设备项目与边缘功能生命周期（第一阶段）

本阶段将项目、边缘功能、功能版本、硬件变体和设备硬件规格升级为正式实体。所有写接口仅管理员可用，已认证操作员可只读查询。

### 项目与设备归属

```http
GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}
PUT  /api/projects/{project_id}
```

设备的 `project_id` 现在是项目实体的整数主键，也允许为 `null`（待分配池），不再接受自由文本项目号。迁移 `20260717_0007` 会主动清空旧的字符串项目关系，但保留设备、端口、凭据和历史任务数据。

设备新增字段包括稳定的 `device_uuid`、预期/实际上报硬件规格、预留设备角色及测试设备标记。当前支持的硬件规格为 `rk3568-4g-debian11` 和 `rk3588-8g-debian11`。

### 功能、版本与硬件变体

```http
GET  /api/functions
POST /api/functions
PUT  /api/functions/{function_id}
GET  /api/functions/{function_id}/releases
POST /api/functions/{function_id}/releases
PUT  /api/functions/{function_id}/releases/{release_id}
GET  /api/functions/{function_id}/releases/{release_id}/variants
POST /api/functions/{function_id}/releases/{release_id}/variants
PUT  /api/functions/{function_id}/releases/{release_id}/variants/{variant_id}
POST /api/functions/{function_id}/releases/{release_id}/publish
```

草稿版本及其变体可以修改；发布前至少要有一个硬件变体。已发布版本和变体不可修改，项目只能选择已发布版本。

### 项目功能配置

```http
GET  /api/projects/{project_id}/functions
PUT  /api/projects/{project_id}/functions/{function_id}
POST /api/projects/{project_id}/functions/{function_id}/pending-uninstall
GET  /api/hardware-profiles
```

单个设备只归属一个项目，一个项目可以启用多个独立功能。项目功能移除先进入 `pending_uninstall`，为后续经人工确认的卸载计划保留状态。

## 单设备初始化闭环（第二阶段）

创建设备后，平台自动建立第 1 代初始化包草稿。管理员需要配置平台 HTTPS 地址、CA、FRP 服务端和固定 FRPC 制品哈希后才能生成可下载包。

### 初始化包管理

```http
GET  /api/devices/{device_id}/bootstrap-package
POST /api/devices/{device_id}/bootstrap-package
GET  /api/devices/{device_id}/bootstrap-package/{package_id}/download
```

- `GET`：已认证用户查看最新草稿或包状态，不返回注册令牌、SSH/VNC 密码或加密字段。
- `POST`：仅管理员生成或重新生成；配置不完整时保持 `draft` 并返回 `validation_errors`。
- `download`：仅管理员下载 `ready` 状态的单设备 ZIP。

设备的 SSH/VNC 端口、SSH 账号、SSH 密码或期望硬件规格变化时，当前包会变为 `invalidated`，并自动建立下一代草稿。已失效、已认领或配置快照变化的包不能下载。

ZIP 包包含 `install.sh`、CA 公钥、FRPC 配置、硬件采集脚本、`edge-deploy`、FRPC/x0vncserver/governor systemd 单元。脚本只面向 Debian 11，不更换软件源、不执行系统全量升级、不自动重启。

### 设备一次性认领

```http
POST /api/device-registration/claim
```

该接口由设备携带一次性令牌调用，不使用管理员 JWT。请求示例:

```json
{
  "token": "<one-time-token>",
  "device_uuid": "<platform-device-uuid>",
  "device_sn": "SN-001",
  "machine_id": "<machine-id>",
  "mac_addresses": ["02:00:00:00:00:01"],
  "hardware": {
    "soc": "rk3588",
    "memory_mb": 7800,
    "os_version": "debian11"
  },
  "ssh_ready": true,
  "vnc_ready": false,
  "bootstrap_status": "ready"
}
```

只有 `bootstrap_status=ready` 且 `ssh_ready=true` 才完成认领并永久消费令牌。失败或 `reboot_required` 上报只更新初始化状态，允许修复后幂等重试。VNC 失败不阻止认领，设备进入 `ready_vnc_pending`。实际规格与期望规格不一致时进入 `hardware_mismatch`，后续业务部署必须阻断。
