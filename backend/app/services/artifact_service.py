from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.config import Settings
from app.models.lifecycle import EdgeFunction, FunctionRelease, FunctionVariant, HardwareProfile
from app.schemas.artifact import ArtifactManifest
from app.services.lifecycle_service import (
    LifecycleConflictError,
    LifecycleImmutableError,
    LifecycleNotFoundError,
)


REQUIRED_PACKAGE_PATHS = {
    "manifest.yaml",
    "config/default.yaml",
    "config/collect-schema.json",
    "scripts/preflight.sh",
    "scripts/install.sh",
    "scripts/configure.sh",
    "scripts/start.sh",
    "scripts/healthcheck.sh",
    "scripts/collect.sh",
    "scripts/rollback.sh",
    "scripts/uninstall.sh",
    "systemd/service.template",
}
MAX_ARCHIVE_MEMBERS = 10_000
MAX_UNPACKED_BYTES = 5 * 1024 * 1024 * 1024


class ArtifactValidationError(ValueError):
    pass


class ArtifactStorageError(RuntimeError):
    pass


class ArtifactService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def upload(
        self,
        session: Session,
        *,
        function_id: int,
        release_id: int,
        hardware_profile_id: int,
        upload: UploadFile,
    ) -> FunctionVariant:
        edge_function = session.get(EdgeFunction, function_id)
        if edge_function is None:
            raise LifecycleNotFoundError(f"功能不存在：{function_id}")
        release = session.get(FunctionRelease, release_id)
        if release is None or release.function_id != function_id:
            raise LifecycleNotFoundError(f"功能版本不存在：{release_id}")
        if release.status != "draft":
            raise LifecycleImmutableError(f"已发布版本不可修改：{release.version}")
        profile = session.get(HardwareProfile, hardware_profile_id)
        if profile is None or not profile.active:
            raise LifecycleNotFoundError(f"硬件规格不存在或已停用：{hardware_profile_id}")
        if not (upload.filename or "").lower().endswith(".tar.gz"):
            raise ArtifactValidationError("标准功能包必须使用 .tar.gz 格式")

        root = self.storage_root()
        root.mkdir(parents=True, exist_ok=True)
        temporary_path, size, digest = await self._write_temporary(root, upload)
        try:
            manifest = self._validate_archive(
                temporary_path,
                function_code=edge_function.code,
                version=release.version,
                profile_code=profile.code,
            )
            target = self._artifact_path(release.id, profile.id)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_path, target)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        variant = session.scalar(
            select(FunctionVariant).where(
                FunctionVariant.release_id == release.id,
                FunctionVariant.hardware_profile_id == profile.id,
            )
        )
        artifact_uri = f"artifacts/{target.relative_to(root).as_posix()}"
        if variant is None:
            variant = FunctionVariant(
                release_id=release.id,
                hardware_profile_id=profile.id,
                artifact_uri=artifact_uri,
                artifact_sha256=digest,
                artifact_size=size,
            )
            session.add(variant)
        else:
            variant.artifact_uri = artifact_uri
            variant.artifact_sha256 = digest
            variant.artifact_size = size
        if release.manifest_json is None:
            release.manifest_json = {
                "schema_version": manifest["schema_version"],
                "runtime": manifest["runtime"],
            }
        session.flush()
        session.refresh(variant)
        return variant

    def storage_root(self) -> Path:
        if self.settings.artifact_storage_dir:
            return Path(self.settings.artifact_storage_dir).resolve()
        if self.settings.database_url.startswith("sqlite:///"):
            database_path = Path(self.settings.database_url.replace("sqlite:///", "", 1)).resolve()
            return database_path.parent / "artifacts"
        return (Path("data") / "artifacts").resolve()

    def get_download(
        self,
        session: Session,
        *,
        function_id: int,
        release_id: int,
        variant_id: int,
    ) -> tuple[Path, FunctionVariant, str]:
        edge_function = session.get(EdgeFunction, function_id)
        release = session.get(FunctionRelease, release_id)
        variant = session.get(FunctionVariant, variant_id)
        if edge_function is None:
            raise LifecycleNotFoundError(f"功能不存在：{function_id}")
        if release is None or release.function_id != function_id:
            raise LifecycleNotFoundError(f"功能版本不存在：{release_id}")
        if variant is None or variant.release_id != release_id:
            raise LifecycleNotFoundError(f"功能变体不存在：{variant_id}")
        profile = session.get(HardwareProfile, variant.hardware_profile_id)
        if profile is None:
            raise LifecycleNotFoundError(f"硬件规格不存在：{variant.hardware_profile_id}")
        path = self._artifact_path(release.id, profile.id)
        if not path.is_file():
            raise ArtifactStorageError("功能包文件不存在")
        filename = f"{edge_function.code}-{release.version}-{profile.code}.tar.gz"
        return path, variant, filename

    def verify_release_artifacts(self, session: Session, *, function_id: int, release_id: int) -> None:
        release = session.get(FunctionRelease, release_id)
        if release is None or release.function_id != function_id:
            raise LifecycleNotFoundError(f"功能版本不存在：{release_id}")
        variants = list(session.scalars(select(FunctionVariant).where(FunctionVariant.release_id == release_id)))
        for variant in variants:
            path = self._artifact_path(release.id, variant.hardware_profile_id)
            expected_uri = f"artifacts/{path.relative_to(self.storage_root()).as_posix()}"
            if variant.artifact_uri != expected_uri or not path.is_file():
                raise LifecycleConflictError("发布前必须将所有硬件变体上传到平台制品仓库")
            if path.stat().st_size != variant.artifact_size:
                raise LifecycleConflictError("平台制品文件大小与登记信息不一致，请重新上传")
            digest = hashlib.sha256()
            with path.open("rb") as artifact:
                while chunk := artifact.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != variant.artifact_sha256:
                raise LifecycleConflictError("平台制品 SHA-256 校验失败，请重新上传")

    async def _write_temporary(self, root: Path, upload: UploadFile) -> tuple[Path, int, str]:
        digest = hashlib.sha256()
        size = 0
        temporary_file = NamedTemporaryFile(prefix="artifact-", suffix=".tar.gz", dir=root, delete=False)
        temporary_path = Path(temporary_file.name)
        try:
            with temporary_file as temporary:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.artifact_max_upload_bytes:
                        raise ArtifactValidationError(
                            f"功能包超过上传上限：{self.settings.artifact_max_upload_bytes} 字节"
                        )
                    digest.update(chunk)
                    temporary.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        if size == 0:
            temporary_path.unlink(missing_ok=True)
            raise ArtifactValidationError("功能包不能为空")
        return temporary_path, size, digest.hexdigest()

    def _artifact_path(self, release_id: int, profile_id: int) -> Path:
        return self.storage_root() / "releases" / str(release_id) / "profiles" / str(profile_id) / "package.tar.gz"

    def _validate_archive(
        self,
        path: Path,
        *,
        function_code: str,
        version: str,
        profile_code: str,
    ) -> dict:
        try:
            with tarfile.open(path, mode="r:gz") as archive:
                files: dict[str, tarfile.TarInfo] = {}
                roots: set[str] = set()
                members = archive.getmembers()
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise ArtifactValidationError(f"功能包文件数量不能超过 {MAX_ARCHIVE_MEMBERS}")
                unpacked_size = sum(member.size for member in members if member.isfile())
                if unpacked_size > MAX_UNPACKED_BYTES:
                    raise ArtifactValidationError(f"功能包解压后不能超过 {MAX_UNPACKED_BYTES} 字节")
                for member in members:
                    member_path = PurePosixPath(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ArtifactValidationError(f"功能包包含不安全路径：{member.name}")
                    if member.issym() or member.islnk() or member.isdev():
                        raise ArtifactValidationError(f"功能包不允许链接或设备文件：{member.name}")
                    parts = [part for part in member_path.parts if part not in {"", "."}]
                    if not parts:
                        continue
                    roots.add(parts[0])
                    if member.isfile() and len(parts) > 1:
                        relative_path = PurePosixPath(*parts[1:]).as_posix()
                        if relative_path in files:
                            raise ArtifactValidationError(f"功能包包含重复路径：{relative_path}")
                        files[relative_path] = member
                if len(roots) != 1:
                    raise ArtifactValidationError("功能包必须只有一个顶层目录")
                missing = sorted(REQUIRED_PACKAGE_PATHS - files.keys())
                if missing:
                    raise ArtifactValidationError(f"功能包缺少必需文件：{', '.join(missing)}")
                if not any(name.startswith("artifacts/") for name in files):
                    raise ArtifactValidationError("功能包 artifacts 目录中至少需要一个制品文件")
                for script in sorted(path for path in REQUIRED_PACKAGE_PATHS if path.startswith("scripts/")):
                    if files[script].mode & 0o111 == 0:
                        raise ArtifactValidationError(f"生命周期脚本必须具有可执行权限：{script}")
                manifest_file = archive.extractfile(files["manifest.yaml"])
                if manifest_file is None:
                    raise ArtifactValidationError("无法读取 manifest.yaml")
                manifest_bytes = manifest_file.read(64 * 1024 + 1)
                if len(manifest_bytes) > 64 * 1024:
                    raise ArtifactValidationError("manifest.yaml 不能超过 64 KiB")
                default_config = archive.extractfile(files["config/default.yaml"])
                collect_schema = archive.extractfile(files["config/collect-schema.json"])
                if default_config is None or collect_schema is None:
                    raise ArtifactValidationError("无法读取功能包配置文件")
                default_config_bytes = default_config.read(1024 * 1024 + 1)
                collect_schema_bytes = collect_schema.read(1024 * 1024 + 1)
                if len(default_config_bytes) > 1024 * 1024 or len(collect_schema_bytes) > 1024 * 1024:
                    raise ArtifactValidationError("单个功能包配置文件不能超过 1 MiB")
        except ArtifactValidationError:
            raise
        except (tarfile.TarError, OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ArtifactValidationError("无法解析标准功能包") from exc

        try:
            manifest = ArtifactManifest.model_validate(yaml.safe_load(manifest_bytes))
            default_config_value = yaml.safe_load(default_config_bytes)
            collect_schema_value = json.loads(collect_schema_bytes)
        except (yaml.YAMLError, json.JSONDecodeError, ValidationError) as exc:
            raise ArtifactValidationError("功能包清单或配置格式不合法") from exc
        if not isinstance(default_config_value, dict):
            raise ArtifactValidationError("config/default.yaml 必须是对象")
        if not isinstance(collect_schema_value, dict):
            raise ArtifactValidationError("config/collect-schema.json 必须是对象")
        expected = {
            "schema_version": 1,
            "function_code": function_code,
            "version": version,
            "hardware_profile": profile_code,
            "runtime": "python-venv-systemd",
        }
        for field, value in expected.items():
            if getattr(manifest, field) != value:
                raise ArtifactValidationError(f"manifest.yaml 字段 {field} 必须为 {value}")
        return manifest.model_dump(mode="json")
