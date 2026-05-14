from app.database import session_scope
from app.models.log import OperationLog
from app.services.operation_log import OperationLogService


def test_operation_log_service_records_action(initialized_settings) -> None:
    service = OperationLogService(initialized_settings)

    with session_scope(initialized_settings) as session:
        log = service.record(
            session,
            user_id=1,
            action="auth.login",
            target_type="user",
            target_id=1,
            status="success",
            detail="admin logged in",
        )
        log_id = log.id

    with session_scope(initialized_settings) as session:
        stored = session.get(OperationLog, log_id)

    assert stored is not None
    assert stored.action == "auth.login"
    assert stored.status == "success"
