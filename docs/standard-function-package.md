# 标准功能包契约（Schema 1）

标准功能包是平台部署到边缘设备的不可变预构建制品。平台不构建算法源码，也不接收识别事件或现场图片。

## 文件格式

上传文件必须是 `.tar.gz`，归档内只能有一个顶层目录：

```text
<function>-<version>-<hardware-profile>/
├── manifest.yaml
├── artifacts/
│   └── <预构建程序、模型或资源>
├── config/
│   ├── default.yaml
│   └── collect-schema.json
├── scripts/
│   ├── preflight.sh
│   ├── install.sh
│   ├── configure.sh
│   ├── start.sh
│   ├── healthcheck.sh
│   ├── collect.sh
│   ├── rollback.sh
│   └── uninstall.sh
└── systemd/
    └── service.template
```

所有生命周期脚本必须具有可执行权限，不得包含符号链接、硬链接、设备文件、绝对路径、`..` 路径或重复路径。`artifacts/` 内至少包含一个文件。

## manifest.yaml

```yaml
schema_version: 1
function_code: outside-rubbish-bag
version: 0.1.0
hardware_profile: rk3588-8g-debian11
runtime: python-venv-systemd
signature: null
key_id: null
```

- `function_code`、`version` 和 `hardware_profile` 必须与平台中选择的功能、版本和硬件规格完全一致。
- 当前只接受 `python-venv-systemd` 运行时。
- `signature` 和 `key_id` 为后续 Ed25519 签名预留，当前发布门槛为平台仓库文件存在、大小一致和 SHA-256 一致。
- JSON Schema 见 [function-manifest.schema.json](schemas/function-manifest.schema.json)。

## 配置与生命周期规则

- `config/default.yaml` 必须是 YAML 对象，只在首次安装时作为默认配置；升级不得覆盖 `/etc/edge-apps/<function>` 中的现场调试配置。
- `config/collect-schema.json` 必须是 JSON 对象，只描述允许只读采集的字段。
- 生命周期脚本必须非交互、可重复执行，并使用退出码 `0` 表示成功。
- `healthcheck.sh` 输出必须满足 [healthcheck.schema.json](schemas/healthcheck.schema.json)。
- 其他生命周期脚本的标准输出应满足 [lifecycle-result.schema.json](schemas/lifecycle-result.schema.json)。

## 平台上传与发布

1. 管理员创建功能和草稿版本。
2. 在版本行点击“上传包”，选择硬件规格和 `.tar.gz` 文件。
3. 平台校验归档并自动计算大小和 SHA-256。同一草稿版本、同一硬件规格可重复上传，后一次原子替换前一次。
4. 发布时平台重新校验本地文件大小和 SHA-256。手工登记的 URI 或丢失的文件不能发布。
5. 发布后版本、变体和制品均不可修改。

默认上传上限为 1 GiB，解压后上限为 5 GiB，单包最多 10,000 个归档成员。
