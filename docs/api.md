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
| `403` | 未提供 Bearer token 时由 `HTTPBearer` 返回 |
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
| `ssh_user` | string | 否 | 默认 `root`,1-64 字符 | SSH 用户 |
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
  "username": "admin"
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

响应 `201`:`DeviceRead`。创建时会自动分配 `ssh_port` 和 `vnc_port`。

错误:

- `409`:`device_sn` 重复或端口池耗尽。
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

请求体:`DeviceCreate` 的可选字段子集,额外支持 `status`。

响应 `200`:`DeviceRead`。

错误:

- `404`:设备不存在。
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
  "proxy_url": "/novnc/vnc.html?device_id=1&port=10500"
}
```

返回会话描述后,前端 noVNC 客户端连接:

```text
/api/ws/devices/{device_id}/vnc?token=<access_token>
```

该 WebSocket 转发二进制 VNC 数据,目标为 `vnc_gateway_host` 和设备 `vnc_port`。当前前端只支持内嵌连接、断开和浏览器全屏,不支持剪贴板同步、文件拖拽或远程分辨率高级控制。

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
| `path` | string | `/` | 远端目录路径 |

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

- `400`:路径包含 `.`、`..` 或逃逸设备存储目录。
- `404`:设备不存在。

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
  "enabled": true
}
```

响应 `201`:`ScheduledTask`。

校验规则:

- `schedule` 必须以 `cron:` 或 `interval:` 开头。

当前实现只保存定时任务配置,不包含后台调度器自动触发。

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
  "output_summary": "simulated scheduled task execution: echo ok"
}
```

当前实现为模拟执行,只记录一条 `scheduled_task.execute` 操作日志。

### 查询定时任务日志

```http
GET /api/scheduled-tasks/{task_id}/logs
```

认证:需要。

响应 `200`:`OperationLogListResponse`。

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

前端"系统诊断"页展示服务名、版本、API 前缀、数据库摘要、文件后端、远程网关、默认 SSH 用户和 `security` 摘要。该接口和页面只展示非敏感摘要,不返回密码、Token、私钥内容、密钥或解密后的设备凭据。

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
- 指标接口返回 401/403 才视为登录失效;单台设备指标读取失败只显示"指标加载失败"。
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
- REST 返回 `401` 或 `403` 时,前端视为登录失效并清理 Token。
- REST 返回 `400`、`502`、`503`、`504` 或 WebSocket 错误时,前端只在远程连接区域显示中文错误,不退出登录。
- 后端日志记录远程会话创建、连接成功、失败和断开摘要,但不得记录 SSH 密码、Token、私钥、完整终端输入或 VNC 画面内容。

### Postman 使用

Postman Collection 的"Wave 14 远程连接"分组提供创建 SSH/VNC 会话描述的请求。WebSocket 交互需要使用 Postman 的 WebSocket 客户端或浏览器前端手工验证,连接地址格式为:

```text
ws://<host>/api/ws/devices/{{device_id}}/ssh?token={{access_token}}
ws://<host>/api/ws/devices/{{device_id}}/vnc?token={{access_token}}
```
