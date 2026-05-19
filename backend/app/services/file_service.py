import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.config import Settings
from app.models.device import Device
from app.schemas.file_transfer import FileItem
from app.services.ssh_service import SshService


class FilePathError(ValueError):
    pass


class RemoteFileNotFoundError(FileNotFoundError):
    pass


class FileService:
    def __init__(self, settings: Settings, ssh_service: SshService | None = None) -> None:
        self.settings = settings
        self.ssh_service = ssh_service or SshService(settings)

    def list_files(self, device: Device, remote_path: str) -> list[FileItem]:
        if self.settings.file_backend == "sftp":
            return self._list_sftp_files(device, remote_path)

        directory = self._resolve(device.id, remote_path)
        if not directory.exists():
            return []
        if not directory.is_dir():
            raise FilePathError(f"Remote path is not a directory: {remote_path}")

        items: list[FileItem] = []
        for child in sorted(directory.iterdir(), key=lambda path: path.name):
            child_remote = self._remote_join(remote_path, child.name)
            items.append(
                FileItem(
                    name=child.name,
                    path=child_remote,
                    type="directory" if child.is_dir() else "file",
                    size=0 if child.is_dir() else child.stat().st_size,
                )
            )
        return items

    def upload_text(self, device: Device, remote_path: str, content: str) -> int:
        return self.upload_bytes(device, remote_path, content.encode("utf-8"))

    def upload_bytes(self, device: Device, remote_path: str, content: bytes) -> int:
        if self.settings.file_backend == "sftp":
            target = self._normalize_sftp_file_path(remote_path)
            sftp = self.ssh_service.open_sftp(device)
            try:
                with sftp.open(target, "wb") as remote_file:
                    remote_file.write(content)
                return len(content)
            finally:
                sftp.close()

        target = self._resolve(device.id, remote_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return len(content)

    def download_text(self, device: Device, remote_path: str) -> str:
        return self.download_bytes(device, remote_path).decode("utf-8")

    def download_bytes(self, device: Device, remote_path: str) -> bytes:
        if self.settings.file_backend == "sftp":
            target = self._normalize_sftp_file_path(remote_path)
            sftp = self.ssh_service.open_sftp(device)
            try:
                with sftp.open(target, "rb") as remote_file:
                    content = remote_file.read()
                if isinstance(content, bytes):
                    return content
                return str(content).encode("utf-8")
            except OSError as exc:
                raise RemoteFileNotFoundError(remote_path) from exc
            finally:
                sftp.close()

        target = self._resolve(device.id, remote_path)
        if not target.exists() or not target.is_file():
            raise RemoteFileNotFoundError(remote_path)
        return target.read_bytes()

    def delete(self, device: Device, remote_path: str) -> None:
        if self.settings.file_backend == "sftp":
            target = self._normalize_sftp_file_path(remote_path)
            sftp = self.ssh_service.open_sftp(device)
            try:
                sftp.remove(target)
            except OSError as exc:
                raise RemoteFileNotFoundError(remote_path) from exc
            finally:
                sftp.close()
            return

        target = self._resolve(device.id, remote_path)
        if not target.exists() or not target.is_file():
            raise RemoteFileNotFoundError(remote_path)
        target.unlink()

    def _resolve(self, device_id: int, remote_path: str) -> Path:
        relative = self._normalize_remote_path(remote_path)
        root = self._device_root(device_id)
        path = (root / relative).resolve()
        if root.resolve() not in [path, *path.parents]:
            raise FilePathError(f"Remote path escapes device storage: {remote_path}")
        return path

    def _device_root(self, device_id: int) -> Path:
        if self.settings.file_storage_dir:
            root = Path(self.settings.file_storage_dir)
        elif self.settings.database_url.startswith("sqlite:///"):
            root = Path(self.settings.database_url.replace("sqlite:///", "", 1)).parent / "device-files"
        else:
            root = Path("data") / "device-files"
        return root / str(device_id)

    def _normalize_remote_path(self, remote_path: str) -> Path:
        posix_path = PurePosixPath(remote_path)
        parts = [part for part in posix_path.parts if part not in {"", "/"}]
        if not parts:
            return Path()
        if any(part in {".", ".."} for part in parts):
            raise FilePathError(f"Remote path contains unsafe segments: {remote_path}")
        return Path(*parts)

    def _remote_join(self, remote_path: str, name: str) -> str:
        base = PurePosixPath(remote_path)
        if str(base) == ".":
            base = PurePosixPath("/")
        return str(base / name)

    def _list_sftp_files(self, device: Device, remote_path: str) -> list[FileItem]:
        directory = self._normalize_sftp_directory_path(remote_path)
        sftp = self.ssh_service.open_sftp(device)
        try:
            items: list[FileItem] = []
            for entry in sorted(sftp.listdir_attr(directory), key=lambda item: item.filename):
                entry_path = str(PurePosixPath(directory) / entry.filename)
                is_directory = stat.S_ISDIR(entry.st_mode)
                modified_at = None
                if entry.st_mtime is not None:
                    modified_at = datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc)
                items.append(
                    FileItem(
                        name=entry.filename,
                        path=entry_path,
                        type="directory" if is_directory else "file",
                        size=0 if is_directory else int(entry.st_size or 0),
                        modified_at=modified_at,
                    )
                )
            return items
        except OSError as exc:
            raise RemoteFileNotFoundError(remote_path) from exc
        finally:
            sftp.close()

    def _normalize_sftp_directory_path(self, remote_path: str) -> str:
        return self._normalize_sftp_path(remote_path, allow_root=True)

    def _normalize_sftp_file_path(self, remote_path: str) -> str:
        return self._normalize_sftp_path(remote_path, allow_root=False)

    def _normalize_sftp_path(self, remote_path: str, *, allow_root: bool) -> str:
        if not remote_path:
            raise FilePathError("Remote path is required")
        posix_path = PurePosixPath(remote_path)
        parts = [part for part in posix_path.parts if part not in {"", "/"}]
        if any(part in {".", ".."} for part in parts):
            raise FilePathError(f"Remote path contains unsafe segments: {remote_path}")
        if not parts:
            if allow_root:
                return "/"
            raise FilePathError("Remote file path is required")
        return "/" + str(PurePosixPath(*parts))
