from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    INSTALLING = "installing"
    INSTALLED = "installed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    ACTIVATING = "activating"
    ACTIVATED = "activated"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"
    COMPLETED = "completed"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, nullable=False, index=True)  # 任务ID
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    software_version_id = Column(Integer, ForeignKey("software_versions.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default=TaskStatus.PENDING)
    priority = Column(String(20), default=TaskPriority.MEDIUM)
    schedule_time = Column(DateTime)  # 计划执行时间
    start_time = Column(DateTime)  # 实际开始时间
    end_time = Column(DateTime)  # 实际结束时间
    timeout = Column(Integer)  # 超时时间（秒）
    retry_count = Column(Integer, default=0)
    max_retry = Column(Integer, default=3)
    configuration = Column(JSON)  # 任务配置参数
    requirements = Column(JSON)  # 执行要求
    security_checks = Column(JSON)  # 安全检查要求
    rollback_strategy = Column(JSON)  # 回滚策略
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)

    # 关联关系
    vehicle = relationship("Vehicle", back_populates="tasks")
    software_version = relationship("SoftwareVersion", back_populates="task_versions")
    creator = relationship("User", back_populates="tasks_created")
    progress = relationship("TaskProgress", back_populates="task", cascade="all, delete-orphan")

class TaskProgress(Base):
    __tablename__ = "task_progress"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    step_name = Column(String(100), nullable=False)
    step_type = Column(String(50), nullable=False)  # download, install, verify, activate, rollback
    status = Column(String(50), nullable=False)
    progress = Column(Integer, default=0)  # 0-100
    message = Column(Text)
    error_message = Column(Text)
    error_code = Column(String(50))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    details = Column(JSON)  # 详细信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关联关系
    task = relationship("Task", back_populates="progress")