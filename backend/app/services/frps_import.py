from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.schemas.frps import FrpsDiscoveredDevice, FrpsImportRequest, FrpsImportResponse
from app.services.port_pool import PortPoolExhaustedError, PortPoolService


class FrpsDashboardError(RuntimeError):
    pass


class FrpsImportService:
    def __init__(self, settings: Settings, dashboard_client: Any | None = None) -> None:
        self.settings = settings
        self.dashboard_client = dashboard_client
        self.port_pool = PortPoolService(settings)

    def discover(self, payload: FrpsImportRequest) -> FrpsImportResponse:
        proxies = self._fetch_tcp_proxies(payload)
        items = self._map_proxies(payload, proxies)
        return FrpsImportResponse(total=len(items), created=0, skipped=0, items=items)

    def import_devices(self, session: Session, payload: FrpsImportRequest) -> FrpsImportResponse:
        proxies = self._fetch_tcp_proxies(payload)
        items = self._map_proxies(payload, proxies)
        created = 0
        skipped = 0
        for item in items:
            existing = session.scalar(
                select(Device).where(
                    or_(
                        Device.device_sn == item.device_sn,
                        Device.ssh_port == item.ssh_port,
                        Device.vnc_port == item.vnc_port if item.vnc_port is not None else Device.id == -1,
                    )
                )
            )
            if existing is not None:
                item.import_status = "skipped"
                item.detail = "设备序列号或端口已存在"
                skipped += 1
                continue

            device = Device(
                name=item.name,
                device_sn=item.device_sn,
                project_id=item.project_id,
                location=payload.location,
                ssh_user="root",
                ssh_port=item.ssh_port,
                vnc_port=item.vnc_port,
                tags=["frps-import", item.ssh_proxy_name] + ([item.vnc_proxy_name] if item.vnc_proxy_name else []),
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
                item.import_status = "skipped"
                item.detail = str(exc)
                skipped += 1
                continue
            item.import_status = "created"
            item.detail = f"设备 {device.id} 已导入"
            created += 1
        return FrpsImportResponse(total=len(items), created=created, skipped=skipped, items=items)

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
                    detail=None if vnc_proxy is not None else f"未发现对应 VNC 端口 {vnc_port}",
                )
            )
        return items

    def _remote_port(self, proxy: dict[str, Any]) -> int | None:
        conf = proxy.get("conf") if isinstance(proxy.get("conf"), dict) else {}
        port = conf.get("remotePort") or conf.get("remote_port") or proxy.get("remotePort") or proxy.get("remote_port")
        try:
            return int(port)
        except (TypeError, ValueError):
            return None
