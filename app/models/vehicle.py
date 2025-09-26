from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from enum import Enum

class VehicleStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UPDATING = "updating"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class ECUType(str, Enum):
    POWERTRAIN = "powertrain"
    BODY = "body"
    CHASSIS = "chassis"
    INFOTAINMENT = "infotainment"
    ADAS = "adas"
    OTHER = "other"

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), unique=True, nullable=False, index=True)  # 车辆识别码
    license_plate = Column(String(50))
    brand = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    owner = Column(String(255))
    status = Column(String(50), default=VehicleStatus.OFFLINE)
    last_heartbeat = Column(DateTime)
    software_version_info = Column(JSON)  # 当前软件版本信息
    capabilities = Column(JSON)  # 车辆能力信息
    location = Column(JSON)  # 位置信息
    network_info = Column(JSON)  # 网络信息
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # 关联关系
    ecus = relationship("VehicleECU", back_populates="vehicle", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="vehicle")

class VehicleECU(Base):
    __tablename__ = "vehicle_ecus"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    ecu_id = Column(String(100), nullable=False)  # ECU唯一标识
    ecu_type = Column(String(50), nullable=False, default=ECUType.OTHER)
    name = Column(String(255))
    manufacturer = Column(String(255))
    part_number = Column(String(100))
    serial_number = Column(String(100))
    hardware_version = Column(String(50))
    software_version = Column(String(50))
    firmware_version = Column(String(50))
    location = Column(String(100))  # ECU在车辆中的位置
    communication_protocol = Column(String(50))  # 通信协议
    capabilities = Column(JSON)  # ECU能力
    status = Column(String(50), default="normal")
    last_updated = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)

    # 关联关系
    vehicle = relationship("Vehicle", back_populates="ecus")