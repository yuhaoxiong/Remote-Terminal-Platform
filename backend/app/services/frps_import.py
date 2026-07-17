from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.lifecycle import Project
from app.schemas.frps import FrpsDiscoveredDevice, FrpsImportRequest, FrpsImportResponse
from app.services.encryption import EncryptionService
from app.services.port_pool import PortPoolExhaustedError, PortPoolService


class FrpsDashboardError(RuntimeError):
    pass


class FrpsProjectError(ValueError):
    pass


class FrpsImportService:
    def __init__(self, settings: Settings, dashboard_client: Any | None = None) -> None:
        self.settings = settings
        self.dashboard_client = dashboard_client
        self.port_pool = PortPoolService(settings)
        self.encryption = EncryptionService(settings)

    def discover(self, session: Session, payload: FrpsImportRequest) -> FrpsImportResponse:
        self._validate_project(session, payload.project_id)
        proxies = self._fetch_tcp_proxies(payload)
        items = self._classify_items(session, self._map_proxies(payload, proxies))
        return self._response(items, created=0, synced=0)

    def import_devices(self, session: Session, payload: FrpsImportRequest) -> FrpsImportResponse:
        self._validate_project(session, payload.project_id)
        proxies = self._fetch_tcp_proxies(payload)
        items = self._classify_items(session, self._map_proxies(payload, proxies))
        created = 0
        synced = 0
        for item in items:
            if item.import_status == "conflict":
                continue

            existing = self._existing_device(session, item)
            if existing is not None:
                self._sync_existing_device(existing, item, payload)
                item.import_status = "synced"
                item.existing_device_id = existing.id
                item.detail = f"已同步设备 {existing.id}"
                synced += 1
                continue

            device = Device(
                name=item.name,
                device_sn=item.device_sn,
                project_id=item.project_id,
                location=payload.location,
                ssh_user=self.settings.default_device_ssh_user,
                ssh_auth_type="password",
                ssh_password_encrypted=self.encryption.encrypt_optional(self.settings.default_device_ssh_password),
                ssh_port=item.ssh_port,
                vnc_port=item.vnc_port,
                tags=self._tags_for_item(item),
                status=item.status,
                description="Imported from frps dashboard",
            )
            session.add(device)
            session.flush()
            try:
                self.port_pool.reserve(session, "ssh", item.ssh_port, device.id)
                if item.vnc_port is not None:
                    self.port_pool.reserve(session, "vnc", item.vnc_port, device.id)
            except PortPoolExhaustedError as exc:
                session.delete(device)
                session.flush()
                item.import_status = "conflict"
                item.detail = str(exc)
                continue
            item.import_status = "created"
            item.existing_device_id = device.id
            item.detail = f"已导入设备 {device.id}"
            created += 1
        return self._response(items, created=created, synced=synced)

    def _fetch_tcp_proxies(self, payload: FrpsImportRequest) -> list[dict[str, Any]]:
        if self.dashboard_client is not None:
            return self.dashboard_client.fetch_tcp_proxies(payload)

        base_url = payload.dashboard_url
        if not base_url.startswith(("http://", "https://")):
            base_url = f"http://{base_url}"
        try:
            response = httpx.get(
                f"{base_url.rstrip('/')}/api/proxy/tcp",
                auth=(payload.username, payload.password),
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FrpsDashboardError(f"无法读取 frps Dashboard: {exc}") from exc
        data = response.json()
        proxies = data.get("proxies")
        if not isinstance(proxies, list):
            raise FrpsDashboardError("frps Dashboard 返回格式不包含 proxies")
        return proxies

    def _validate_project(self, session: Session, project_id: int | None) -> None:
        if project_id is None:
            return
        project = session.get(Project, project_id)
        if project is None or project.status != "active":
            raise FrpsProjectError(f"项目不存在或不可分配：{project_id}")

    def _map_proxies(self, payload: FrpsImportRequest, proxies: list[dict[str, Any]]) -> list[FrpsDiscoveredDevice]:
        ssh_by_port: dict[int, dict[str, Any]] = {}
        vnc_by_port: dict[int, dict[str, Any]] = {}
        for proxy in proxies:
            port = self._remote_port(proxy)
            if port is None:
                continue
            if payload.ssh_port_start <= port <= payload.ssh_port_end:
                ssh_by_port[port] = proxy
            elif payload.vnc_port_start <= port <= payload.vnc_port_end:
                vnc_by_port[port] = proxy

        items: list[FrpsDiscoveredDevice] = []
        port_offset = payload.vnc_port_start - payload.ssh_port_start
        for ssh_port in sorted(ssh_by_port):
            ssh_proxy = ssh_by_port[ssh_port]
            vnc_port = ssh_port + port_offset
            vnc_proxy = vnc_by_port.get(vnc_port)
            status = "online" if str(ssh_proxy.get("status", "")).lower() == "online" else "offline"
            import_status = "new"
            detail = None
            if status != "online":
                import_status = "offline"
                detail = "frps 代理离线"
            elif vnc_proxy is None:
                import_status = "missing_vnc"
                detail = f"未发现对应 VNC 端口 {vnc_port}"
            items.append(
                FrpsDiscoveredDevice(
                    name=f"frps-{ssh_port}",
                    device_sn=f"frps-{ssh_port}",
                    project_id=payload.project_id,
                    ssh_port=ssh_port,
                    vnc_port=vnc_port if vnc_proxy is not None else None,
                    ssh_proxy_name=str(ssh_proxy.get("name") or f"ssh-{ssh_port}"),
                    vnc_proxy_name=str(vnc_proxy.get("name")) if vnc_proxy is not None else None,
                    status=status,
                    import_status=import_status,
                    detail=detail,
                )
            )
        return items

    def _classify_items(self, session: Session, items: list[FrpsDiscoveredDevice]) -> list[FrpsDiscoveredDevice]:
        for item in items:
            existing = self._existing_device(session, item)
            if existing is not None:
                item.import_status = "existing"
                item.existing_device_id = existing.id
                item.detail = f"设备已存在: {existing.id}"
                continue
            conflict = self._conflicting_device(session, item)
            if conflict is not None:
                item.import_status = "conflict"
                item.existing_device_id = conflict.id
                item.detail = f"端口已被设备 {conflict.id} 占用"
        return items

    def _existing_device(self, session: Session, item: FrpsDiscoveredDevice) -> Device | None:
        return session.scalar(select(Device).where(Device.device_sn == item.device_sn))

    def _conflicting_device(self, session: Session, item: FrpsDiscoveredDevice) -> Device | None:
        conditions = [Device.ssh_port == item.ssh_port]
        if item.vnc_port is not None:
            conditions.append(Device.vnc_port == item.vnc_port)
        return session.scalar(select(Device).where(or_(*conditions)))

    def _sync_existing_device(self, device: Device, item: FrpsDiscoveredDevice, payload: FrpsImportRequest) -> None:
        device.status = item.status
        device.tags = self._tags_for_item(item)
        if payload.overwrite_project_location:
            device.project_id = item.project_id
            device.location = payload.location

    def _tags_for_item(self, item: FrpsDiscoveredDevice) -> list[str]:
        return ["frps-import", item.ssh_proxy_name] + ([item.vnc_proxy_name] if item.vnc_proxy_name else [])

    def _response(self, items: list[FrpsDiscoveredDevice], *, created: int, synced: int) -> FrpsImportResponse:
        skipped_statuses = {"existing", "missing_vnc", "offline", "skipped"}
        return FrpsImportResponse(
            total=len(items),
            created=created,
            synced=synced,
            skipped=sum(1 for item in items if item.import_status in skipped_statuses),
            conflicts=sum(1 for item in items if item.import_status == "conflict"),
            items=items,
        )

    def _remote_port(self, proxy: dict[str, Any]) -> int | None:
        conf = proxy.get("conf") if isinstance(proxy.get("conf"), dict) else {}
        port = conf.get("remotePort") or conf.get("remote_port") or proxy.get("remotePort") or proxy.get("remote_port")
        try:
            return int(port)
        except (TypeError, ValueError):
            return None
