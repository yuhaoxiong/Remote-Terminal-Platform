from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.lifecycle import (
    DeploymentExecution,
    DeploymentExecutionItem,
    DeploymentPlan,
    DeploymentPlanItem,
    FunctionRelease,
    FunctionVariant,
    DeviceReleaseOverride,
    Project,
    ProjectFunction,
)
from app.services.artifact_service import ArtifactService, ArtifactStorageError


class DeploymentNotFoundError(LookupError):
    pass


class DeploymentConflictError(ValueError):
    pass


class DeploymentPlanService:
    READY_INITIALIZATION_STATUSES = {"ready", "ready_vnc_pending"}

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(
        self,
        session: Session,
        *,
        project_id: int,
        device_ids: list[int],
        created_by: int,
    ) -> tuple[DeploymentPlan, list[DeploymentPlanItem]]:
        project = session.get(Project, project_id)
        if project is None:
            raise DeploymentNotFoundError(f"项目不存在：{project_id}")
        if project.status != "active":
            raise DeploymentConflictError("归档项目不能创建部署计划")
        unique_device_ids = sorted(dict.fromkeys(device_ids))
        if len(unique_device_ids) != len(device_ids):
            raise DeploymentConflictError("部署计划不能包含重复设备")

        assignments = list(
            session.scalars(
                select(ProjectFunction)
                .where(ProjectFunction.project_id == project_id, ProjectFunction.status == "active")
                .order_by(ProjectFunction.function_id)
            )
        )
        if not assignments:
            raise DeploymentConflictError("项目尚未配置可部署功能")

        devices = [session.get(Device, device_id) for device_id in unique_device_ids]
        if any(device is None for device in devices):
            raise DeploymentNotFoundError("部署目标中存在无效设备")

        now = datetime.now(timezone.utc)
        item_snapshots: list[dict] = []
        prepared_items: list[dict] = []
        for device in devices:
            assert device is not None
            self._require_deployable_device(device, project_id)
            for assignment in assignments:
                release, override = self._resolve_release(session, device, assignment, now)
                variant = session.scalar(
                    select(FunctionVariant).where(
                        FunctionVariant.release_id == release.id,
                        FunctionVariant.hardware_profile_id == device.actual_profile_id,
                        FunctionVariant.status == "published",
                    )
                )
                if variant is None:
                    raise DeploymentConflictError(
                        f"功能 {assignment.function_id} 缺少设备 {device.device_sn} 对应的已发布硬件变体"
                    )
                try:
                    ArtifactService(self.settings).get_download(
                        session,
                        function_id=assignment.function_id,
                        release_id=release.id,
                        variant_id=variant.id,
                    )
                except ArtifactStorageError as exc:
                    raise DeploymentConflictError(f"设备 {device.device_sn} 的功能包文件不存在") from exc

                config_snapshot = assignment.config_json or {}
                config_hash = self._hash(config_snapshot)
                preflight = {
                    "ready": True,
                    "device_status": device.status,
                    "initialization_status": device.initialization_status,
                    "hardware_profile_id": device.actual_profile_id,
                    "ssh_port": device.ssh_port,
                    "release_source": "device_override" if override is not None else "project_default",
                    "override_id": override.id if override is not None else None,
                    "override_reason": override.reason if override is not None else None,
                    "override_expires_at": override.expires_at.isoformat() if override is not None else None,
                    "checks": [
                        {"name": "device_online", "status": "passed"},
                        {"name": "initialization_ready", "status": "passed"},
                        {"name": "hardware_matches", "status": "passed"},
                        {"name": "ssh_ready", "status": "passed"},
                        {"name": "artifact_available", "status": "passed"},
                    ],
                }
                prepared = {
                    "device_id": device.id,
                    "function_id": assignment.function_id,
                    "release_id": release.id,
                    "variant_id": variant.id,
                    "config_snapshot": config_snapshot,
                    "config_hash": config_hash,
                    "artifact_sha256": variant.artifact_sha256,
                    "preflight_json": preflight,
                    "status": "ready",
                }
                prepared_items.append(prepared)
                item_snapshots.append(
                    {
                        "device_id": device.id,
                        "function_id": assignment.function_id,
                        "release_id": release.id,
                        "variant_id": variant.id,
                        "config_hash": config_hash,
                        "artifact_sha256": variant.artifact_sha256,
                        "device_status": device.status,
                        "initialization_status": device.initialization_status,
                        "actual_profile_id": device.actual_profile_id,
                        "release_source": "device_override" if override is not None else "project_default",
                        "override_id": override.id if override is not None else None,
                        "override_expires_at": override.expires_at.isoformat() if override is not None else None,
                    }
                )

        plan = DeploymentPlan(
            project_id=project_id,
            status="ready",
            snapshot_hash=self._hash(item_snapshots),
            expires_at=now + timedelta(hours=24),
            created_by=created_by,
        )
        session.add(plan)
        session.flush()
        items = [DeploymentPlanItem(plan_id=plan.id, **prepared) for prepared in prepared_items]
        session.add_all(items)
        session.flush()
        for item in items:
            session.refresh(item)
        session.refresh(plan)
        return plan, items

    def get(self, session: Session, plan_id: int) -> tuple[DeploymentPlan, list[DeploymentPlanItem]]:
        plan = session.get(DeploymentPlan, plan_id)
        if plan is None:
            raise DeploymentNotFoundError(f"部署计划不存在：{plan_id}")
        items = list(
            session.scalars(
                select(DeploymentPlanItem)
                .where(DeploymentPlanItem.plan_id == plan_id)
                .order_by(DeploymentPlanItem.device_id, DeploymentPlanItem.function_id)
            )
        )
        return plan, items

    def set_override(
        self,
        session: Session,
        *,
        device_id: int,
        function_id: int,
        release_id: int,
        reason: str,
        expires_at: datetime,
        created_by: int,
    ) -> DeviceReleaseOverride:
        device = session.get(Device, device_id)
        if device is None:
            raise DeploymentNotFoundError(f"设备不存在：{device_id}")
        if device.project_id is None:
            raise DeploymentConflictError("未分配项目的设备不能设置版本覆盖")
        assignment = session.scalar(
            select(ProjectFunction).where(
                ProjectFunction.project_id == device.project_id,
                ProjectFunction.function_id == function_id,
                ProjectFunction.status == "active",
            )
        )
        if assignment is None:
            raise DeploymentConflictError("设备所属项目尚未启用该功能")
        release = session.get(FunctionRelease, release_id)
        if release is None or release.function_id != function_id or release.status != "published":
            raise DeploymentConflictError("覆盖版本必须是该功能的已发布版本")
        normalized_expiry = self._as_utc(expires_at)
        if normalized_expiry <= datetime.now(timezone.utc):
            raise DeploymentConflictError("版本覆盖到期时间必须晚于当前时间")
        override = session.scalar(
            select(DeviceReleaseOverride).where(
                DeviceReleaseOverride.device_id == device_id,
                DeviceReleaseOverride.function_id == function_id,
            )
        )
        if override is None:
            override = DeviceReleaseOverride(
                device_id=device_id,
                function_id=function_id,
                release_id=release_id,
                reason=reason,
                expires_at=expires_at,
                created_by=created_by,
            )
            session.add(override)
        else:
            override.release_id = release_id
            override.reason = reason
            override.expires_at = expires_at
            override.active = True
            override.created_by = created_by
        session.flush()
        session.refresh(override)
        return override

    def validate_for_confirmation(
        self,
        session: Session,
        plan: DeploymentPlan,
        items: list[DeploymentPlanItem],
    ) -> None:
        if plan.status != "ready":
            raise DeploymentConflictError(f"部署计划当前状态不可确认：{plan.status}")
        now = datetime.now(timezone.utc)
        expires_at = plan.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            plan.status = "expired"
            plan.stale_reason = "部署计划已超过 24 小时有效期"
            session.flush()
            raise DeploymentConflictError(plan.stale_reason)

        current_snapshots: list[dict] = []
        for item in items:
            device = session.get(Device, item.device_id)
            if device is None:
                self._mark_stale(session, plan, "部署目标设备已不存在")
            assert device is not None
            try:
                self._require_deployable_device(device, plan.project_id)
            except DeploymentConflictError as exc:
                self._mark_stale(session, plan, str(exc))

            assignment = session.scalar(
                select(ProjectFunction).where(
                    ProjectFunction.project_id == plan.project_id,
                    ProjectFunction.function_id == item.function_id,
                    ProjectFunction.status == "active",
                )
            )
            if assignment is None:
                self._mark_stale(session, plan, f"项目功能 {item.function_id} 已移除或待卸载")
            assert assignment is not None
            if self._hash(assignment.config_json or {}) != item.config_hash:
                self._mark_stale(session, plan, f"项目功能 {item.function_id} 的配置已变化")

            try:
                release, override = self._resolve_release(session, device, assignment, now)
            except DeploymentConflictError as exc:
                self._mark_stale(session, plan, str(exc))
            if release.id != item.release_id:
                self._mark_stale(session, plan, f"项目功能 {item.function_id} 的期望版本或设备覆盖已变化")
            variant = session.get(FunctionVariant, item.variant_id)
            if release is None or release.status != "published":
                self._mark_stale(session, plan, f"功能版本 {item.release_id} 已不可部署")
            if (
                variant is None
                or variant.release_id != item.release_id
                or variant.hardware_profile_id != device.actual_profile_id
                or variant.status != "published"
                or variant.artifact_sha256 != item.artifact_sha256
            ):
                self._mark_stale(session, plan, f"功能 {item.function_id} 的硬件变体或制品已变化")
            assert variant is not None
            try:
                ArtifactService(self.settings).get_download(
                    session,
                    function_id=item.function_id,
                    release_id=item.release_id,
                    variant_id=item.variant_id,
                )
            except ArtifactStorageError:
                self._mark_stale(session, plan, f"功能 {item.function_id} 的制品文件已丢失")

            current_snapshots.append(
                {
                    "device_id": device.id,
                    "function_id": item.function_id,
                    "release_id": item.release_id,
                    "variant_id": item.variant_id,
                    "config_hash": item.config_hash,
                    "artifact_sha256": item.artifact_sha256,
                    "device_status": device.status,
                    "initialization_status": device.initialization_status,
                    "actual_profile_id": device.actual_profile_id,
                    "release_source": "device_override" if override is not None else "project_default",
                    "override_id": override.id if override is not None else None,
                    "override_expires_at": override.expires_at.isoformat() if override is not None else None,
                }
            )
        if self._hash(current_snapshots) != plan.snapshot_hash:
            self._mark_stale(session, plan, "部署目标状态已变化")

    def confirm(
        self,
        session: Session,
        *,
        plan_id: int,
        confirmed_by: int,
    ) -> tuple[DeploymentExecution, list[DeploymentExecutionItem]]:
        existing = session.scalar(select(DeploymentExecution).where(DeploymentExecution.plan_id == plan_id))
        if existing is not None:
            existing_items = list(
                session.scalars(
                    select(DeploymentExecutionItem)
                    .where(DeploymentExecutionItem.deployment_execution_id == existing.id)
                    .order_by(DeploymentExecutionItem.plan_item_id)
                )
            )
            return existing, existing_items

        plan, plan_items = self.get(session, plan_id)
        self.validate_for_confirmation(session, plan, plan_items)
        now = datetime.now(timezone.utc)
        plan.status = "confirmed"
        plan.confirmed_by = confirmed_by
        plan.confirmed_at = now
        execution = DeploymentExecution(plan_id=plan.id, status="pending", created_by=confirmed_by)
        session.add(execution)
        session.flush()
        execution_items = [
            DeploymentExecutionItem(
                deployment_execution_id=execution.id,
                plan_item_id=item.id,
                status="pending",
            )
            for item in plan_items
        ]
        session.add_all(execution_items)
        session.flush()
        session.refresh(plan)
        session.refresh(execution)
        for item in execution_items:
            session.refresh(item)
        return execution, execution_items

    def _require_deployable_device(self, device: Device, project_id: int) -> None:
        if device.project_id != project_id:
            raise DeploymentConflictError(f"设备 {device.device_sn} 不属于当前项目")
        if device.status != "online":
            raise DeploymentConflictError(f"设备 {device.device_sn} 当前不在线")
        if device.initialization_status not in self.READY_INITIALIZATION_STATUSES:
            raise DeploymentConflictError(f"设备 {device.device_sn} 尚未完成初始化")
        if device.actual_profile_id is None or device.actual_profile_id != device.expected_profile_id:
            raise DeploymentConflictError(f"设备 {device.device_sn} 的实际硬件规格与期望不一致")
        if device.ssh_port is None or not device.ssh_credential_configured:
            raise DeploymentConflictError(f"设备 {device.device_sn} 缺少可用 SSH 配置")

    def _resolve_release(
        self,
        session: Session,
        device: Device,
        assignment: ProjectFunction,
        now: datetime,
    ) -> tuple[FunctionRelease, DeviceReleaseOverride | None]:
        override = session.scalar(
            select(DeviceReleaseOverride).where(
                DeviceReleaseOverride.device_id == device.id,
                DeviceReleaseOverride.function_id == assignment.function_id,
                DeviceReleaseOverride.active.is_(True),
            )
        )
        if override is not None and self._as_utc(override.expires_at) <= now:
            override.active = False
            override = None
        release_id = override.release_id if override is not None else assignment.desired_release_id
        release = session.get(FunctionRelease, release_id)
        if release is None or release.function_id != assignment.function_id or release.status != "published":
            raise DeploymentConflictError(f"项目功能 {assignment.function_id} 未选择有效的已发布版本")
        return release, override

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _hash(self, value: object) -> str:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _mark_stale(self, session: Session, plan: DeploymentPlan, reason: str) -> None:
        plan.status = "stale"
        plan.stale_reason = reason
        session.flush()
        raise DeploymentConflictError(reason)
