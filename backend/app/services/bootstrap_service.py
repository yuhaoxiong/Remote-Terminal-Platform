from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import secrets
import shlex
from string import ascii_letters, digits
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.bootstrap import DeviceBootstrapPackage
from app.models.device import Device
from app.models.lifecycle import HardwareProfile
from app.schemas.bootstrap import DeviceRegistrationClaim
from app.services.encryption import EncryptionService


class BootstrapNotFoundError(ValueError):
    pass


class BootstrapConflictError(ValueError):
    pass


class BootstrapTokenError(ValueError):
    pass


class BootstrapPackageService:
    CONNECTION_FIELDS = {"ssh_port", "vnc_port", "ssh_user", "ssh_password", "expected_profile_id"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.encryption = EncryptionService(settings)

    def ensure_initial_draft(self, session: Session, device: Device) -> DeviceBootstrapPackage:
        existing = session.scalar(
            select(DeviceBootstrapPackage).where(DeviceBootstrapPackage.device_id == device.id).limit(1)
        )
        if existing is not None:
            return existing
        package = DeviceBootstrapPackage(
            device_id=device.id,
            generation=1,
            status="draft",
            validation_errors=["尚未生成初始化包"],
        )
        session.add(package)
        device.initialization_status = "draft"
        device.bootstrap_generation = 1
        session.flush()
        return package

    def latest(self, session: Session, device_id: int) -> DeviceBootstrapPackage:
        package = session.scalar(
            select(DeviceBootstrapPackage)
            .where(DeviceBootstrapPackage.device_id == device_id)
            .order_by(DeviceBootstrapPackage.generation.desc())
            .limit(1)
        )
        if package is None:
            raise BootstrapNotFoundError(f"设备初始化包不存在：{device_id}")
        return package

    def prepare(self, session: Session, device: Device, *, created_by: int) -> DeviceBootstrapPackage:
        try:
            latest = self.latest(session, device.id)
        except BootstrapNotFoundError:
            latest = self.ensure_initial_draft(session, device)

        if latest.status != "draft":
            if latest.status == "ready":
                self._invalidate(latest)
            generation = (session.scalar(
                select(func.max(DeviceBootstrapPackage.generation)).where(
                    DeviceBootstrapPackage.device_id == device.id
                )
            ) or 0) + 1
            latest = DeviceBootstrapPackage(device_id=device.id, generation=generation, status="draft")
            session.add(latest)

        errors = self._validation_errors(device)
        latest.created_by = created_by
        latest.validation_errors = errors or None
        latest.token_digest = None
        latest.token_encrypted = None
        latest.vnc_password_encrypted = None
        latest.ca_sha256 = None
        latest.config_hash = None
        device.bootstrap_generation = latest.generation
        if errors:
            latest.status = "draft"
            device.initialization_status = "draft"
            session.flush()
            session.refresh(latest)
            return latest

        token = secrets.token_urlsafe(32)
        vnc_password = "".join(secrets.choice(ascii_letters + digits) for _ in range(8))
        ca_certificate = self._ca_certificate()
        ssh_password = self.encryption.decrypt_optional(device.ssh_password_encrypted)
        device.ssh_password_encrypted = self.encryption.encrypt_optional(ssh_password)
        latest.status = "ready"
        latest.token_digest = self._digest(token)
        latest.token_encrypted = self.encryption.encrypt_optional(token)
        latest.vnc_password_encrypted = self.encryption.encrypt_optional(vnc_password)
        device.vnc_password_encrypted = self.encryption.encrypt_optional(vnc_password)
        latest.ca_sha256 = self._digest(ca_certificate)
        latest.config_hash = self._config_hash(device, ca_certificate)
        device.initialization_status = "package_ready"
        session.flush()
        session.refresh(latest)
        return latest

    def invalidate_for_device_change(self, session: Session, device: Device) -> DeviceBootstrapPackage:
        for package in session.scalars(
            select(DeviceBootstrapPackage).where(
                DeviceBootstrapPackage.device_id == device.id,
                DeviceBootstrapPackage.status.in_(("draft", "ready")),
            )
        ):
            self._invalidate(package)
        generation = (session.scalar(
            select(func.max(DeviceBootstrapPackage.generation)).where(
                DeviceBootstrapPackage.device_id == device.id
            )
        ) or 0) + 1
        package = DeviceBootstrapPackage(
            device_id=device.id,
            generation=generation,
            status="draft",
            validation_errors=["设备连接信息已变更，请重新生成初始化包"],
        )
        session.add(package)
        device.bootstrap_generation = generation
        device.initialization_status = "package_stale"
        session.flush()
        return package

    def build_archive(self, session: Session, device: Device, package_id: int) -> tuple[bytes, str]:
        package = session.get(DeviceBootstrapPackage, package_id)
        if package is None or package.device_id != device.id:
            raise BootstrapNotFoundError(f"设备初始化包不存在：{package_id}")
        if package.status != "ready":
            raise BootstrapConflictError("只有已就绪且未认领的初始化包可以下载")
        ca_certificate = self._ca_certificate()
        if package.config_hash != self._config_hash(device, ca_certificate):
            self._invalidate(package)
            device.initialization_status = "package_stale"
            session.flush()
            raise BootstrapConflictError("平台或设备连接配置已变化，请重新生成初始化包")
        token = self.encryption.decrypt_optional(package.token_encrypted)
        vnc_password = self.encryption.decrypt_optional(package.vnc_password_encrypted)
        ssh_password = self.encryption.decrypt_optional(device.ssh_password_encrypted)
        if not token or not vnc_password or not ssh_password:
            raise BootstrapConflictError("初始化包敏感配置不可用，请重新生成")

        files = self._archive_files(device, token, vnc_password, ssh_password, ca_certificate)
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content.replace("\r\n", "\n").replace("\r", "\n"))
        package.downloaded_at = datetime.now(timezone.utc)
        session.flush()
        return output.getvalue(), f"edge-bootstrap-{device.device_sn}-g{package.generation}.zip"

    def claim(
        self,
        session: Session,
        payload: DeviceRegistrationClaim,
    ) -> tuple[Device, DeviceBootstrapPackage, bool, bool | None]:
        package = session.scalar(
            select(DeviceBootstrapPackage).where(DeviceBootstrapPackage.token_digest == self._digest(payload.token))
        )
        if package is None:
            raise BootstrapTokenError("注册令牌无效")
        if package.status == "claimed":
            raise BootstrapConflictError("注册令牌已经使用")
        if package.status != "ready":
            raise BootstrapConflictError("注册令牌已失效")
        device = session.get(Device, package.device_id)
        if device is None:
            raise BootstrapNotFoundError("注册令牌对应设备不存在")
        if payload.device_uuid != device.device_uuid or payload.device_sn != device.device_sn:
            raise BootstrapConflictError("设备身份与初始化包不匹配")

        device.machine_id_hash = self._digest(payload.machine_id) if payload.machine_id else None
        device.mac_fingerprint_hash = self._digest("\n".join(payload.mac_addresses)) if payload.mac_addresses else None
        profile = self._resolve_profile(
            session,
            payload.hardware.soc,
            payload.hardware.memory_mb,
            payload.hardware.os_version,
        )
        device.actual_profile_id = profile.id if profile else None
        device.hardware_model = payload.hardware.soc
        device.os_version = payload.hardware.os_version

        if payload.bootstrap_status != "ready" or not payload.ssh_ready:
            device.initialization_status = (
                "reboot_required" if payload.bootstrap_status == "reboot_required" else "failed"
            )
            device.vnc_status = "ready" if payload.vnc_ready else "pending"
            session.flush()
            return device, package, False, None

        hardware_matches = None
        if device.expected_profile_id is not None:
            hardware_matches = device.expected_profile_id == device.actual_profile_id
        if hardware_matches is False:
            device.initialization_status = "hardware_mismatch"
        elif payload.vnc_ready:
            device.initialization_status = "ready"
        else:
            device.initialization_status = "ready_vnc_pending"
        device.vnc_status = "ready" if payload.vnc_ready else "pending"
        device.status = "online"
        device.last_seen = datetime.now(timezone.utc)
        device.initialized_at = datetime.now(timezone.utc)
        package.status = "claimed"
        package.claimed_at = datetime.now(timezone.utc)
        package.token_encrypted = None
        package.vnc_password_encrypted = None
        session.flush()
        return device, package, True, hardware_matches

    def _validation_errors(self, device: Device) -> list[str]:
        errors: list[str] = []
        if not self.encryption.enabled:
            errors.append("未配置 CREDENTIAL_ENCRYPTION_KEY，不能安全保存初始化令牌")
        if not self.settings.bootstrap_platform_url or not self.settings.bootstrap_platform_url.startswith("https://"):
            errors.append("BOOTSTRAP_PLATFORM_URL 必须是 HTTPS 地址")
        try:
            ca_certificate = self._ca_certificate().strip()
            if not ca_certificate:
                errors.append("平台 CA 证书为空")
            elif "BEGIN CERTIFICATE" not in ca_certificate:
                errors.append("平台 CA 配置不是 PEM 证书")
            elif "PRIVATE KEY" in ca_certificate:
                errors.append("初始化包只能携带 CA 公钥证书，禁止包含私钥")
        except BootstrapConflictError as exc:
            errors.append(str(exc))
        if not self.settings.bootstrap_frp_server_addr:
            errors.append("未配置 BOOTSTRAP_FRP_SERVER_ADDR")
        if not self.settings.bootstrap_frpc_download_url or not self.settings.bootstrap_frpc_download_url.startswith("https://"):
            errors.append("BOOTSTRAP_FRPC_DOWNLOAD_URL 必须是 HTTPS 地址")
        digest = (self.settings.bootstrap_frpc_sha256 or "").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            errors.append("BOOTSTRAP_FRPC_SHA256 必须是 64 位小写十六进制")
        if device.ssh_port is None or device.vnc_port is None:
            errors.append("设备必须分配 SSH 和 VNC 远程端口")
        if device.ssh_auth_type != "password" or not device.ssh_password_encrypted:
            errors.append("当前初始化器要求设备配置 SSH 密码认证")
        if re.fullmatch(r"[a-z_][a-z0-9_-]{0,62}[$]?", device.ssh_user) is None:
            errors.append("SSH 用户名必须是安全的 Unix 用户名")
        return errors

    def _ca_certificate(self) -> str:
        if self.settings.bootstrap_ca_certificate:
            return self.settings.bootstrap_ca_certificate
        if self.settings.bootstrap_ca_cert_path:
            path = Path(self.settings.bootstrap_ca_cert_path)
            try:
                return path.read_text(encoding="utf-8")
            except OSError as exc:
                raise BootstrapConflictError(f"无法读取平台 CA 证书：{path}") from exc
        raise BootstrapConflictError("未配置 BOOTSTRAP_CA_CERTIFICATE 或 BOOTSTRAP_CA_CERT_PATH")

    def _resolve_profile(
        self,
        session: Session,
        soc: str,
        memory_mb: int,
        os_version: str,
    ) -> HardwareProfile | None:
        normalized_soc = soc.lower().replace("rockchip,", "")
        normalized_os = os_version.lower().replace(" ", "")
        for profile in session.scalars(select(HardwareProfile).where(HardwareProfile.active.is_(True))):
            memory_tolerance = max(512, int(profile.memory_mb * 0.15))
            if (
                profile.soc.lower() in normalized_soc
                and abs(profile.memory_mb - memory_mb) <= memory_tolerance
                and (profile.os_version.lower() in normalized_os or "debian11" in normalized_os)
            ):
                return profile
        return None

    def _config_hash(self, device: Device, ca_certificate: str) -> str:
        snapshot = {
            "device_uuid": device.device_uuid,
            "device_sn": device.device_sn,
            "ssh_port": device.ssh_port,
            "vnc_port": device.vnc_port,
            "ssh_user": device.ssh_user,
            "ssh_secret_digest": self._digest(device.ssh_password_encrypted or ""),
            "expected_profile_id": device.expected_profile_id,
            "platform_url": self.settings.bootstrap_platform_url,
            "api_prefix": self.settings.api_prefix,
            "ca_sha256": self._digest(ca_certificate),
            "frp_addr": self.settings.bootstrap_frp_server_addr,
            "frp_port": self.settings.bootstrap_frp_server_port,
            "frp_token_digest": self._digest(self.settings.bootstrap_frp_auth_token or ""),
            "frpc_url": self.settings.bootstrap_frpc_download_url,
            "frpc_sha256": self.settings.bootstrap_frpc_sha256,
        }
        return self._digest(json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")))

    def _archive_files(
        self,
        device: Device,
        token: str,
        vnc_password: str,
        ssh_password: str,
        ca_certificate: str,
    ) -> dict[str, str]:
        values = {
            "PLATFORM_URL": self.settings.bootstrap_platform_url or "",
            "REGISTRATION_URL": (
                f"{(self.settings.bootstrap_platform_url or '').rstrip('/')}"
                f"{self.settings.api_prefix}/device-registration/claim"
            ),
            "DEVICE_UUID": device.device_uuid,
            "DEVICE_SN": device.device_sn,
            "REGISTRATION_TOKEN": token,
            "SSH_USER": device.ssh_user,
            "SSH_PASSWORD": ssh_password,
            "VNC_PASSWORD": vnc_password,
            "FRPC_DOWNLOAD_URL": self.settings.bootstrap_frpc_download_url or "",
            "FRPC_SHA256": self.settings.bootstrap_frpc_sha256 or "",
            "CA_SHA256": self._digest(ca_certificate),
        }
        env_content = "\n".join(f"{key}={shlex.quote(value)}" for key, value in values.items()) + "\n"
        artifact_url_prefix = (
            f"{(self.settings.bootstrap_platform_url or '').rstrip('/')}"
            f"{self.settings.api_prefix}/deployment-executions/"
        )
        edge_deploy_script = EDGE_DEPLOY_SCRIPT.replace(
            "__ARTIFACT_URL_PREFIX__",
            shlex.quote(artifact_url_prefix),
        )
        return {
            "README.txt": README_TEXT,
            "install.sh": INSTALL_SCRIPT,
            "config/device.env": env_content,
            "config/frpc.toml": self._frpc_config(device),
            "config/platform-ca.crt": ca_certificate.rstrip() + "\n",
            "bin/edge-deploy": edge_deploy_script,
            "scripts/hardware_collect.sh": HARDWARE_COLLECT_SCRIPT,
            "scripts/register.sh": REGISTER_SCRIPT,
            "systemd/frpc.service": FRPC_SERVICE,
            "systemd/x0vncserver.service": X0VNC_SERVICE,
            "systemd/edge-governor.service": GOVERNOR_SERVICE,
            "scripts/set_governor.sh": GOVERNOR_SCRIPT,
        }

    def _frpc_config(self, device: Device) -> str:
        token_lines = []
        if self.settings.bootstrap_frp_auth_token:
            token_lines = ["auth.method = \"token\"", f"auth.token = {json.dumps(self.settings.bootstrap_frp_auth_token)}", ""]
        return "\n".join(
            [
                f"serverAddr = {json.dumps(self.settings.bootstrap_frp_server_addr)}",
                f"serverPort = {self.settings.bootstrap_frp_server_port}",
                "",
                *token_lines,
                "[[proxies]]",
                f"name = {json.dumps(device.device_sn + '-ssh')}",
                'type = "tcp"',
                'localIP = "127.0.0.1"',
                "localPort = 22",
                f"remotePort = {device.ssh_port}",
                "",
                "[[proxies]]",
                f"name = {json.dumps(device.device_sn + '-vnc')}",
                'type = "tcp"',
                'localIP = "127.0.0.1"',
                "localPort = 5901",
                f"remotePort = {device.vnc_port}",
                "",
            ]
        )

    def _invalidate(self, package: DeviceBootstrapPackage) -> None:
        package.status = "invalidated"
        package.invalidated_at = datetime.now(timezone.utc)
        package.token_encrypted = None
        package.vnc_password_encrypted = None

    @staticmethod
    def _digest(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()


README_TEXT = """Edge Platform 单设备初始化包

1. 将整个目录复制到目标 Debian 11 设备。
2. 使用 root 执行：bash install.sh
3. 脚本不会自动重启设备；退出码 20 表示需要人工重启后再次执行。
4. 初始化包只属于本设备，不要复制给其他设备。
"""

INSTALL_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT_DIR/config/device.env"

if [[ "${EUID}" -ne 0 ]]; then
  echo "failed: please run as root" >&2
  exit 1
fi

if [[ ! "$SSH_USER" =~ ^[a-z_][a-z0-9_-]{0,62}[$]?$ ]]; then
  echo "failed: unsafe SSH user name" >&2
  exit 1
fi

if ! grep -q '^VERSION_ID="\?11' /etc/os-release; then
  echo "failed: Debian 11 is required" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server sudo curl ca-certificates jq tar gzip iproute2 tigervnc-scraping-server python3

id -u "$SSH_USER" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$SSH_USER"
printf '%s:%s\n' "$SSH_USER" "$SSH_PASSWORD" | chpasswd

install -d -m 0700 /etc/edge-platform /etc/frp /opt/edge-platform/bootstrap
install -m 0600 "$ROOT_DIR/config/device.env" /etc/edge-platform/device.env
install -m 0600 "$ROOT_DIR/config/frpc.toml" /etc/frp/frpc.toml
install -m 0644 "$ROOT_DIR/config/platform-ca.crt" /usr/local/share/ca-certificates/edge-platform-ca.crt
update-ca-certificates
actual_ca_sha="$(sha256sum /usr/local/share/ca-certificates/edge-platform-ca.crt | awk '{print $1}')"
[[ "$actual_ca_sha" == "$CA_SHA256" ]] || { echo "failed: CA fingerprint mismatch" >&2; exit 1; }

tmp_archive="$(mktemp)"
tmp_extract="$(mktemp -d)"
trap 'rm -f "$tmp_archive"; rm -rf "$tmp_extract"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 "$FRPC_DOWNLOAD_URL" --output "$tmp_archive"
echo "$FRPC_SHA256  $tmp_archive" | sha256sum --check --status || { echo "failed: frpc sha256 mismatch" >&2; exit 1; }
tar -xzf "$tmp_archive" -C "$tmp_extract"
frpc_binary="$(find "$tmp_extract" -type f -name frpc -print -quit)"
[[ -n "$frpc_binary" ]] || { echo "failed: frpc binary not found" >&2; exit 1; }
install -m 0755 "$frpc_binary" /usr/local/bin/frpc

install -m 0755 "$ROOT_DIR/bin/edge-deploy" /usr/local/bin/edge-deploy
sudoers_file=/etc/sudoers.d/edge-platform-deploy
printf '%s ALL=(root) NOPASSWD: /usr/local/bin/edge-deploy apply --stdin\n' "$SSH_USER" >"$sudoers_file"
chmod 0440 "$sudoers_file"
visudo -cf "$sudoers_file" >/dev/null
install -m 0755 "$ROOT_DIR/scripts/hardware_collect.sh" /opt/edge-platform/bootstrap/hardware_collect.sh
install -m 0755 "$ROOT_DIR/scripts/register.sh" /opt/edge-platform/bootstrap/register.sh
install -m 0755 "$ROOT_DIR/scripts/set_governor.sh" /opt/edge-platform/bootstrap/set_governor.sh
install -m 0644 "$ROOT_DIR/systemd/frpc.service" /etc/systemd/system/frpc.service
install -m 0644 "$ROOT_DIR/systemd/x0vncserver.service" /etc/systemd/system/x0vncserver.service
install -m 0644 "$ROOT_DIR/systemd/edge-governor.service" /etc/systemd/system/edge-governor.service
vncpasswd_binary="$(command -v tigervncpasswd || command -v vncpasswd || true)"
[[ -n "$vncpasswd_binary" ]] || { echo "failed: VNC password utility not found" >&2; exit 1; }
printf '%s\n' "$VNC_PASSWORD" | "$vncpasswd_binary" -f > /etc/edge-platform/vnc.pass
chmod 0600 /etc/edge-platform/vnc.pass

systemctl daemon-reload
systemctl enable --now ssh
systemctl enable --now frpc
systemctl enable --now edge-governor.service
vnc_ready=true
if ! systemctl enable --now x0vncserver.service; then
  vnc_ready=false
fi
ssh_ready=false
if systemctl is-active --quiet ssh && ss -ltn | grep -qE '[:.]22[[:space:]]'; then
  ssh_ready=true
fi

bootstrap_status=ready
if [[ "$ssh_ready" != true ]]; then
  bootstrap_status=failed
elif [[ -f /var/run/reboot-required ]]; then
  bootstrap_status=reboot_required
fi

set +e
/opt/edge-platform/bootstrap/register.sh "$bootstrap_status" "$ssh_ready" "$vnc_ready"
register_result=$?
set -e
if [[ $register_result -ne 0 ]]; then
  echo "failed: platform registration failed" >&2
  exit 1
fi
if [[ "$bootstrap_status" == reboot_required ]]; then
  echo "reboot_required"
  exit 20
fi
if [[ "$bootstrap_status" == failed ]]; then
  echo "failed"
  exit 1
fi
echo "ready"
'''

HARDWARE_COLLECT_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
compatible="$(tr '\0' ',' </proc/device-tree/compatible 2>/dev/null || true)"
soc=unknown
[[ "$compatible" == *rk3568* ]] && soc=rk3568
[[ "$compatible" == *rk3588* ]] && soc=rk3588
memory_mb="$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 ))"
os_version="$(. /etc/os-release; printf 'debian%s' "${VERSION_ID:-unknown}")"
machine_id="$(cat /etc/machine-id 2>/dev/null || true)"
mapfile -t macs < <(find /sys/class/net -mindepth 1 -maxdepth 1 ! -name lo -exec sh -c 'cat "$1/address"' _ {}/address \; 2>/dev/null | sort -u)
mac_json="$(printf '%s\n' "${macs[@]}" | jq -R . | jq -s .)"
jq -n --arg soc "$soc" --argjson memory_mb "$memory_mb" --arg os_version "$os_version" --arg machine_id "$machine_id" --argjson mac_addresses "$mac_json" \
  '{soc:$soc,memory_mb:$memory_mb,os_version:$os_version,machine_id:$machine_id,mac_addresses:$mac_addresses}'
'''

REGISTER_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
source /etc/edge-platform/device.env
bootstrap_status="${1:-failed}"
ssh_ready="${2:-false}"
vnc_ready="${3:-false}"
hardware="$(/opt/edge-platform/bootstrap/hardware_collect.sh)"
payload="$(jq -n \
  --arg token "$REGISTRATION_TOKEN" \
  --arg device_uuid "$DEVICE_UUID" \
  --arg device_sn "$DEVICE_SN" \
  --arg machine_id "$(jq -r '.machine_id' <<<"$hardware")" \
  --argjson mac_addresses "$(jq '.mac_addresses' <<<"$hardware")" \
  --argjson hardware "$(jq '{soc,memory_mb,os_version}' <<<"$hardware")" \
  --argjson ssh_ready "$ssh_ready" \
  --argjson vnc_ready "$vnc_ready" \
  --arg bootstrap_status "$bootstrap_status" \
  '{token:$token,device_uuid:$device_uuid,device_sn:$device_sn,machine_id:$machine_id,mac_addresses:$mac_addresses,hardware:$hardware,ssh_ready:$ssh_ready,vnc_ready:$vnc_ready,bootstrap_status:$bootstrap_status}')"
curl --fail-with-body --silent --show-error --cacert /usr/local/share/ca-certificates/edge-platform-ca.crt \
  -H 'Content-Type: application/json' \
  --data "$payload" \
  "$REGISTRATION_URL"
'''

EDGE_DEPLOY_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
readonly DEPLOYMENT_ARTIFACT_URL_PREFIX=__ARTIFACT_URL_PREFIX__

apply_function() {
  [[ "${EUID}" -eq 0 ]] || { echo "edge-deploy apply must run as root" >&2; return 2; }
  [[ $# -eq 1 ]] || { echo "usage: edge-deploy apply <base64-descriptor>" >&2; return 2; }
  local descriptor
  descriptor="$(printf '%s' "$1" | base64 --decode)" || { echo "invalid deployment descriptor" >&2; return 2; }
  jq -e '
    .schema_version == 1 and
    (.execution_id | type == "string" and test("^[A-Za-z0-9-]{1,64}$")) and
    (.execution_item_id | type == "number") and
    (.function_code | type == "string" and test("^[a-z0-9][a-z0-9-]{1,63}$")) and
    (.version | type == "string" and test("^[A-Za-z0-9._+-]{1,64}$")) and
    (.artifact_url | type == "string" and startswith("https://")) and
    (.artifact_token | type == "string" and length > 20) and
    (.artifact_sha256 | type == "string" and test("^[a-f0-9]{64}$")) and
    (.deployment_fingerprint | type == "string" and test("^[a-f0-9]{64}$")) and
    (.config | type == "object") and
    (.rollback_on_failure | type == "boolean") and
    (.ca_cert_path | type == "string" and length > 0)
  ' <<<"$descriptor" >/dev/null || { echo "invalid deployment descriptor fields" >&2; return 2; }

  local execution_id execution_item_id function_code version artifact_url artifact_token artifact_sha256 deployment_fingerprint rollback_on_failure ca_cert_path
  execution_id="$(jq -r '.execution_id' <<<"$descriptor")"
  execution_item_id="$(jq -r '.execution_item_id' <<<"$descriptor")"
  function_code="$(jq -r '.function_code' <<<"$descriptor")"
  version="$(jq -r '.version' <<<"$descriptor")"
  artifact_url="$(jq -r '.artifact_url' <<<"$descriptor")"
  artifact_token="$(jq -r '.artifact_token' <<<"$descriptor")"
  artifact_sha256="$(jq -r '.artifact_sha256' <<<"$descriptor")"
  deployment_fingerprint="$(jq -r '.deployment_fingerprint' <<<"$descriptor")"
  rollback_on_failure="$(jq -r '.rollback_on_failure' <<<"$descriptor")"
  ca_cert_path="$(jq -r '.ca_cert_path' <<<"$descriptor")"
  local expected_artifact_url
  expected_artifact_url="${DEPLOYMENT_ARTIFACT_URL_PREFIX}${execution_id}/items/${execution_item_id}/artifact"
  [[ "$artifact_url" == "$expected_artifact_url" ]] || {
    echo "artifact URL does not match platform execution" >&2
    return 2
  }
  [[ "$ca_cert_path" == /usr/local/share/ca-certificates/edge-platform-ca.crt ]] || {
    echo "platform CA path is not allowed" >&2
    return 2
  }
  [[ -r "$ca_cert_path" ]] || { echo "platform CA certificate is not readable" >&2; return 2; }

  local state_root cache_root state_dir result_file curl_config="" extract_dir=""
  state_root="${EDGE_DEPLOY_STATE_ROOT:-/var/lib/edge-platform/deployments}"
  cache_root="${EDGE_DEPLOY_CACHE_ROOT:-/var/cache/edge-platform/artifacts}"
  state_dir="$state_root/$execution_id"
  result_file="$state_dir/$function_code.json"
  install -d -m 0700 "$state_dir" "$cache_root"
  trap '[[ -z "${curl_config:-}" ]] || rm -f "$curl_config"; [[ -z "${extract_dir:-}" ]] || rm -rf "$extract_dir"' RETURN
  if [[ -f "$result_file" ]]; then
    [[ "$(jq -r '.deployment_fingerprint // empty' "$result_file")" == "$deployment_fingerprint" ]] || {
      echo "execution id already exists with a different descriptor" >&2
      return 2
    }
    cat "$result_file"
    [[ "$(jq -r '.status' "$result_file")" == "succeeded" ]]
    return
  fi

  local archive_path partial_path
  archive_path="$cache_root/$artifact_sha256.tar.gz"
  partial_path="$archive_path.part"
  if [[ -f "$archive_path" ]] && ! echo "$artifact_sha256  $archive_path" | sha256sum --check --status; then
    rm -f "$archive_path"
  fi
  if [[ ! -f "$archive_path" ]]; then
    curl_config="$(mktemp "$state_dir/.curl-config.XXXXXX")"
    chmod 0600 "$curl_config"
    printf 'header = "Authorization: Bearer %s"\n' "$artifact_token" >"$curl_config"
    curl --fail-with-body --silent --show-error --location --retry 3 --retry-all-errors \
      --proto '=https' --tlsv1.2 --cacert "$ca_cert_path" \
      --config "$curl_config" \
      --continue-at - --output "$partial_path" "$artifact_url"
    rm -f "$curl_config"
    curl_config=""
    echo "$artifact_sha256  $partial_path" | sha256sum --check --status || {
      rm -f "$partial_path"
      echo "artifact sha256 mismatch" >&2
      return 1
    }
    mv -f "$partial_path" "$archive_path"
  fi

  local package_root config_path
  extract_dir="$(mktemp -d)"
  package_root="$(python3 - "$archive_path" "$extract_dir" <<'PY'
import os
import sys
import tarfile
from pathlib import PurePosixPath

archive_path, destination = sys.argv[1:]
with tarfile.open(archive_path, mode="r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 10_000:
        raise SystemExit("too many archive members")
    if sum(member.size for member in members if member.isfile()) > 5 * 1024 * 1024 * 1024:
        raise SystemExit("archive is too large after extraction")
    roots = set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk() or member.isdev():
            raise SystemExit(f"unsafe archive member: {member.name}")
        parts = [part for part in path.parts if part not in {"", "."}]
        if parts:
            roots.add(parts[0])
    if len(roots) != 1:
        raise SystemExit("archive must contain exactly one root directory")
    archive.extractall(destination)
    print(os.path.join(destination, roots.pop()))
PY
)" || { echo "artifact safe extraction failed" >&2; return 1; }
  config_path="$state_dir/$function_code-config.json"
  jq -c '.config' <<<"$descriptor" >"$config_path"
  chmod 0600 "$config_path"

  export EDGE_DEPLOY_EXECUTION_ID="$execution_id"
  export EDGE_FUNCTION_CODE="$function_code"
  export EDGE_FUNCTION_VERSION="$version"
  export EDGE_PACKAGE_ROOT="$package_root"
  export EDGE_ARTIFACT_PATH="$archive_path"
  export EDGE_DEPLOY_CONFIG_JSON="$config_path"

  local step output exit_code status failure_step="" failure_message="" changed=false
  local step_results='{}'
  local steps
  steps=(preflight install configure start healthcheck)
  for step in "${steps[@]}"; do
    local script_path="$package_root/scripts/$step.sh"
    if [[ ! -x "$script_path" ]]; then
      failure_step="$step"
      failure_message="missing executable lifecycle script: $step"
      break
    fi
    set +e
    output="$(cd "$package_root" && "$script_path")"
    exit_code=$?
    set -e
    if ! jq -e 'type == "object" and .schema_version == 1' <<<"$output" >/dev/null 2>&1; then
      failure_step="$step"
      failure_message="$step returned invalid JSON"
      break
    fi
    step_results="$(jq --arg step "$step" --argjson result "$output" '. + {($step): $result}' <<<"$step_results")"
    status="$(jq -r '.status // empty' <<<"$output")"
    if [[ "$step" == healthcheck ]]; then
      [[ $exit_code -eq 0 && "$status" == healthy ]] || {
        failure_step="$step"
        failure_message="healthcheck did not report healthy"
        break
      }
    else
      [[ "$(jq -r '.changed // false' <<<"$output")" == true ]] && changed=true
      [[ $exit_code -eq 0 && "$status" == succeeded ]] || {
        failure_step="$step"
        failure_message="$step failed"
        break
      }
    fi
  done

  local rollback_performed=false rollback_output rollback_exit=0
  if [[ -n "$failure_step" ]]; then
    if [[ "$rollback_on_failure" == true && "$failure_step" != preflight ]]; then
      set +e
      rollback_output="$(cd "$package_root" && "$package_root/scripts/rollback.sh")"
      rollback_exit=$?
      set -e
      if [[ $rollback_exit -eq 0 ]] && jq -e '.schema_version == 1 and .status == "succeeded"' <<<"$rollback_output" >/dev/null 2>&1; then
        rollback_performed=true
      else
        failure_message="$failure_message; rollback failed"
      fi
      if jq -e 'type == "object"' <<<"$rollback_output" >/dev/null 2>&1; then
        step_results="$(jq --argjson result "$rollback_output" '. + {rollback: $result}' <<<"$step_results")"
      fi
    fi
    output="$(jq -n \
      --arg execution_id "$execution_id" --arg function_code "$function_code" \
      --arg message "$failure_message" --arg deployment_fingerprint "$deployment_fingerprint" \
      --argjson changed "$changed" --argjson rollback_performed "$rollback_performed" \
      --argjson steps "$step_results" \
      '{schema_version:1,execution_id:$execution_id,function_code:$function_code,status:"failed",changed:$changed,message:$message,rollback_performed:$rollback_performed,deployment_fingerprint:$deployment_fingerprint,steps:$steps}')"
    printf '%s\n' "$output" >"$result_file.tmp"
    mv -f "$result_file.tmp" "$result_file"
    cat "$result_file"
    return 1
  fi

  output="$(jq -n \
    --arg execution_id "$execution_id" --arg function_code "$function_code" \
    --arg deployment_fingerprint "$deployment_fingerprint" --argjson changed "$changed" --argjson steps "$step_results" \
    '{schema_version:1,execution_id:$execution_id,function_code:$function_code,status:"succeeded",changed:$changed,message:"deployment completed",rollback_performed:false,deployment_fingerprint:$deployment_fingerprint,steps:$steps}')"
  printf '%s\n' "$output" >"$result_file.tmp"
  mv -f "$result_file.tmp" "$result_file"
  cat "$result_file"
}

case "${1:-help}" in
  hardware) exec /opt/edge-platform/bootstrap/hardware_collect.sh ;;
  register) shift; exec /opt/edge-platform/bootstrap/register.sh "$@" ;;
  health) systemctl is-active ssh frpc ;;
  apply)
    shift
    if [[ "${1:-}" == --stdin ]]; then
      IFS= read -r descriptor_input
      apply_function "$descriptor_input"
    else
      apply_function "$@"
    fi
    ;;
  *) echo "usage: edge-deploy {hardware|register|health|apply}" >&2; exit 2 ;;
esac
'''

GOVERNOR_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
for governor in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do
  [[ -w "$governor" ]] && printf performance > "$governor" || true
done
'''

FRPC_SERVICE = """[Unit]
Description=Edge Platform FRP Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frpc -c /etc/frp/frpc.toml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

X0VNC_SERVICE = """[Unit]
Description=Share local desktop with x0vncserver
After=graphical.target

[Service]
Type=simple
ExecStart=/usr/bin/x0vncserver -display :0 -rfbauth /etc/edge-platform/vnc.pass -rfbport 5901 -AlwaysShared=1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
"""

GOVERNOR_SERVICE = """[Unit]
Description=Set edge device CPU governor
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/opt/edge-platform/bootstrap/set_governor.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
