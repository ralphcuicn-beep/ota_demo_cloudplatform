from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.software import SoftwareType, SoftwareStatus

class SoftwareBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    software_type: SoftwareType = SoftwareType.SOFTWARE
    vendor: Optional[str] = None
    category: Optional[str] = None

class SoftwareCreate(SoftwareBase):
    pass

class SoftwareUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class SoftwareResponse(SoftwareBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    is_active: bool
    versions_count: int = 0

    class Config:
        from_attributes = True

class SoftwareVersionBase(BaseModel):
    version: str = Field(..., min_length=1, max_length=100)
    version_code: Optional[str] = None
    release_notes: Optional[str] = None
    min_supported_version: Optional[str] = None
    max_supported_version: Optional[str] = None
    target_ecu_types: Optional[List[str]] = None
    security_requirements: Optional[Dict[str, Any]] = None
    rollback_info: Optional[Dict[str, Any]] = None

class SoftwareVersionCreate(SoftwareVersionBase):
    pass

class SoftwareVersionUpdate(BaseModel):
    version: Optional[str] = Field(None, min_length=1, max_length=100)
    version_code: Optional[str] = None
    release_notes: Optional[str] = None
    status: Optional[SoftwareStatus] = None
    min_supported_version: Optional[str] = None
    max_supported_version: Optional[str] = None
    target_ecu_types: Optional[List[str]] = None
    security_requirements: Optional[Dict[str, Any]] = None
    rollback_info: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class SoftwareVersionResponse(SoftwareVersionBase):
    id: int
    software_id: int
    file_path: str
    file_name: str
    file_size: int
    file_hash: str
    signature: Optional[str]
    status: SoftwareStatus
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    download_count: int
    is_active: bool
    software_name: Optional[str] = None

    @validator('target_ecu_types', pre=True)
    def parse_ecu_types(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @validator('security_requirements', pre=True)
    def parse_security_requirements(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @validator('rollback_info', pre=True)
    def parse_rollback_info(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    class Config:
        from_attributes = True