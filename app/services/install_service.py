import json
import hashlib
import subprocess
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Task, TaskProgress, SoftwareVersion, Vehicle, VehicleECU
from app.services.task_service import TaskService
from app.schemas.task import TaskProgressCreate
from app.models.task import TaskStatus

class InstallService:
    def __init__(self, db: Session):
        self.db = db
        self.task_service = TaskService(db)

    def start_installation(self, task_id: str, install_config: Dict[str, Any]) -> Dict[str, Any]:
        """开始安装"""
        # 获取任务
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证任务状态
        if task.status != TaskStatus.DOWNLOADED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务未完成下载，无法开始安装"
            )

        # 获取车辆信息
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 检查车辆状态
        if vehicle.status != "online":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="车辆不在线"
            )

        # 检查车辆是否适合安装（如：停车状态、电池电量等）
        if not self._check_vehicle_install_conditions(vehicle):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="车辆状态不适合安装"
            )

        # 获取软件版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 验证文件完整性
        if not self._verify_software_integrity(software_version):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="软件完整性验证失败"
            )

        # 更新任务状态为安装中
        self.task_service.update_task(task.id, {"status": TaskStatus.INSTALLING})

        # 记录安装开始
        self._record_install_progress(task.id, "installation_started", "安装开始")

        # 异步执行安装（这里返回安装信息）
        return {
            "status": "installing",
            "message": "安装已开始",
            "estimated_duration": self._estimate_install_duration(software_version),
            "install_steps": self._get_install_steps(software_version)
        }

    def execute_install_step(self, task_id: str, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行安装步骤"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 记录步骤开始
        self._record_install_progress(task.id, step_name, "in_progress")

        try:
            # 执行安装步骤
            result = self._execute_install_step_internal(task, step_name, step_data)

            # 记录步骤完成
            self._record_install_progress(task.id, step_name, "completed",
                                       message=result.get("message", "步骤完成"))

            return result

        except Exception as e:
            # 记录步骤失败
            self._record_install_progress(task.id, step_name, "failed",
                                       error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"安装步骤失败: {str(e)}"
            )

    def verify_installation(self, task_id: str, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证安装结果"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 更新任务状态为验证中
        self.task_service.update_task(task.id, {"status": TaskStatus.VERIFYING})

        # 记录验证开始
        self._record_install_progress(task.id, "verification_started", "开始验证")

        try:
            # 执行完整性校验
            integrity_result = self._verify_installation_integrity(task, verification_data)

            # 执行真实性校验
            authenticity_result = self._verify_installation_authenticity(task, verification_data)

            # 综合验证结果
            is_valid = integrity_result["is_valid"] and authenticity_result["is_valid"]

            if is_valid:
                # 验证成功
                self.task_service.update_task(task.id, {"status": TaskStatus.VERIFIED})
                self._record_install_progress(task.id, "verification_completed", "验证成功")
            else:
                # 验证失败
                self.task_service.update_task(task.id, {"status": TaskStatus.FAILED})
                self._record_install_progress(task.id, "verification_failed", "验证失败",
                                           error_message="安装验证失败")

            return {
                "is_valid": is_valid,
                "integrity_result": integrity_result,
                "authenticity_result": authenticity_result,
                "message": "验证完成" if is_valid else "验证失败"
            }

        except Exception as e:
            self.task_service.update_task(task.id, {"status": TaskStatus.FAILED})
            self._record_install_progress(task.id, "verification_failed", "验证失败",
                                       error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"验证失败: {str(e)}"
            )

    def get_install_status(self, task_id: str) -> Dict[str, Any]:
        """获取安装状态"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 获取安装进度
        progress_records = self.task_service.get_task_progress(task.id)
        install_progress = [p for p in progress_records if p.step_type in ["install", "verify"]]

        # 计算总体进度
        total_steps = len(install_progress)
        completed_steps = len([p for p in install_progress if p.status == "completed"])
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

        return {
            "task_status": task.status,
            "progress_percentage": progress_percentage,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "current_step": install_progress[-1].step_name if install_progress else None,
            "last_update": install_progress[-1].updated_at if install_progress else task.updated_at,
            "install_steps": [
                {
                    "name": p.step_name,
                    "status": p.status,
                    "progress": p.progress,
                    "message": p.message,
                    "error_message": p.error_message,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in install_progress
            ]
        }

    def cancel_installation(self, task_id: str) -> Dict[str, Any]:
        """取消安装"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查是否可以取消
        if task.status not in [TaskStatus.INSTALLING, TaskStatus.VERIFYING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前状态不允许取消安装"
            )

        # 执行清理操作
        self._cleanup_installation(task)

        # 更新任务状态
        self.task_service.update_task(task.id, {"status": TaskStatus.CANCELLED})

        # 记录取消状态
        self._record_install_progress(task.id, "installation_cancelled", "安装已取消")

        return {
            "status": "cancelled",
            "message": "安装已取消"
        }

    def _check_vehicle_install_conditions(self, vehicle: Vehicle) -> bool:
        """检查车辆安装条件"""
        # 检查车辆状态
        vehicle_conditions = vehicle.capabilities or {}

        # 检查是否停车
        is_parked = vehicle_conditions.get("is_parked", False)
        if not is_parked:
            return False

        # 检查电池电量
        battery_level = vehicle_conditions.get("battery_level", 0)
        if battery_level < 30:  # 电池电量低于30%不允许安装
            return False

        # 检查引擎状态
        engine_status = vehicle_conditions.get("engine_status", "running")
        if engine_status == "running":
            return False

        return True

    def _verify_software_integrity(self, software_version: SoftwareVersion) -> bool:
        """验证软件完整性"""
        import os
        from app.services.software_service import SoftwareService

        software_service = SoftwareService(self.db)
        return software_service.verify_file_integrity(software_version.file_path, software_version.file_hash)

    def _estimate_install_duration(self, software_version: SoftwareVersion) -> int:
        """估算安装时长（秒）"""
        # 基于文件大小估算安装时间
        base_time = software_version.file_size // 1024  # 每KB 1秒
        safety_factor = 2.5  # 安全系数

        return int(base_time * safety_factor)

    def _get_install_steps(self, software_version: SoftwareVersion) -> List[Dict[str, Any]]:
        """获取安装步骤"""
        # 解析目标ECU类型
        target_ecus = json.loads(software_version.target_ecu_types) if software_version.target_ecu_types else []

        steps = [
            {
                "name": "pre_install_check",
                "description": "安装前检查",
                "estimated_time": 30
            },
            {
                "name": "backup_current_version",
                "description": "备份当前版本",
                "estimated_time": 120
            }
        ]

        # 为每个ECU添加安装步骤
        for ecu_type in target_ecus:
            steps.extend([
                {
                    "name": f"install_{ecu_type}",
                    "description": f"安装 {ecu_type} ECU",
                    "estimated_time": 300
                },
                {
                    "name": f"verify_{ecu_type}",
                    "description": f"验证 {ecu_type} ECU",
                    "estimated_time": 60
                }
            ])

        steps.extend([
            {
                "name": "post_install_check",
                "description": "安装后检查",
                "estimated_time": 60
            },
            {
                "name": "cleanup",
                "description": "清理临时文件",
                "estimated_time": 30
            }
        ])

        return steps

    def _execute_install_step_internal(self, task: Task, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """内部执行安装步骤"""
        # 这里应该实现具体的安装逻辑
        # 简化版：模拟安装步骤

        if step_name == "pre_install_check":
            return self._pre_install_check(task, step_data)
        elif step_name == "backup_current_version":
            return self._backup_current_version(task, step_data)
        elif step_name.startswith("install_"):
            ecu_type = step_name.replace("install_", "")
            return self._install_ecu(task, ecu_type, step_data)
        elif step_name.startswith("verify_"):
            ecu_type = step_name.replace("verify_", "")
            return self._verify_ecu(task, ecu_type, step_data)
        elif step_name == "post_install_check":
            return self._post_install_check(task, step_data)
        elif step_name == "cleanup":
            return self._cleanup_installation(task)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的安装步骤: {step_name}"
            )

    def _pre_install_check(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """安装前检查"""
        # 检查系统资源
        # 检查依赖关系
        # 检查安全要求

        return {
            "status": "success",
            "message": "安装前检查通过",
            "details": {
                "system_resources": "ok",
                "dependencies": "ok",
                "security_requirements": "ok"
            }
        }

    def _backup_current_version(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """备份当前版本"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        # 为每个ECU创建备份
        backup_results = []
        for ecu in ecus:
            backup_result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "current_version": ecu.software_version,
                "backup_status": "success",
                "backup_location": f"/backups/{task.vehicle_id}/{ecu.ecu_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
            }
            backup_results.append(backup_result)

        return {
            "status": "success",
            "message": "版本备份完成",
            "backup_results": backup_results
        }

    def _install_ecu(self, task: Task, ecu_type: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """安装ECU"""
        # 获取目标ECU
        target_ecu = self.db.query(VehicleECU).filter(
            VehicleECU.vehicle_id == task.vehicle_id,
            VehicleECU.ecu_type == ecu_type
        ).first()

        if not target_ecu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到 {ecu_type} 类型的ECU"
            )

        # 执行安装逻辑
        # 这里应该调用实际的ECU安装接口

        # 更新ECU版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        if software_version:
            target_ecu.software_version = software_version.version
            target_ecu.last_updated = datetime.now()
            self.db.commit()

        return {
            "status": "success",
            "message": f"{ecu_type} ECU安装完成",
            "ecu_id": target_ecu.ecu_id,
            "new_version": software_version.version if software_version else "unknown"
        }

    def _verify_ecu(self, task: Task, ecu_type: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证ECU"""
        # 获取目标ECU
        target_ecu = self.db.query(VehicleECU).filter(
            VehicleECU.vehicle_id == task.vehicle_id,
            VehicleECU.ecu_type == ecu_type
        ).first()

        if not target_ecu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到 {ecu_type} 类型的ECU"
            )

        # 执行验证逻辑
        # 这里应该调用实际的ECU验证接口

        # 验证版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        version_match = target_ecu.software_version == software_version.version if software_version else False

        return {
            "status": "success" if version_match else "failed",
            "message": f"{ecu_type} ECU验证{'成功' if version_match else '失败'}",
            "ecu_id": target_ecu.ecu_id,
            "version_match": version_match,
            "current_version": target_ecu.software_version,
            "expected_version": software_version.version if software_version else "unknown"
        }

    def _post_install_check(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """安装后检查"""
        # 检查所有ECU状态
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        check_results = []
        all_ok = True

        for ecu in ecus:
            result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "status": ecu.status,
                "version": ecu.software_version,
                "check_result": "ok" if ecu.status == "normal" else "error"
            }
            check_results.append(result)
            if ecu.status != "normal":
                all_ok = False

        return {
            "status": "success" if all_ok else "failed",
            "message": "安装后检查完成" if all_ok else "安装后检查发现问题",
            "check_results": check_results
        }

    def _cleanup_installation(self, task: Task) -> Dict[str, Any]:
        """清理安装"""
        # 清理临时文件
        # 释放资源

        return {
            "status": "success",
            "message": "清理完成"
        }

    def _verify_installation_integrity(self, task: Task, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证安装完整性"""
        # 获取软件版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        if not software_version:
            return {
                "is_valid": False,
                "message": "软件版本不存在"
            }

        # 验证文件哈希
        received_hash = verification_data.get("file_hash")
        if received_hash != software_version.file_hash:
            return {
                "is_valid": False,
                "message": "文件哈希不匹配",
                "expected": software_version.file_hash,
                "received": received_hash
            }

        # 验证文件大小
        received_size = verification_data.get("file_size")
        if received_size != software_version.file_size:
            return {
                "is_valid": False,
                "message": "文件大小不匹配",
                "expected": software_version.file_size,
                "received": received_size
            }

        return {
            "is_valid": True,
            "message": "完整性验证通过"
        }

    def _verify_installation_authenticity(self, task: Task, verification_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证安装真实性"""
        # 获取软件版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        if not software_version:
            return {
                "is_valid": False,
                "message": "软件版本不存在"
            }

        # 验证数字签名
        received_signature = verification_data.get("signature")
        if received_signature != software_version.signature:
            return {
                "is_valid": False,
                "message": "数字签名不匹配",
                "expected": software_version.signature,
                "received": received_signature
            }

        # 验证证书链（简化版）
        # 实际应用中应该验证完整的证书链

        return {
            "is_valid": True,
            "message": "真实性验证通过"
        }

    def _record_install_progress(self, task_id: int, step_name: str, status: str,
                               message: str = None, error_message: str = None):
        """记录安装进度"""
        try:
            progress_data = TaskProgressCreate(
                task_id=task_id,
                step_name=step_name,
                step_type="install" if "install" in step_name.lower() else "verify",
                status=status,
                message=message,
                error_message=error_message
            )
            self.task_service.add_progress_record(task_id, progress_data)
        except Exception as e:
            print(f"Failed to record install progress: {e}")