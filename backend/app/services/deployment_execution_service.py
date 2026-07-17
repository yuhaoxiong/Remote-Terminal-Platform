from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.device import Device
from app.models.lifecycle import (
    DeploymentExecution,
    DeploymentExecutionItem,
    DeploymentPlanItem,
    EdgeFunction,
    FunctionRelease,
    FunctionVariant,
)
from app.services.artifact_service import ArtifactService, ArtifactStorageError
from app.services.lifecycle_service import LifecycleNotFoundError
from app.services.security import TokenError, create_token, decode_token
from app.services.ssh_service import RemoteAuthenticationError, RemoteConnectionError, SshService


class DeploymentExecutionNotFoundError(LookupError):
    pass


class DeploymentExecutionConflictError(ValueError):
    pass


class DeploymentArtifactAuthorizationError(PermissionError):
    pass


class DeploymentExecutionService:
    output_limit = 4000

    def __init__(self, settings: Settings, ssh_service: SshService | None = None) -> None:
        self.settings = settings
        self.ssh_service = ssh_service or SshService(settings)

    def get(
        self,
        session: Session,
        execution_id: str,
    ) -> tuple[DeploymentExecution, list[DeploymentExecutionItem]]:
        execution = session.scalar(
            select(DeploymentExecution).where(DeploymentExecution.execution_id == execution_id)
        )
        if execution is None:
            raise DeploymentExecutionNotFoundError(f"部署执行不存在：{execution_id}")
        items = list(
            session.scalars(
                select(DeploymentExecutionItem)
                .where(DeploymentExecutionItem.deployment_execution_id == execution.id)
                .order_by(DeploymentExecutionItem.id)
            )
        )
        return execution, items

    def execute(
        self,
        session: Session,
        execution_id: str,
    ) -> tuple[DeploymentExecution, list[DeploymentExecutionItem]]:
        execution, items = self.get(session, execution_id)
        if execution.status in {"completed", "failed", "partial_failed"}:
            return execution, items
        if execution.status != "pending":
            raise DeploymentExecutionConflictError(f"部署执行当前状态不可启动：{execution.status}")
        platform_url = (self.settings.bootstrap_platform_url or "").rstrip("/")
        if not platform_url.startswith("https://"):
            raise DeploymentExecutionConflictError("执行部署前必须配置 HTTPS 平台地址")

        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        session.flush()
        for item in items:
            self._execute_item(session, execution, item, platform_url)
        execution.finished_at = datetime.now(timezone.utc)
        success_count = sum(1 for item in items if item.status == "success")
        if success_count == len(items):
            execution.status = "completed"
        elif success_count:
            execution.status = "partial_failed"
        else:
            execution.status = "failed"
        session.flush()
        session.refresh(execution)
        for item in items:
            session.refresh(item)
        return execution, items

    def get_artifact(
        self,
        session: Session,
        *,
        execution_id: str,
        item_id: int,
        token: str,
    ) -> tuple[Path, FunctionVariant, str]:
        try:
            payload = decode_token(self.settings, token, "deployment_artifact")
        except TokenError as exc:
            raise DeploymentArtifactAuthorizationError("部署制品令牌无效或已过期") from exc
        if payload.get("sub") != f"{execution_id}:{item_id}":
            raise DeploymentArtifactAuthorizationError("部署制品令牌与执行项不匹配")
        execution, _items = self.get(session, execution_id)
        item = session.get(DeploymentExecutionItem, item_id)
        if item is None or item.deployment_execution_id != execution.id:
            raise DeploymentExecutionNotFoundError(f"部署执行项不存在：{item_id}")
        plan_item = session.get(DeploymentPlanItem, item.plan_item_id)
        if plan_item is None:
            raise DeploymentExecutionNotFoundError(f"部署计划项不存在：{item.plan_item_id}")
        try:
            path, variant, filename = ArtifactService(self.settings).get_download(
                session,
                function_id=plan_item.function_id,
                release_id=plan_item.release_id,
                variant_id=plan_item.variant_id,
            )
        except (LifecycleNotFoundError, ArtifactStorageError) as exc:
            raise DeploymentExecutionNotFoundError(str(exc)) from exc
        if variant.artifact_sha256 != plan_item.artifact_sha256:
            raise DeploymentExecutionConflictError("部署制品哈希已变化")
        return path, variant, filename

    def _execute_item(
        self,
        session: Session,
        execution: DeploymentExecution,
        item: DeploymentExecutionItem,
        platform_url: str,
    ) -> None:
        plan_item = session.get(DeploymentPlanItem, item.plan_item_id)
        if plan_item is None:
            self._mark_failed(item, "部署计划项不存在")
            return
        device = session.get(Device, plan_item.device_id)
        edge_function = session.get(EdgeFunction, plan_item.function_id)
        release = session.get(FunctionRelease, plan_item.release_id)
        if device is None or edge_function is None or release is None:
            self._mark_failed(item, "部署目标、功能或版本不存在")
            return

        item.status = "running"
        item.attempt_count += 1
        item.started_at = datetime.now(timezone.utc)
        item.finished_at = None
        item.error_message = None
        descriptor = self._descriptor(execution, item, plan_item, device, edge_function, release, platform_url)
        encoded = base64.b64encode(
            json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        command = "sudo -n /usr/local/bin/edge-deploy apply --stdin"
        try:
            exit_code, stdout_text, stderr_text = self.ssh_service.execute_with_input(
                device,
                command,
                encoded + "\n",
                self.settings.deployment_timeout_seconds,
            )
        except RemoteAuthenticationError:
            self._mark_failed(item, "SSH 认证失败")
            return
        except RemoteConnectionError as exc:
            self._mark_failed(item, str(exc))
            return
        except Exception:
            self._mark_failed(item, "SSH 执行异常")
            return

        try:
            result = json.loads(stdout_text)
        except (json.JSONDecodeError, TypeError):
            fallback = self._truncate(stderr_text) or f"edge-deploy 退出码：{exit_code}"
            self._mark_failed(item, f"edge-deploy 未返回有效 JSON；{fallback}")
            return
        if (
            not isinstance(result, dict)
            or result.get("execution_id") != execution.execution_id
            or result.get("function_code") != edge_function.code
        ):
            self._mark_failed(item, "edge-deploy 返回结果与执行项不匹配")
            return
        item.result_json = result
        if exit_code != 0 or result.get("status") != "succeeded":
            item.status = "rolled_back" if result.get("rollback_performed") is True else "failed"
            item.error_message = self._truncate(
                str(result.get("message") or stderr_text or f"edge-deploy 退出码非 0：{exit_code}")
            )
            item.finished_at = datetime.now(timezone.utc)
            return
        item.status = "success"
        item.finished_at = datetime.now(timezone.utc)

    def _descriptor(
        self,
        execution: DeploymentExecution,
        item: DeploymentExecutionItem,
        plan_item: DeploymentPlanItem,
        device: Device,
        edge_function: EdgeFunction,
        release: FunctionRelease,
        platform_url: str,
    ) -> dict:
        fingerprint_payload = {
            "execution_id": execution.execution_id,
            "execution_item_id": item.id,
            "function_code": edge_function.code,
            "version": release.version,
            "artifact_sha256": plan_item.artifact_sha256,
            "config_hash": plan_item.config_hash,
            "rollback_on_failure": not device.is_test_device,
        }
        deployment_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_token = create_token(
            self.settings,
            subject=f"{execution.execution_id}:{item.id}",
            token_type="deployment_artifact",
            expires_delta=timedelta(minutes=30),
        )
        return {
            "schema_version": 1,
            "execution_id": execution.execution_id,
            "execution_item_id": item.id,
            "function_code": edge_function.code,
            "version": release.version,
            "artifact_url": (
                f"{platform_url}{self.settings.api_prefix}/deployment-executions/"
                f"{execution.execution_id}/items/{item.id}/artifact"
            ),
            "artifact_token": artifact_token,
            "artifact_sha256": plan_item.artifact_sha256,
            "deployment_fingerprint": deployment_fingerprint,
            "config": plan_item.config_snapshot or {},
            "rollback_on_failure": not device.is_test_device,
            "ca_cert_path": "/usr/local/share/ca-certificates/edge-platform-ca.crt",
        }

    def _mark_failed(self, item: DeploymentExecutionItem, message: str) -> None:
        item.status = "failed"
        item.error_message = self._truncate(message)
        item.finished_at = datetime.now(timezone.utc)

    def _truncate(self, value: str) -> str:
        if len(value) <= self.output_limit:
            return value
        return value[: self.output_limit] + "...[已截断]"
