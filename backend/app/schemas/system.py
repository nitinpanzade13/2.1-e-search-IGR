from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional

class NetworkConfigBase(BaseModel):
    profile_name: str
    interface_name: str = "Wi-Fi"
    priority: int = 10
    is_enabled: bool = True
    connection_timeout: int = 30
    validation_timeout: int = 10

class NetworkConfigCreate(NetworkConfigBase):
    pass

class NetworkConfigUpdate(BaseModel):
    profile_name: Optional[str] = None
    interface_name: Optional[str] = None
    priority: Optional[int] = None
    is_enabled: Optional[bool] = None
    connection_timeout: Optional[int] = None
    validation_timeout: Optional[int] = None

class NetworkConfigResponse(NetworkConfigBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
