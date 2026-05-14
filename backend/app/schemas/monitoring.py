from pydantic import BaseModel


class MonitoringOverviewResponse(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    unknown_devices: int

