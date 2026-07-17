from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lifecycle import (
    EdgeFunction,
    FunctionRelease,
    FunctionVariant,
    HardwareProfile,
    Project,
    ProjectFunction,
)
from app.schemas.lifecycle import (
    FunctionCreate,
    FunctionReleaseCreate,
    FunctionReleaseUpdate,
    FunctionUpdate,
    FunctionVariantCreate,
    FunctionVariantUpdate,
    ProjectCreate,
    ProjectFunctionSet,
    ProjectUpdate,
)


class LifecycleNotFoundError(ValueError):
    pass


class LifecycleConflictError(ValueError):
    pass


class LifecycleImmutableError(ValueError):
    pass


class ProjectService:
    def list(self, session: Session, *, offset: int, limit: int) -> tuple[int, list[Project]]:
        total = session.scalar(select(func.count(Project.id))) or 0
        items = list(session.scalars(select(Project).order_by(Project.id).offset(offset).limit(limit)))
        return total, items

    def get(self, session: Session, project_id: int) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise LifecycleNotFoundError(f"项目不存在：{project_id}")
        return project

    def create(self, session: Session, payload: ProjectCreate) -> Project:
        code = payload.code or self._generated_code(session)
        if session.scalar(select(Project.id).where(Project.code == code)) is not None:
            raise LifecycleConflictError(f"项目代码已存在：{code}")
        project = Project(code=code, **payload.model_dump(exclude={"code"}))
        session.add(project)
        session.flush()
        session.refresh(project)
        return project

    def _generated_code(self, session: Session) -> str:
        while True:
            code = f"project-{uuid4().hex[:12]}"
            if session.scalar(select(Project.id).where(Project.code == code)) is None:
                return code

    def update(self, session: Session, project_id: int, payload: ProjectUpdate) -> Project:
        project = self.get(session, project_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        session.flush()
        session.refresh(project)
        return project

    def list_functions(self, session: Session, project_id: int) -> tuple[int, list[ProjectFunction]]:
        self.get(session, project_id)
        statement = select(ProjectFunction).where(ProjectFunction.project_id == project_id)
        total = session.scalar(select(func.count(ProjectFunction.id)).where(ProjectFunction.project_id == project_id)) or 0
        return total, list(session.scalars(statement.order_by(ProjectFunction.id)))

    def set_function(
        self,
        session: Session,
        project_id: int,
        function_id: int,
        payload: ProjectFunctionSet,
    ) -> ProjectFunction:
        project = self.get(session, project_id)
        if project.status != "active":
            raise LifecycleConflictError(f"归档项目不能配置功能：{project.code}")
        edge_function = FunctionService().get(session, function_id)
        if edge_function.status != "active":
            raise LifecycleConflictError(f"归档功能不能分配：{edge_function.code}")
        release = FunctionService().get_release(session, function_id, payload.desired_release_id)
        if release.status != "published":
            raise LifecycleConflictError("项目只能选择已发布版本")

        assignment = session.scalar(
            select(ProjectFunction).where(
                ProjectFunction.project_id == project_id,
                ProjectFunction.function_id == function_id,
            )
        )
        if assignment is None:
            assignment = ProjectFunction(
                project_id=project_id,
                function_id=function_id,
                desired_release_id=release.id,
                config_json=payload.config_json,
                status="active",
            )
            session.add(assignment)
        else:
            assignment.desired_release_id = release.id
            assignment.config_json = payload.config_json
            assignment.status = "active"
        session.flush()
        session.refresh(assignment)
        return assignment

    def mark_pending_uninstall(self, session: Session, project_id: int, function_id: int) -> ProjectFunction:
        assignment = session.scalar(
            select(ProjectFunction).where(
                ProjectFunction.project_id == project_id,
                ProjectFunction.function_id == function_id,
            )
        )
        if assignment is None:
            raise LifecycleNotFoundError("项目未启用该功能")
        assignment.status = "pending_uninstall"
        session.flush()
        session.refresh(assignment)
        return assignment


class HardwareProfileService:
    def list(self, session: Session, *, active_only: bool = True) -> tuple[int, list[HardwareProfile]]:
        statement = select(HardwareProfile)
        count_statement = select(func.count(HardwareProfile.id))
        if active_only:
            statement = statement.where(HardwareProfile.active.is_(True))
            count_statement = count_statement.where(HardwareProfile.active.is_(True))
        total = session.scalar(count_statement) or 0
        return total, list(session.scalars(statement.order_by(HardwareProfile.id)))


class FunctionService:
    def list(self, session: Session, *, offset: int, limit: int) -> tuple[int, list[EdgeFunction]]:
        total = session.scalar(select(func.count(EdgeFunction.id))) or 0
        items = list(session.scalars(select(EdgeFunction).order_by(EdgeFunction.id).offset(offset).limit(limit)))
        return total, items

    def get(self, session: Session, function_id: int) -> EdgeFunction:
        edge_function = session.get(EdgeFunction, function_id)
        if edge_function is None:
            raise LifecycleNotFoundError(f"功能不存在：{function_id}")
        return edge_function

    def create(self, session: Session, payload: FunctionCreate) -> EdgeFunction:
        code = payload.code or self._generated_code(session)
        if session.scalar(select(EdgeFunction.id).where(EdgeFunction.code == code)) is not None:
            raise LifecycleConflictError(f"功能代码已存在：{code}")
        edge_function = EdgeFunction(code=code, **payload.model_dump(exclude={"code"}))
        session.add(edge_function)
        session.flush()
        session.refresh(edge_function)
        return edge_function

    def _generated_code(self, session: Session) -> str:
        while True:
            code = f"function-{uuid4().hex[:12]}"
            if session.scalar(select(EdgeFunction.id).where(EdgeFunction.code == code)) is None:
                return code

    def update(self, session: Session, function_id: int, payload: FunctionUpdate) -> EdgeFunction:
        edge_function = self.get(session, function_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(edge_function, field, value)
        session.flush()
        session.refresh(edge_function)
        return edge_function

    def list_releases(self, session: Session, function_id: int) -> tuple[int, list[FunctionRelease]]:
        self.get(session, function_id)
        statement = select(FunctionRelease).where(FunctionRelease.function_id == function_id)
        total = session.scalar(select(func.count(FunctionRelease.id)).where(FunctionRelease.function_id == function_id)) or 0
        return total, list(session.scalars(statement.order_by(FunctionRelease.id)))

    def get_release(self, session: Session, function_id: int, release_id: int) -> FunctionRelease:
        release = session.get(FunctionRelease, release_id)
        if release is None or release.function_id != function_id:
            raise LifecycleNotFoundError(f"功能版本不存在：{release_id}")
        return release

    def create_release(
        self,
        session: Session,
        function_id: int,
        payload: FunctionReleaseCreate,
        *,
        created_by: int,
    ) -> FunctionRelease:
        edge_function = self.get(session, function_id)
        if edge_function.status != "active":
            raise LifecycleConflictError(f"归档功能不能创建版本：{edge_function.code}")
        if session.scalar(
            select(FunctionRelease.id).where(
                FunctionRelease.function_id == function_id,
                FunctionRelease.version == payload.version,
            )
        ) is not None:
            raise LifecycleConflictError(f"版本已存在：{payload.version}")
        release = FunctionRelease(function_id=function_id, created_by=created_by, **payload.model_dump())
        session.add(release)
        session.flush()
        session.refresh(release)
        return release

    def update_release(
        self,
        session: Session,
        function_id: int,
        release_id: int,
        payload: FunctionReleaseUpdate,
    ) -> FunctionRelease:
        release = self.get_release(session, function_id, release_id)
        self._require_draft(release)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(release, field, value)
        session.flush()
        session.refresh(release)
        return release

    def add_variant(
        self,
        session: Session,
        function_id: int,
        release_id: int,
        payload: FunctionVariantCreate,
    ) -> FunctionVariant:
        release = self.get_release(session, function_id, release_id)
        self._require_draft(release)
        profile = session.get(HardwareProfile, payload.hardware_profile_id)
        if profile is None or not profile.active:
            raise LifecycleNotFoundError(f"硬件规格不存在或已停用：{payload.hardware_profile_id}")
        if session.scalar(
            select(FunctionVariant.id).where(
                FunctionVariant.release_id == release_id,
                FunctionVariant.hardware_profile_id == payload.hardware_profile_id,
            )
        ) is not None:
            raise LifecycleConflictError("该版本的硬件变体已存在")
        variant = FunctionVariant(release_id=release_id, **payload.model_dump())
        session.add(variant)
        session.flush()
        session.refresh(variant)
        return variant

    def list_variants(
        self,
        session: Session,
        function_id: int,
        release_id: int,
    ) -> tuple[int, list[FunctionVariant]]:
        self.get_release(session, function_id, release_id)
        statement = select(FunctionVariant).where(FunctionVariant.release_id == release_id)
        total = session.scalar(select(func.count(FunctionVariant.id)).where(FunctionVariant.release_id == release_id)) or 0
        return total, list(session.scalars(statement.order_by(FunctionVariant.id)))

    def update_variant(
        self,
        session: Session,
        function_id: int,
        release_id: int,
        variant_id: int,
        payload: FunctionVariantUpdate,
    ) -> FunctionVariant:
        release = self.get_release(session, function_id, release_id)
        self._require_draft(release)
        variant = session.get(FunctionVariant, variant_id)
        if variant is None or variant.release_id != release_id:
            raise LifecycleNotFoundError(f"功能变体不存在：{variant_id}")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(variant, field, value)
        session.flush()
        session.refresh(variant)
        return variant

    def publish_release(self, session: Session, function_id: int, release_id: int) -> FunctionRelease:
        release = self.get_release(session, function_id, release_id)
        self._require_draft(release)
        variants = list(session.scalars(select(FunctionVariant).where(FunctionVariant.release_id == release_id)))
        if not variants:
            raise LifecycleConflictError("发布前至少需要一个硬件变体")
        release.status = "published"
        release.published_at = datetime.now(timezone.utc)
        for variant in variants:
            variant.status = "published"
        session.flush()
        session.refresh(release)
        return release

    def _require_draft(self, release: FunctionRelease) -> None:
        if release.status != "draft":
            raise LifecycleImmutableError(f"已发布版本不可修改：{release.version}")
