import pytest

from app.database import session_scope
from app.services.port_pool import PortPoolExhaustedError, PortPoolService


def test_port_pool_allocates_lowest_available_port_and_reuses_released_port(initialized_settings) -> None:
    service = PortPoolService(initialized_settings)

    with session_scope(initialized_settings) as session:
        ssh_port = service.allocate(session, "ssh", device_id=1)
        next_ssh_port = service.allocate(session, "ssh", device_id=2)
        service.release(session, "ssh", ssh_port)
        reused_port = service.allocate(session, "ssh", device_id=3)

    assert ssh_port == 10000
    assert next_ssh_port == 10001
    assert reused_port == 10000


def test_port_pool_raises_when_service_type_is_exhausted(settings) -> None:
    settings.ssh_port_start = 10000
    settings.ssh_port_end = 10000
    service = PortPoolService(settings)
    service.initialize()

    with session_scope(settings) as session:
        service.allocate(session, "ssh", device_id=1)
        with pytest.raises(PortPoolExhaustedError):
            service.allocate(session, "ssh", device_id=2)
