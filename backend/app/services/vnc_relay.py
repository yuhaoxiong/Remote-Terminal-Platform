import asyncio
import contextlib

from fastapi import WebSocket

from app.config import Settings
from app.models.device import Device


class VncRelayService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def relay(self, websocket: WebSocket, device: Device) -> None:
        if device.vnc_port is None:
            raise RuntimeError("设备没有分配 VNC 端口")

        host = self.settings.vnc_gateway_host or self.settings.remote_gateway_host
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, device.vnc_port),
            timeout=self.settings.vnc_timeout_seconds,
        )
        tcp_to_ws = asyncio.create_task(self._tcp_to_websocket(reader, websocket))
        ws_to_tcp = asyncio.create_task(self._websocket_to_tcp(websocket, writer))
        try:
            done, pending = await asyncio.wait({tcp_to_ws, ws_to_tcp}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _tcp_to_websocket(self, reader: asyncio.StreamReader, websocket: WebSocket) -> None:
        while True:
            data = await reader.read(8192)
            if not data:
                break
            await websocket.send_bytes(data)

    async def _websocket_to_tcp(self, websocket: WebSocket, writer: asyncio.StreamWriter) -> None:
        while True:
            data = await websocket.receive_bytes()
            writer.write(data)
            await writer.drain()
