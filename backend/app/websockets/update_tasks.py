from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from app.config import get_settings
from app.database import session_scope
from app.models.user import User
from app.services.security import TokenError, decode_token
from app.services.update_task_service import UpdateTaskNotFoundError, UpdateTaskService

router = APIRouter(tags=["update-task-websockets"])


@router.websocket("/ws/update-tasks/{task_id}")
async def update_task_progress(websocket: WebSocket, task_id: int) -> None:
    settings = getattr(websocket.app.state, "settings", get_settings())
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = decode_token(settings, token, "access")
    except TokenError:
        await websocket.close(code=1008)
        return

    username = str(payload.get("sub", ""))
    service = UpdateTaskService(settings)
    with session_scope(settings) as session:
        user = session.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
        if user is None:
            await websocket.close(code=1008)
            return
        try:
            task = service.to_read(session, service.get(session, task_id))
        except UpdateTaskNotFoundError:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    await websocket.send_json({"type": "task.snapshot", "task": task.model_dump(mode="json")})
    await websocket.close()
