import json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models import Vehicle, VehicleECU, Task, TaskProgress
from app.models.vehicle import VehicleStatus
from app.models.task import TaskStatus
from app.services.task_service import TaskService
from app.schemas.task import TaskProgressCreate
from app.core.config import settings

class StatusService:
    def __init__(self, db: Session):
        self.db = db
        self.task_service = TaskService(db)

    def report_vehicle_status(self, vin: str, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """上报车辆状态"""
        # 获取车辆
        vehicle = self.db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 更新车辆基本信息
        vehicle.status = status_data.get("vehicle_status", vehicle.status)
        vehicle.last_heartbeat = datetime.now()

        # 更新软件版本信息
        if "software_version_info" in status_data:
            vehicle.software_version_info = status_data["software_version_info"]

        # 更新车辆能力
        if "capabilities" in status_data:
            vehicle.capabilities = status_data["capabilities"]

        # 更新位置信息
        if "location" in status_data:
            vehicle.location = status_data["location"]

        # 更新网络信息
        if "network_info" in status_data:
            vehicle.network_info = status_data["network_info"]

        self.db.commit()

        # 更新ECU状态
        if "ecu_status" in status_data:
            self._update_ecu_status(vehicle.id, status_data["ecu_status"])

        # 检查并更新相关任务状态
        self._update_task_status_from_vehicle(vehicle.id, status_data)

        return {
            "status": "success",
            "message": "车辆状态更新成功",
            "updated_at": vehicle.last_heartbeat.isoformat()
        }

    def report_ecu_status(self, vin: str, ecu_id: str, ecu_status: Dict[str, Any]) -> Dict[str, Any]:
        """上报ECU状态"""
        # 获取车辆
        vehicle = self.db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 获取ECU
        ecu = self.db.query(VehicleECU).filter(
            VehicleECU.vehicle_id == vehicle.id,
            VehicleECU.ecu_id == ecu_id
        ).first()

        if not ecu:
            # 如果ECU不存在，创建新的ECU记录
            ecu = VehicleECU(
                vehicle_id=vehicle.id,
                ecu_id=ecu_id,
                ecu_type=ecu_status.get("ecu_type", "other"),
                name=ecu_status.get("name"),
                manufacturer=ecu_status.get("manufacturer"),
                part_number=ecu_status.get("part_number"),
                serial_number=ecu_status.get("serial_number"),
                hardware_version=ecu_status.get("hardware_version"),
                software_version=ecu_status.get("software_version"),
                firmware_version=ecu_status.get("firmware_version"),
                location=ecu_status.get("location"),
                communication_protocol=ecu_status.get("communication_protocol"),
                capabilities=ecu_status.get("capabilities"),
                status=ecu_status.get("status", "normal"),
                last_updated=datetime.now()
            )
            self.db.add(ecu)
        else:
            # 更新现有ECU信息
            ecu.software_version = ecu_status.get("software_version", ecu.software_version)
            ecu.firmware_version = ecu_status.get("firmware_version", ecu.firmware_version)
            ecu.status = ecu_status.get("status", ecu.status)
            ecu.capabilities = ecu_status.get("capabilities", ecu.capabilities)
            ecu.last_updated = datetime.now()

        self.db.commit()

        return {
            "status": "success",
            "message": "ECU状态更新成功",
            "ecu_id": ecu.ecu_id,
            "updated_at": ecu.last_updated.isoformat()
        }

    def report_task_progress(self, task_id: str, progress_data: Dict[str, Any]) -> Dict[str, Any]:
        """上报任务进度"""
        # 获取任务
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 记录进度
        progress_record = TaskProgressCreate(
            task_id=task.id,
            step_name=progress_data.get("step_name", "unknown"),
            step_type=progress_data.get("step_type", "general"),
            status=progress_data.get("status", "unknown"),
            progress=progress_data.get("progress", 0),
            message=progress_data.get("message"),
            error_message=progress_data.get("error_message"),
            error_code=progress_data.get("error_code"),
            details=progress_data.get("details")
        )

        self.task_service.add_progress_record(task.id, progress_record)

        # 如果进度状态异常，更新任务状态
        if progress_data.get("status") in ["failed", "error"]:
            self.task_service.update_task(task.id, {"status": TaskStatus.FAILED})

        return {
            "status": "success",
            "message": "任务进度上报成功",
            "task_id": task.task_id,
            "progress_id": progress_record.task_id
        }

    def report_heartbeat(self, vin: str, heartbeat_data: Dict[str, Any]) -> Dict[str, Any]:
        """上报心跳"""
        # 获取车辆
        vehicle = self.db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 更新心跳时间
        vehicle.last_heartbeat = datetime.now()

        # 更新车辆状态为在线
        if vehicle.status != VehicleStatus.UPDATING:
            vehicle.status = VehicleStatus.ONLINE

        # 更新其他信息
        if "network_info" in heartbeat_data:
            vehicle.network_info = heartbeat_data["network_info"]

        if "location" in heartbeat_data:
            vehicle.location = heartbeat_data["location"]

        self.db.commit()

        return {
            "status": "success",
            "message": "心跳上报成功",
            "next_heartbeat_interval": settings.VEHICLE_HEARTBEAT_TIMEOUT
        }

    def get_vehicle_status(self, vin: str) -> Dict[str, Any]:
        """获取车辆状态"""
        vehicle = self.db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 获取ECU状态
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == vehicle.id).all()

        # 获取活跃任务
        active_task = self.task_service.get_vehicle_active_task(vehicle.id)

        return {
            "vehicle": {
                "vin": vehicle.vin,
                "status": vehicle.status,
                "last_heartbeat": vehicle.last_heartbeat.isoformat() if vehicle.last_heartbeat else None,
                "software_version_info": vehicle.software_version_info,
                "capabilities": vehicle.capabilities,
                "location": vehicle.location,
                "network_info": vehicle.network_info
            },
            "ecus": [
                {
                    "ecu_id": ecu.ecu_id,
                    "ecu_type": ecu.ecu_type,
                    "name": ecu.name,
                    "manufacturer": ecu.manufacturer,
                    "software_version": ecu.software_version,
                    "firmware_version": ecu.firmware_version,
                    "status": ecu.status,
                    "last_updated": ecu.last_updated.isoformat(),
                    "capabilities": ecu.capabilities
                }
                for ecu in ecus
            ],
            "active_task": {
                "task_id": active_task.task_id,
                "status": active_task.status,
                "name": active_task.name,
                "created_at": active_task.created_at.isoformat()
            } if active_task else None
        }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 获取任务进度
        progress_records = self.task_service.get_task_progress(task.id)

        # 获取车辆信息
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()

        return {
            "task": {
                "task_id": task.task_id,
                "name": task.name,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "start_time": task.start_time.isoformat() if task.start_time else None,
                "end_time": task.end_time.isoformat() if task.end_time else None,
                "retry_count": task.retry_count,
                "max_retry": task.max_retry,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            },
            "vehicle": {
                "vin": vehicle.vin if vehicle else None,
                "status": vehicle.status if vehicle else None
            },
            "progress": [
                {
                    "step_name": p.step_name,
                    "step_type": p.step_type,
                    "status": p.status,
                    "progress": p.progress,
                    "message": p.message,
                    "error_message": p.error_message,
                    "error_code": p.error_code,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat()
                }
                for p in progress_records
            ]
        }

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        # 统计车辆状态
        vehicle_stats = self._get_vehicle_statistics()

        # 统计任务状态
        task_stats = self._get_task_statistics()

        # 检查超时任务
        timeout_tasks = self.task_service.get_timeout_tasks()

        return {
            "system_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "vehicles": vehicle_stats,
                "tasks": task_stats,
                "timeout_tasks": len(timeout_tasks)
            },
            "alerts": self._generate_system_alerts(vehicle_stats, task_stats, timeout_tasks)
        }

    def check_offline_vehicles(self) -> List[Dict[str, Any]]:
        """检查离线车辆"""
        timeout_time = datetime.now() - timedelta(seconds=settings.VEHICLE_HEARTBEAT_TIMEOUT)

        offline_vehicles = self.db.query(Vehicle).filter(
            Vehicle.last_heartbeat < timeout_time,
            Vehicle.status != VehicleStatus.OFFLINE
        ).all()

        offline_list = []
        for vehicle in offline_vehicles:
            # 更新车辆状态为离线
            vehicle.status = VehicleStatus.OFFLINE
            offline_list.append({
                "vin": vehicle.vin,
                "last_heartbeat": vehicle.last_heartbeat.isoformat(),
                "previous_status": vehicle.status
            })

        self.db.commit()
        return offline_list

    def _update_ecu_status(self, vehicle_id: int, ecu_status_list: List[Dict[str, Any]]) -> None:
        """更新ECU状态"""
        for ecu_status in ecu_status_list:
            ecu_id = ecu_status.get("ecu_id")
            if not ecu_id:
                continue

            ecu = self.db.query(VehicleECU).filter(
                VehicleECU.vehicle_id == vehicle_id,
                VehicleECU.ecu_id == ecu_id
            ).first()

            if ecu:
                # 更新现有ECU
                ecu.software_version = ecu_status.get("software_version", ecu.software_version)
                ecu.firmware_version = ecu_status.get("firmware_version", ecu.firmware_version)
                ecu.status = ecu_status.get("status", ecu.status)
                ecu.capabilities = ecu_status.get("capabilities", ecu.capabilities)
                ecu.last_updated = datetime.now()
            else:
                # 创建新ECU
                new_ecu = VehicleECU(
                    vehicle_id=vehicle_id,
                    ecu_id=ecu_id,
                    ecu_type=ecu_status.get("ecu_type", "other"),
                    name=ecu_status.get("name"),
                    manufacturer=ecu_status.get("manufacturer"),
                    software_version=ecu_status.get("software_version"),
                    firmware_version=ecu_status.get("firmware_version"),
                    status=ecu_status.get("status", "normal"),
                    last_updated=datetime.now()
                )
                self.db.add(new_ecu)

        self.db.commit()

    def _update_task_status_from_vehicle(self, vehicle_id: int, status_data: Dict[str, Any]) -> None:
        """根据车辆状态更新任务状态"""
        # 获取车辆的活跃任务
        active_task = self.task_service.get_vehicle_active_task(vehicle_id)
        if not active_task:
            return

        # 如果车辆离线且有进行中的任务，标记任务为失败
        if status_data.get("vehicle_status") == VehicleStatus.OFFLINE:
            if active_task.status in [TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING,
                                    TaskStatus.INSTALLING, TaskStatus.VERIFYING, TaskStatus.ACTIVATING]:
                self.task_service.update_task(active_task.id, {"status": TaskStatus.FAILED})

                # 记录失败原因
                progress_data = TaskProgressCreate(
                    task_id=active_task.id,
                    step_name="vehicle_offline",
                    step_type="system",
                    status="failed",
                    message="车辆离线导致任务失败",
                    error_message="车辆失去连接"
                )
                self.task_service.add_progress_record(active_task.id, progress_data)

    def _get_vehicle_statistics(self) -> Dict[str, int]:
        """获取车辆统计信息"""
        total = self.db.query(Vehicle).count()
        online = self.db.query(Vehicle).filter(Vehicle.status == VehicleStatus.ONLINE).count()
        offline = self.db.query(Vehicle).filter(Vehicle.status == VehicleStatus.OFFLINE).count()
        updating = self.db.query(Vehicle).filter(Vehicle.status == VehicleStatus.UPDATING).count()
        error = self.db.query(Vehicle).filter(Vehicle.status == VehicleStatus.ERROR).count()

        return {
            "total": total,
            "online": online,
            "offline": offline,
            "updating": updating,
            "error": error
        }

    def _get_task_statistics(self) -> Dict[str, int]:
        """获取任务统计信息"""
        total = self.db.query(Task).count()
        pending = self.db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
        running = self.db.query(Task).filter(
            Task.status.in_([TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING,
                           TaskStatus.INSTALLING, TaskStatus.VERIFYING, TaskStatus.ACTIVATING])
        ).count()
        completed = self.db.query(Task).filter(Task.status == TaskStatus.COMPLETED).count()
        failed = self.db.query(Task).filter(Task.status == TaskStatus.FAILED).count()

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed
        }

    def _generate_system_alerts(self, vehicle_stats: Dict[str, int],
                               task_stats: Dict[str, int],
                               timeout_tasks: List[Task]) -> List[Dict[str, Any]]:
        """生成系统告警"""
        alerts = []

        # 离线车辆告警
        if vehicle_stats["offline"] > 0:
            alerts.append({
                "type": "warning",
                "category": "vehicle",
                "message": f"有 {vehicle_stats['offline']} 辆车辆离线",
                "severity": "medium"
            })

        # 失败任务告警
        if task_stats["failed"] > 0:
            alerts.append({
                "type": "error",
                "category": "task",
                "message": f"有 {task_stats['failed']} 个任务失败",
                "severity": "high"
            })

        # 超时任务告警
        if len(timeout_tasks) > 0:
            alerts.append({
                "type": "error",
                "category": "task",
                "message": f"有 {len(timeout_tasks)} 个任务超时",
                "severity": "high"
            })

        # 错误车辆告警
        if vehicle_stats["error"] > 0:
            alerts.append({
                "type": "error",
                "category": "vehicle",
                "message": f"有 {vehicle_stats['error']} 辆车辆处于错误状态",
                "severity": "high"
            })

        return alerts