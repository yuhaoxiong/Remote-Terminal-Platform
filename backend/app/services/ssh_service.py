import socket
from typing import Any

from app.config import Settings
from app.models.device import Device
from app.services.encryption import EncryptionService


class RemoteConnectionError(RuntimeError):
    pass


class RemoteAuthenticationError(RemoteConnectionError):
    pass


class SshShellSession:
    def recv(self, size: int = 4096, timeout: float = 0.2) -> bytes:
        raise NotImplementedError

    def send(self, data: str) -> None:
        raise NotImplementedError

    def resize(self, columns: int, rows: int) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class ParamikoShellSession(SshShellSession):
    def __init__(self, client: Any, channel: Any) -> None:
        self.client = client
        self.channel = channel

    def recv(self, size: int = 4096, timeout: float = 0.2) -> bytes:
        self.channel.settimeout(timeout)
        try:
            return self.channel.recv(size)
        except socket.timeout:
            return b""

    def send(self, data: str) -> None:
        self.channel.send(data)

    def resize(self, columns: int, rows: int) -> None:
        self.channel.resize_pty(width=columns, height=rows)

    def close(self) -> None:
        try:
            self.channel.close()
        finally:
            self.client.close()


class ParamikoSftpSession:
    def __init__(self, client: Any, sftp: Any) -> None:
        self.client = client
        self.sftp = sftp

    def listdir_attr(self, path: str):
        return self.sftp.listdir_attr(path)

    def open(self, path: str, mode: str):
        return self.sftp.open(path, mode)

    def remove(self, path: str) -> None:
        self.sftp.remove(path)

    def stat(self, path: str):
        return self.sftp.stat(path)

    def mkdir(self, path: str) -> None:
        self.sftp.mkdir(path)

    def rmdir(self, path: str) -> None:
        self.sftp.rmdir(path)

    def rename(self, source: str, target: str) -> None:
        self.sftp.rename(source, target)

    def close(self) -> None:
        try:
            self.sftp.close()
        finally:
            self.client.close()


class SshService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.encryption = EncryptionService(settings)

    def open_shell(self, device: Device) -> SshShellSession:
        client = self._connect(device)
        channel = client.invoke_shell(term="xterm-256color", width=120, height=32)
        return ParamikoShellSession(client, channel)

    def open_sftp(self, device: Device) -> ParamikoSftpSession:
        client = self._connect(device)
        return ParamikoSftpSession(client, client.open_sftp())

    def execute(self, device: Device, command: str, timeout: int | None = None) -> tuple[int, str, str]:
        client = self._connect(device)
        try:
            _stdin, stdout, stderr = client.exec_command(command, timeout=timeout or self.settings.ssh_timeout_seconds)
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
            return stdout.channel.recv_exit_status(), stdout_text, stderr_text
        finally:
            client.close()

    def execute_with_input(
        self,
        device: Device,
        command: str,
        input_text: str,
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        client = self._connect(device)
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout or self.settings.ssh_timeout_seconds)
            stdin.write(input_text)
            stdin.flush()
            stdin.channel.shutdown_write()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
            return stdout.channel.recv_exit_status(), stdout_text, stderr_text
        finally:
            client.close()

    def _connect(self, device: Device):
        if device.ssh_port is None:
            raise RemoteConnectionError("设备没有分配 SSH 端口")

        password = self.encryption.decrypt_optional(device.ssh_password_encrypted) or self.settings.ssh_password
        if not password and not self.settings.ssh_key_filename:
            raise RemoteConnectionError("设备没有可用的 SSH 凭据")

        try:
            import paramiko
        except ImportError as exc:
            raise RemoteConnectionError("后端未安装 paramiko，无法建立 SSH 连接") from exc

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.settings.ssh_known_hosts_file:
            try:
                client.load_host_keys(self.settings.ssh_known_hosts_file)
            except OSError as exc:
                raise RemoteConnectionError(f"SSH known_hosts 文件不可用: {exc}") from exc
        if self.settings.ssh_host_key_policy == "reject":
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        elif self.settings.ssh_host_key_policy == "warning":
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.settings.remote_gateway_host,
                port=device.ssh_port,
                username=device.ssh_user,
                password=password,
                key_filename=self.settings.ssh_key_filename,
                passphrase=self.settings.ssh_key_passphrase,
                timeout=self.settings.ssh_timeout_seconds,
                banner_timeout=self.settings.ssh_timeout_seconds,
                auth_timeout=self.settings.ssh_timeout_seconds,
                look_for_keys=False,
                allow_agent=False,
            )
        except paramiko.AuthenticationException as exc:
            client.close()
            raise RemoteAuthenticationError("SSH 认证失败") from exc
        except (paramiko.SSHException, OSError, socket.error) as exc:
            client.close()
            raise RemoteConnectionError(f"SSH 连接失败: {exc}") from exc
        return client
