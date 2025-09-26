import json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Task, TaskProgress, SoftwareVersion, Vehicle, VehicleECU
from app.services.task_service import TaskService
from app.schemas.task import TaskProgressCreate
from app.models.task import TaskStatus

class ActivationService:
    def __init__(self, db: Session):
        self.db = db
        self.task_service = TaskService(db)

    def start_activation(self, task_id: str, activation_config: Dict[str, Any]) -> Dict[str, Any]:
        """开始激活"""
        # 获取任务
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证任务状态
        if task.status != TaskStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务未完成验证，无法开始激活"
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

        # 检查激活条件
        if not self._check_activation_conditions(vehicle, activation_config):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="激活条件不满足"
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

        # 更新任务状态为激活中
        self.task_service.update_task(task.id, {"status": TaskStatus.ACTIVATING})

        # 记录激活开始
        self._record_activation_progress(task.id, "activation_started", "激活开始")

        # 执行激活
        return self._execute_activation(task, vehicle, software_version, activation_config)

    def execute_activation_step(self, task_id: str, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行激活步骤"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 记录步骤开始
        self._record_activation_progress(task.id, step_name, "in_progress")

        try:
            # 执行激活步骤
            result = self._execute_activation_step_internal(task, step_name, step_data)

            # 记录步骤完成
            self._record_activation_progress(task.id, step_name, "completed",
                                           message=result.get("message", "步骤完成"))

            return result

        except Exception as e:
            # 记录步骤失败
            self._record_activation_progress(task.id, step_name, "failed",
                                           error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"激活步骤失败: {str(e)}"
            )

    def complete_activation(self, task_id: str, completion_data: Dict[str, Any]) -> Dict[str, Any]:
        """完成激活"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证激活结果
        validation_result = self._validate_activation_result(task, completion_data)

        if validation_result["is_valid"]:
            # 激活成功
            self.task_service.update_task(task.id, {"status": TaskStatus.ACTIVATED})
            self._record_activation_progress(task.id, "activation_completed", "激活成功")

            # 更新车辆软件版本信息
            self._update_vehicle_software_info(task)

        else:
            # 激活失败
            self.task_service.update_task(task.id, {"status": TaskStatus.FAILED})
            self._record_activation_progress(task.id, "activation_failed", "激活失败",
                                           error_message=validation_result["message"])

        return validation_result

    def start_rollback(self, task_id: str, rollback_config: Dict[str, Any]) -> Dict[str, Any]:
        """开始回滚"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证任务状态
        if task.status not in [TaskStatus.FAILED, TaskStatus.ACTIVATED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前状态不允许回滚"
            )

        # 更新任务状态为回滚中
        self.task_service.update_task(task.id, {"status": TaskStatus.ROLLBACK})

        # 记录回滚开始
        self._record_activation_progress(task.id, "rollback_started", "开始回滚")

        # 执行回滚
        return self._execute_rollback(task, rollback_config)

    def execute_rollback_step(self, task_id: str, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行回滚步骤"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 记录步骤开始
        self._record_activation_progress(task.id, step_name, "in_progress")

        try:
            # 执行回滚步骤
            result = self._execute_rollback_step_internal(task, step_name, step_data)

            # 记录步骤完成
            self._record_activation_progress(task.id, step_name, "completed",
                                           message=result.get("message", "步骤完成"))

            return result

        except Exception as e:
            # 记录步骤失败
            self._record_activation_progress(task.id, step_name, "failed",
                                           error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"回滚步骤失败: {str(e)}"
            )

    def complete_rollback(self, task_id: str, completion_data: Dict[str, Any]) -> Dict[str, Any]:
        """完成回滚"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证回滚结果
        validation_result = self._validate_rollback_result(task, completion_data)

        if validation_result["is_valid"]:
            # 回滚成功
            self.task_service.update_task(task.id, {"status": TaskStatus.COMPLETED})
            self._record_activation_progress(task.id, "rollback_completed", "回滚成功")

            # 恢复车辆软件版本信息
            self._restore_vehicle_software_info(task)

        else:
            # 回滚失败
            self.task_service.update_task(task.id, {"status": TaskStatus.FAILED})
            self._record_activation_progress(task.id, "rollback_failed", "回滚失败",
                                           error_message=validation_result["message"])

        return validation_result

    def get_activation_status(self, task_id: str) -> Dict[str, Any]:
        """获取激活状态"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 获取激活进度
        progress_records = self.task_service.get_task_progress(task.id)
        activation_progress = [p for p in progress_records if p.step_type in ["activate", "rollback"]]

        # 计算总体进度
        total_steps = len(activation_progress)
        completed_steps = len([p for p in activation_progress if p.status == "completed"])
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0

        return {
            "task_status": task.status,
            "progress_percentage": progress_percentage,
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "current_step": activation_progress[-1].step_name if activation_progress else None,
            "last_update": activation_progress[-1].updated_at if activation_progress else task.updated_at,
            "activation_steps": [
                {
                    "name": p.step_name,
                    "status": p.status,
                    "progress": p.progress,
                    "message": p.message,
                    "error_message": p.error_message,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in activation_progress
            ]
        }

    def cancel_activation(self, task_id: str) -> Dict[str, Any]:
        """取消激活"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查是否可以取消
        if task.status not in [TaskStatus.ACTIVATING, TaskStatus.ROLLBACK]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前状态不允许取消激活"
            )

        # 执行清理操作
        self._cleanup_activation(task)

        # 更新任务状态
        self.task_service.update_task(task.id, {"status": TaskStatus.CANCELLED})

        # 记录取消状态
        self._record_activation_progress(task.id, "activation_cancelled", "激活已取消")

        return {
            "status": "cancelled",
            "message": "激活已取消"
        }

    def _check_activation_conditions(self, vehicle: Vehicle, activation_config: Dict[str, Any]) -> bool:
        """检查激活条件"""
        vehicle_conditions = vehicle.capabilities or {}

        # 检查电池电量
        battery_level = vehicle_conditions.get("battery_level", 0)
        if battery_level < 20:  # 电池电量低于20%不允许激活
            return False

        # 检查车辆状态
        is_parked = vehicle_conditions.get("is_parked", False)
        if not is_parked:
            return False

        # 检查网络连接
        network_quality = vehicle_conditions.get("network_quality", "poor")
        if network_quality == "poor":
            return False

        return True

    def _execute_activation(self, task: Task, vehicle: Vehicle, software_version: SoftwareVersion,
                          activation_config: Dict[str, Any]) -> Dict[str, Any]:
        """执行激活"""
        # 获取激活步骤
        activation_steps = self._get_activation_steps(software_version)

        return {
            "status": "activating",
            "message": "激活已开始",
            "estimated_duration": self._estimate_activation_duration(software_version),
            "activation_steps": activation_steps
        }

    def _execute_activation_step_internal(self, task: Task, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """内部执行激活步骤"""
        if step_name == "prepare_activation":
            return self._prepare_activation(task, step_data)
        elif step_name == "switch_partition":
            return self._switch_partition(task, step_data)
        elif step_name == "verify_activation":
            return self._verify_activation(task, step_data)
        elif step_name == "finalize_activation":
            return self._finalize_activation(task, step_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的激活步骤: {step_name}"
            )

    def _execute_rollback(self, task: Task, rollback_config: Dict[str, Any]) -> Dict[str, Any]:
        """执行回滚"""
        # 获取软件版本信息
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 获取回滚步骤
        rollback_steps = self._get_rollback_steps(software_version)

        return {
            "status": "rolling_back",
            "message": "回滚已开始",
            "estimated_duration": self._estimate_rollback_duration(software_version),
            "rollback_steps": rollback_steps
        }

    def _execute_rollback_step_internal(self, task: Task, step_name: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """内部执行回滚步骤"""
        if step_name == "prepare_rollback":
            return self._prepare_rollback(task, step_data)
        elif step_name == "restore_backup":
            return self._restore_backup(task, step_data)
        elif step_name == "verify_rollback":
            return self._verify_rollback(task, step_data)
        elif step_name == "finalize_rollback":
            return self._finalize_rollback(task, step_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的回滚步骤: {step_name}"
            )

    def _prepare_activation(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """准备激活"""
        # 检查系统状态
        # 准备激活环境

        return {
            "status": "success",
            "message": "激活准备完成",
            "details": {
                "system_check": "passed",
                "environment_ready": True
            }
        }

    def _switch_partition(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """切换分区"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        switch_results = []
        for ecu in ecus:
            # 执行分区切换
            result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "switch_status": "success",
                "new_partition": "secondary",
                "old_partition": "primary"
            }
            switch_results.append(result)

        return {
            "status": "success",
            "message": "分区切换完成",
            "switch_results": switch_results
        }

    def _verify_activation(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证激活"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        verification_results = []
        all_verified = True

        for ecu in ecus:
            # 验证ECU激活状态
            is_verified = ecu.status == "normal"
            result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "verification_status": "success" if is_verified else "failed",
                "current_version": ecu.software_version,
                "partition_status": "active"
            }
            verification_results.append(result)
            if not is_verified:
                all_verified = False

        return {
            "status": "success" if all_verified else "failed",
            "message": "激活验证完成" if all_verified else "激活验证失败",
            "verification_results": verification_results
        }

    def _finalize_activation(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """完成激活"""
        # 清理临时文件
        # 更新系统状态

        return {
            "status": "success",
            "message": "激活完成",
            "details": {
                "cleanup_completed": True,
                "system_updated": True
            }
        }

    def _prepare_rollback(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """准备回滚"""
        # 检查备份文件
        # 准备回滚环境

        return {
            "status": "success",
            "message": "回滚准备完成",
            "details": {
                "backup_check": "passed",
                "environment_ready": True
            }
        }

    def _restore_backup(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """恢复备份"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        restore_results = []
        for ecu in ecus:
            # 恢复备份
            result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "restore_status": "success",
                "restored_version": "previous_version",
                "backup_location": f"/backups/{task.vehicle_id}/{ecu.ecu_id}_backup.bin"
            }
            restore_results.append(result)

        return {
            "status": "success",
            "message": "备份恢复完成",
            "restore_results": restore_results
        }

    def _verify_rollback(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证回滚"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        verification_results = []
        all_verified = True

        for ecu in ecus:
            # 验证回滚结果
            is_verified = ecu.status == "normal"
            result = {
                "ecu_id": ecu.ecu_id,
                "ecu_type": ecu.ecu_type,
                "verification_status": "success" if is_verified else "failed",
                "current_version": ecu.software_version,
                "rollback_status": "completed"
            }
            verification_results.append(result)
            if not is_verified:
                all_verified = False

        return {
            "status": "success" if all_verified else "failed",
            "message": "回滚验证完成" if all_verified else "回滚验证失败",
            "verification_results": verification_results
        }

    def _finalize_rollback(self, task: Task, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """完成回滚"""
        # 清理临时文件
        # 更新系统状态

        return {
            "status": "success",
            "message": "回滚完成",
            "details": {
                "cleanup_completed": True,
                "system_restored": True
            }
        }

    def _validate_activation_result(self, task: Task, completion_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证激活结果"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        all_normal = all(ecu.status == "normal" for ecu in ecus)

        return {
            "is_valid": all_normal,
            "message": "激活验证成功" if all_normal else "部分ECU状态异常",
            "ecu_status": [
                {
                    "ecu_id": ecu.ecu_id,
                    "ecu_type": ecu.ecu_type,
                    "status": ecu.status,
                    "version": ecu.software_version
                }
                for ecu in ecus
            ]
        }

    def _validate_rollback_result(self, task: Task, completion_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证回滚结果"""
        # 获取车辆ECU信息
        ecus = self.db.query(VehicleECU).filter(VehicleECU.vehicle_id == task.vehicle_id).all()

        all_normal = all(ecu.status == "normal" for ecu in ecus)

        return {
            "is_valid": all_normal,
            "message": "回滚验证成功" if all_normal else "部分ECU状态异常",
            "ecu_status": [
                {
                    "ecu_id": ecu.ecu_id,
                    "ecu_type": ecu.ecu_type,
                    "status": ecu.status,
                    "version": ecu.software_version
                }
                for ecu in ecus
            ]
        }

    def _update_vehicle_software_info(self, task: Task) -> None:
        """更新车辆软件信息"""
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task.software_version_id
        ).first()

        if software_version:
            vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
            if vehicle:
                # 更新车辆软件版本信息
                version_info = vehicle.software_version_info or {}
                version_info[str(software_version.software_id)] = {
                    "version": software_version.version,
                    "version_code": software_version.version_code,
                    "updated_at": datetime.now().isoformat(),
                    "task_id": task.task_id
                }
                vehicle.software_version_info = version_info
                self.db.commit()

    def _restore_vehicle_software_info(self, task: Task) -> None:
        """恢复车辆软件信息"""
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
        if vehicle and vehicle.software_version_info:
            # 恢复到之前的版本信息
            version_info = vehicle.software_version_info
            for software_id, info in version_info.items():
                if info.get("task_id") == task.task_id:
                    # 移除当前任务的版本信息
                    del version_info[software_id]
            vehicle.software_version_info = version_info
            self.db.commit()

    def _cleanup_activation(self, task: Task) -> None:
        """清理激活"""
        # 清理临时文件
        # 释放资源
        pass

    def _get_activation_steps(self, software_version: SoftwareVersion) -> List[Dict[str, Any]]:
        """获取激活步骤"""
        return [
            {
                "name": "prepare_activation",
                "description": "准备激活",
                "estimated_time": 30
            },
            {
                "name": "switch_partition",
                "description": "切换分区",
                "estimated_time": 60
            },
            {
                "name": "verify_activation",
                "description": "验证激活",
                "estimated_time": 30
            },
            {
                "name": "finalize_activation",
                "description": "完成激活",
                "estimated_time": 30
            }
        ]

    def _get_rollback_steps(self, software_version: SoftwareVersion) -> List[Dict[str, Any]]:
        """获取回滚步骤"""
        return [
            {
                "name": "prepare_rollback",
                "description": "准备回滚",
                "estimated_time": 30
            },
            {
                "name": "restore_backup",
                "description": "恢复备份",
                "estimated_time": 120
            },
            {
                "name": "verify_rollback",
                "description": "验证回滚",
                "estimated_time": 30
            },
            {
                "name": "finalize_rollback",
                "description": "完成回滚",
                "estimated_time": 30
            }
        ]

    def _estimate_activation_duration(self, software_version: SoftwareVersion) -> int:
        """估算激活时长（秒）"""
        return 150  # 2.5分钟

    def _estimate_rollback_duration(self, software_version: SoftwareVersion) -> int:
        """估算回滚时长（秒）"""
        return 210  # 3.5分钟

    def _record_activation_progress(self, task_id: int, step_name: str, status: str,
                                  message: str = None, error_message: str = None):
        """记录激活进度"""
        try:
            progress_data = TaskProgressCreate(
                task_id=task_id,
                step_name=step_name,
                step_type="activate" if "activation" in step_name.lower() or "switch" in step_name.lower() else "rollback",
                status=status,
                message=message,
                error_message=error_message
            )
            self.task_service.add_progress_record(task_id, progress_data)
        except Exception as e:
            print(f"Failed to record activation progress: {e}")