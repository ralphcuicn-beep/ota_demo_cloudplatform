import os
import json
import hashlib
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from app.models import SoftwareVersion, Task, Vehicle
from app.services.software_service import SoftwareService
from app.services.task_service import TaskService
from app.schemas.task import TaskProgressCreate
from app.core.config import settings

class DownloadService:
    def __init__(self, db: Session):
        self.db = db
        self.software_service = SoftwareService(db)
        self.task_service = TaskService(db)

    def get_download_url(self, task_id: str, auth_token: str) -> Dict[str, Any]:
        """获取下载链接"""
        # 验证任务
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 验证权限
        if not self._validate_download_permission(task, auth_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无下载权限"
            )

        # 检查软件版本
        software_version = self.software_service.get_software_version(task.software_version_id)
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 验证文件是否存在
        if not os.path.exists(software_version.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )

        # 生成下载令牌
        download_token = self._generate_download_token(task_id, auth_token)

        # 返回下载信息
        return {
            "download_url": f"/api/download/{task_id}/{download_token}",
            "file_name": software_version.file_name,
            "file_size": software_version.file_size,
            "file_hash": software_version.file_hash,
            "chunk_size": 1024 * 1024,  # 1MB chunks
            "total_chunks": self._calculate_chunk_count(software_version.file_size)
        }

    def download_file(self, task_id: str, download_token: str, chunk_number: Optional[int] = None) -> FileResponse:
        """下载文件（支持分块下载）"""
        # 验证下载令牌
        if not self._validate_download_token(task_id, download_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="下载令牌无效"
            )

        # 获取任务和软件版本
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        software_version = self.software_service.get_software_version(task.software_version_id)
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 验证文件完整性
        if not self.software_service.verify_file_integrity(software_version.file_path, software_version.file_hash):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件完整性验证失败"
            )

        # 记录下载进度
        self._record_download_progress(task.id, chunk_number)

        # 增加下载计数
        self.software_service.increment_download_count(software_version.id)

        # 返回文件
        return FileResponse(
            path=software_version.file_path,
            filename=software_version.file_name,
            media_type='application/octet-stream'
        )

    def verify_download_integrity(self, task_id: str, received_hash: str) -> Dict[str, Any]:
        """验证下载完整性"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        software_version = self.software_service.get_software_version(task.software_version_id)
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        is_valid = software_version.file_hash == received_hash

        # 记录验证结果
        if is_valid:
            self._record_download_progress(task.id, None, "verification_completed")
        else:
            self._record_download_progress(task.id, None, "verification_failed",
                                          error_message="文件哈希不匹配")

        return {
            "is_valid": is_valid,
            "expected_hash": software_version.file_hash,
            "received_hash": received_hash
        }

    def get_download_info(self, task_id: str) -> Dict[str, Any]:
        """获取下载信息"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        software_version = self.software_service.get_software_version(task.software_version_id)
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        return {
            "file_name": software_version.file_name,
            "file_size": software_version.file_size,
            "file_hash": software_version.file_hash,
            "signature": software_version.signature,
            "security_requirements": json.loads(software_version.security_requirements) if software_version.security_requirements else None,
            "download_count": software_version.download_count,
            "created_at": software_version.created_at.isoformat()
        }

    def prepare_download_environment(self, task_id: str) -> Dict[str, Any]:
        """准备下载环境"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查车辆状态
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 检查车辆是否在线
        if vehicle.status != "online":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="车辆不在线"
            )

        # 检查网络状况
        network_info = vehicle.network_info or {}
        if network_info.get("signal_strength", 0) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="网络信号强度不足"
            )

        # 检查存储空间
        software_version = self.software_service.get_software_version(task.software_version_id)
        if software_version:
            required_space = software_version.file_size * 1.2  # 20% 额外空间
            available_space = network_info.get("available_storage", 0)
            if available_space < required_space:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="存储空间不足"
                )

        # 记录准备完成
        self._record_download_progress(task.id, None, "environment_prepared")

        return {
            "status": "ready",
            "message": "下载环境准备完成",
            "vehicle_status": vehicle.status,
            "network_info": network_info,
            "estimated_download_time": self._estimate_download_time(software_version.file_size, network_info)
        }

    def _validate_download_permission(self, task: Task, auth_token: str) -> bool:
        """验证下载权限"""
        # 这里应该实现更复杂的权限验证逻辑
        # 简化版：检查车辆是否有对应的认证令牌
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
        if not vehicle:
            return False

        # 实际应用中应该验证JWT token或其他认证机制
        return True

    def _generate_download_token(self, task_id: str, auth_token: str) -> str:
        """生成下载令牌"""
        import secrets
        import time

        # 生成基于时间和随机数的令牌
        timestamp = str(int(time.time()))
        random_part = secrets.token_hex(16)

        # 创建令牌内容
        token_content = f"{task_id}:{timestamp}:{random_part}"

        # 使用哈希生成令牌
        return hashlib.sha256(token_content.encode()).hexdigest()

    def _validate_download_token(self, task_id: str, download_token: str) -> bool:
        """验证下载令牌"""
        # 简化版验证，实际应用中应该检查令牌是否过期、是否匹配等
        return len(download_token) == 64  # SHA-256哈希长度

    def _calculate_chunk_count(self, file_size: int, chunk_size: int = 1024 * 1024) -> int:
        """计算分块数量"""
        return (file_size + chunk_size - 1) // chunk_size

    def _record_download_progress(self, task_id: int, chunk_number: Optional[int],
                                 status: str = "downloading", error_message: str = None) -> None:
        """记录下载进度"""
        try:
            if chunk_number is not None:
                progress_data = TaskProgressCreate(
                    task_id=task_id,
                    step_name=f"下载分块 {chunk_number}",
                    step_type="download",
                    status=status,
                    progress=min(chunk_number * 5, 95),  # 每个分块5%进度，最大95%
                    message=f"正在下载第 {chunk_number} 个分块",
                    error_message=error_message
                )
            else:
                progress_data = TaskProgressCreate(
                    task_id=task_id,
                    step_name=status.replace("_", " ").title(),
                    step_type="download",
                    status=status,
                    progress=100 if "completed" in status else 0,
                    message=status.replace("_", " ").title(),
                    error_message=error_message
                )

            self.task_service.add_progress_record(task_id, progress_data)
        except Exception as e:
            # 记录错误但不中断下载流程
            print(f"Failed to record download progress: {e}")

    def _estimate_download_time(self, file_size: int, network_info: Dict[str, Any]) -> int:
        """估算下载时间（秒）"""
        # 获取网络速度（Kbps）
        network_speed = network_info.get("download_speed", 100)  # 默认100Kbps

        # 计算下载时间（秒）
        download_time = (file_size * 8) / (network_speed * 1024)  # 转换为秒

        # 添加缓冲时间
        return int(download_time * 1.2)

    def resume_download(self, task_id: str, last_chunk: int) -> Dict[str, Any]:
        """恢复下载"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        software_version = self.software_service.get_software_version(task.software_version_id)
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        total_chunks = self._calculate_chunk_count(software_version.file_size)
        remaining_chunks = total_chunks - last_chunk

        return {
            "can_resume": True,
            "last_chunk": last_chunk,
            "remaining_chunks": remaining_chunks,
            "total_chunks": total_chunks,
            "resume_url": f"/api/download/{task_id}/resume?last_chunk={last_chunk}"
        }

    def cancel_download(self, task_id: str) -> Dict[str, Any]:
        """取消下载"""
        task = self.task_service.get_task_by_task_id(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 记录取消状态
        self._record_download_progress(task.id, None, "cancelled", "下载被用户取消")

        return {
            "status": "cancelled",
            "message": "下载已取消"
        }