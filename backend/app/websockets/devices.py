import asyncio
import contextlib
import json

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from app.config import get_settings
from app.database import session_scope
from app.models.device import Device
from app.models.user import User
from app.services.device_service import DeviceNotFoundError, DeviceService
from app.services.operation_log import OperationLogService
from app.services.security import TokenError, decode_token, token_matches_password_version
from app.services.ssh_service import RemoteConnectionError, SshService, SshShellSession
from app.services.vnc_relay import VncRelayService

router = APIRouter(tags=["device-websockets"])


async def _authenticated_user_and_device(websocket: WebSocket, device_id: int) -> tuple[User, Device] | None:
    settings = getattr(websocket.app.state, "settings", get_settings())
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return None
    try:
        payload = decode_token(settings, token, "access")
    except TokenError:
        await websocket.close(code=1008)
        return None

    username = str(payload.get("sub", ""))
    with session_scope(settings) as session:
        user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            await websocket.close(code=1008)
            return None
        if not token_matches_password_version(payload, user.password_changed_at):
            await websocket.close(code=1008)
            return None
        try:
            device = DeviceService(settings).get(session, device_id)
        except DeviceNotFoundError:
            await websocket.close(code=1008)
            return None
        session.expunge(user)
        session.expunge(device)
        return user, device


def _record(websocket: WebSocket, user_id: int, action: str, device_id: int, status: str, detail: str) -> None:
    settings = getattr(websocket.app.state, "settings", get_settings())
    with session_scope(settings) as session:
        OperationLogService(settings).record(
            session,
            user_id=user_id,
            action=action,
            target_type="device",
            target_id=device_id,
            status=status,
            detail=detail,
        )


@router.websocket("/ws/devices/{device_id}/ssh")
async def device_ssh(websocket: WebSocket, device_id: int) -> None:
    auth = await _authenticated_user_and_device(websocket, device_id)
    if auth is None:
        return
    user, device = auth
    settings = getattr(websocket.app.state, "settings", get_settings())
    service = getattr(websocket.app.state, "ssh_service", SshService(settings))

    await websocket.accept()
    shell: SshShellSession | None = None
    output_task: asyncio.Task | None = None
    try:
        _record(websocket, user.id, "remote.ssh.connect", device.id, "started", device.device_sn)
        shell = await asyncio.to_thread(service.open_shell, device)
        await websocket.send_json({"type": "status", "status": "connected"})
        _record(websocket, user.id, "remote.ssh.connect", device.id, "success", device.device_sn)
        output_task = asyncio.create_task(_pump_ssh_output(websocket, shell))
        while True:
            raw_message = await websocket.receive_text()
            message = json.loads(raw_message)
            message_type = message.get("type")
            if message_type == "input":
                await asyncio.to_thread(shell.send, str(message.get("data", "")))
            elif message_type == "resize":
                await asyncio.to_thread(shell.resize, int(message.get("columns", 120)), int(message.get("rows", 32)))
            elif message_type == "close":
                await asyncio.to_thread(shell.close)
                await websocket.send_json({"type": "status", "status": "closed"})
                shell = None
                break
    except RemoteConnectionError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        _record(websocket, user.id, "remote.ssh.connect", device.id, "failed", str(exc))
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "SSH 消息格式无效"})
    except Exception as exc:
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": "SSH 会话已断开"})
        _record(websocket, user.id, "remote.ssh.disconnect", device.id, "closed", str(exc))
    finally:
        if output_task:
            output_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await output_task
        if shell is not None:
            await asyncio.to_thread(shell.close)
        with contextlib.suppress(Exception):
            await websocket.close()


async def _pump_ssh_output(websocket: WebSocket, shell: SshShellSession) -> None:
    while True:
        data = await asyncio.to_thread(shell.recv)
        if data:
            await websocket.send_json({"type": "output", "data": data.decode("utf-8", errors="replace")})
        else:
            await asyncio.sleep(0.05)


@router.websocket("/ws/devices/{device_id}/vnc")
async def device_vnc(websocket: WebSocket, device_id: int) -> None:
    auth = await _authenticated_user_and_device(websocket, device_id)
    if auth is None:
        return
    user, device = auth
    settings = getattr(websocket.app.state, "settings", get_settings())
    service = getattr(websocket.app.state, "vnc_relay_service", VncRelayService(settings))

    await websocket.accept()
    try:
        _record(websocket, user.id, "remote.vnc.connect", device.id, "started", device.device_sn)
        await service.relay(websocket, device)
        _record(websocket, user.id, "remote.vnc.disconnect", device.id, "closed", device.device_sn)
    except Exception as exc:
        _record(websocket, user.id, "remote.vnc.connect", device.id, "failed", str(exc))
        with contextlib.suppress(Exception):
            await websocket.close()
