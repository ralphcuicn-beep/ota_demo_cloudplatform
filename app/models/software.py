from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, LargeBinary, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from enum import Enum

class SoftwareType(str, Enum):
    FIRMWARE = "firmware"
    SOFTWARE = "software"
    CONFIG = "config"

class SoftwareStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"

class Software(Base):
    __tablename__ = "software"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    software_type = Column(String(50), nullable=False, default=SoftwareType.SOFTWARE)
    vendor = Column(String(255))
    category = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)

    # 关联关系
    versions = relationship("SoftwareVersion", back_populates="software", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="software_created")

class SoftwareVersion(Base):
    __tablename__ = "software_versions"

    id = Column(Integer, primary_key=True, index=True)
    software_id = Column(Integer, ForeignKey("software.id"), nullable=False)
    version = Column(String(100), nullable=False)
    version_code = Column(String(50))
    release_notes = Column(Text)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(256), nullable=False)  # SHA-256 hash
    signature = Column(Text)  # 数字签名
    status = Column(String(50), default=SoftwareStatus.DRAFT)
    min_supported_version = Column(String(50))
    max_supported_version = Column(String(50))
    target_ecu_types = Column(Text)  # JSON格式的ECU类型列表
    security_requirements = Column(Text)  # JSON格式的安全要求
    rollback_info = Column(Text)  # JSON格式的回滚信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    download_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # 关联关系
    software = relationship("Software", back_populates="versions")
    creator = relationship("User", back_populates="versions_created")
    task_versions = relationship("Task", back_populates="software_version")

    @property
    def full_version(self):
        return f"{self.software.name} v{self.version}"