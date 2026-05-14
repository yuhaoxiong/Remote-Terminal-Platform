import stat
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models.device import Device
from app.services.file_service import FilePathError, FileService


class FakeSftp:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {"/opt/app/config.txt": b"mode=remote\n"}
        self.closed = False

    def listdir_attr(self, path: str):
        assert path == "/opt/app"
        return [
            SimpleNamespace(
                filename="config.txt",
                st_size=len(self.files["/opt/app/config.txt"]),
                st_mode=stat.S_IFREG | 0o644,
                st_mtime=1_700_000_000,
            )
        ]

    def open(self, path: str, mode: str):
        sftp = self

        class RemoteFile:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self):
                return sftp.files[path]

            def write(self, data):
                sftp.files[path] = data.encode("utf-8") if isinstance(data, str) else data

        return RemoteFile()

    def remove(self, path: str) -> None:
        del self.files[path]

    def close(self) -> None:
        self.closed = True


class FakeSshService:
    def __init__(self) -> None:
        self.sftp = FakeSftp()

    def open_sftp(self, device):
        return self.sftp


def _device() -> Device:
    return Device(id=7, name="SFTP", device_sn="sftp-001", project_id="factory", ssh_user="root", ssh_port=10000)


def test_file_service_can_use_sftp_backend_for_remote_files() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret_key="test-secret-key",
        file_backend="sftp",
    )
    ssh_service = FakeSshService()
    service = FileService(settings, ssh_service=ssh_service)
    device = _device()

    items = service.list_files(device, "/opt/app")
    assert items[0].name == "config.txt"
    assert items[0].type == "file"
    assert items[0].size == 12
    assert items[0].modified_at is not None

    assert service.download_text(device, "/opt/app/config.txt") == "mode=remote\n"
    assert service.upload_text(device, "/opt/app/next.txt", "next") == 4
    assert ssh_service.sftp.files["/opt/app/next.txt"] == b"next"

    service.delete(device, "/opt/app/next.txt")
    assert "/opt/app/next.txt" not in ssh_service.sftp.files
    assert ssh_service.sftp.closed is True


@pytest.mark.parametrize("unsafe_path", ["", "../secret", "/../secret", "/"])
def test_sftp_file_service_rejects_unsafe_paths(unsafe_path: str) -> None:
    settings = Settings(database_url="sqlite:///:memory:", jwt_secret_key="test-secret-key", file_backend="sftp")
    service = FileService(settings, ssh_service=FakeSshService())

    with pytest.raises(FilePathError):
        service.delete(_device(), unsafe_path)
