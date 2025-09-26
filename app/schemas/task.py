from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.task import TaskStatus, TaskPriority

class TaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    schedule_time: Optional[datetime] = None
    timeout: Optional[int] = None
    max_retry: int = Field(default=3, ge=1, le=10)
    configuration: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    security_checks: Optional[Dict[str, Any]] = None
    rollback_strategy: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    vehicle_id: int
    software_version_id: int

class TaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    schedule_time: Optional[datetime] = None
    timeout: Optional[int] = None
    max_retry: Optional[int] = Field(None, ge=1, le=10)
    configuration: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    security_checks: Optional[Dict[str, Any]] = None
    rollback_strategy: Optional[Dict[str, Any]] = None

class TaskResponse(TaskBase):
    id: int
    task_id: str
    vehicle_id: int
    software_version_id: int
    status: TaskStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    is_active: bool
    vehicle_vin: Optional[str] = None
    software_version_name: Optional[str] = None

    class Config:
        from_attributes = True

class TaskProgressBase(BaseModel):
    step_name: str = Field(..., min_length=1, max_length=100)
    step_type: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., min_length=1, max_length=50)
    progress: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class TaskProgressCreate(TaskProgressBase):
    task_id: int

class TaskProgressResponse(TaskProgressBase):
    id: int
    task_id: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True