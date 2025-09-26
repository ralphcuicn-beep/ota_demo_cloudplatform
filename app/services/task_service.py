import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import Task, TaskProgress, Vehicle, SoftwareVersion, User
from app.schemas.task import TaskCreate, TaskUpdate, TaskProgressCreate
from app.models.task import TaskStatus, TaskPriority
from app.core.config import settings

class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, task_data: TaskCreate, user_id: int) -> Task:
        """创建OTA任务"""
        # 验证车辆是否存在
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == task_data.vehicle_id).first()
        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在"
            )

        # 验证软件版本是否存在
        software_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == task_data.software_version_id
        ).first()
        if not software_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 检查车辆是否有正在进行的任务
        active_task = self.db.query(Task).filter(
            and_(
                Task.vehicle_id == task_data.vehicle_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING,
                               TaskStatus.INSTALLING, TaskStatus.VERIFYING, TaskStatus.ACTIVATING])
            )
        ).first()

        if active_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该车辆有正在进行的OTA任务"
            )

        # 生成任务ID
        task_id = f"OTA_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 创建任务
        db_task = Task(
            task_id=task_id,
            created_by=user_id,
            **task_data.dict()
        )

        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)

        # 创建初始进度记录
        self._create_initial_progress(db_task.id)

        return db_task

    def get_task(self, task_id: int) -> Optional[Task]:
        """获取任务详情"""
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_task_by_task_id(self, task_id: str) -> Optional[Task]:
        """根据任务ID获取任务"""
        return self.db.query(Task).filter(Task.task_id == task_id).first()

    def get_tasks(self,
                  vehicle_id: Optional[int] = None,
                  status: Optional[TaskStatus] = None,
                  skip: int = 0,
                  limit: int = 100) -> List[Task]:
        """获取任务列表"""
        query = self.db.query(Task)

        if vehicle_id:
            query = query.filter(Task.vehicle_id == vehicle_id)
        if status:
            query = query.filter(Task.status == status)

        return query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    def update_task(self, task_id: int, task_update: TaskUpdate) -> Optional[Task]:
        """更新任务"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 状态变更验证
        if task_update.status:
            self._validate_status_transition(db_task.status, task_update.status)

        update_data = task_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_task, field, value)

        # 如果状态变更为开始执行，记录开始时间
        if task_update.status in [TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING]:
            if not db_task.start_time:
                db_task.start_time = datetime.now()

        # 如果任务完成或失败，记录结束时间
        if task_update.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            if not db_task.end_time:
                db_task.end_time = datetime.now()

        self.db.commit()
        self.db.refresh(db_task)
        return db_task

    def delete_task(self, task_id: int) -> bool:
        """删除任务"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 只能删除未开始或已完成的任务
        if db_task.status not in [TaskStatus.PENDING, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能删除未开始或已完成的任务"
            )

        self.db.delete(db_task)
        self.db.commit()
        return True

    def execute_task(self, task_id: int) -> Task:
        """执行任务"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查任务是否可以执行
        if db_task.status != TaskStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务状态不允许执行"
            )

        # 检查车辆状态
        vehicle = self.db.query(Vehicle).filter(Vehicle.id == db_task.vehicle_id).first()
        if not vehicle or vehicle.status != "online":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="车辆不在线，无法执行任务"
            )

        # 更新任务状态
        db_task.status = TaskStatus.SCHEDULED
        db_task.start_time = datetime.now()
        self.db.commit()
        self.db.refresh(db_task)

        # 这里可以添加异步任务执行逻辑
        # 例如：发送通知给车辆端开始下载

        return db_task

    def cancel_task(self, task_id: int) -> Task:
        """取消任务"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查任务是否可以取消
        if db_task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务已完成或已取消"
            )

        db_task.status = TaskStatus.CANCELLED
        db_task.end_time = datetime.now()
        self.db.commit()
        self.db.refresh(db_task)

        # 记录取消进度
        self._add_progress_record(
            task_id=db_task.id,
            step_name="任务取消",
            step_type="cancel",
            status="cancelled",
            message="任务被用户取消"
        )

        return db_task

    def retry_task(self, task_id: int) -> Task:
        """重试任务"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 检查是否可以重试
        if db_task.status not in [TaskStatus.FAILED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有失败的任务可以重试"
            )

        if db_task.retry_count >= db_task.max_retry:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已达到最大重试次数"
            )

        # 重置任务状态
        db_task.status = TaskStatus.PENDING
        db_task.retry_count += 1
        db_task.start_time = None
        db_task.end_time = None
        self.db.commit()
        self.db.refresh(db_task)

        # 记录重试进度
        self._add_progress_record(
            task_id=db_task.id,
            step_name="任务重试",
            step_type="retry",
            status="retry",
            message=f"第 {db_task.retry_count} 次重试"
        )

        return db_task

    def get_task_progress(self, task_id: int) -> List[TaskProgress]:
        """获取任务进度"""
        return self.db.query(TaskProgress).filter(
            TaskProgress.task_id == task_id
        ).order_by(TaskProgress.created_at.asc()).all()

    def add_progress_record(self, task_id: int, progress_data: TaskProgressCreate) -> TaskProgress:
        """添加进度记录"""
        db_task = self.get_task(task_id)
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        # 如果是开始新步骤，更新开始时间
        if progress_data.status == "in_progress":
            progress_data.start_time = datetime.now()
        elif progress_data.status in ["completed", "failed"]:
            progress_data.end_time = datetime.now()

        db_progress = TaskProgress(
            task_id=task_id,
            **progress_data.dict()
        )

        self.db.add(db_progress)
        self.db.commit()
        self.db.refresh(db_progress)

        # 更新任务状态
        self._update_task_status_from_progress(task_id, progress_data.step_type, progress_data.status)

        return db_progress

    def get_vehicle_active_task(self, vehicle_id: int) -> Optional[Task]:
        """获取车辆的活跃任务"""
        return self.db.query(Task).filter(
            and_(
                Task.vehicle_id == vehicle_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING,
                               TaskStatus.INSTALLING, TaskStatus.VERIFYING, TaskStatus.ACTIVATING])
            )
        ).first()

    def get_timeout_tasks(self, timeout_hours: int = None) -> List[Task]:
        """获取超时任务"""
        if timeout_hours is None:
            timeout_hours = settings.TASK_TIMEOUT_HOURS

        timeout_time = datetime.now() - timedelta(hours=timeout_hours)

        return self.db.query(Task).filter(
            and_(
                Task.status.in_([TaskStatus.SCHEDULED, TaskStatus.DOWNLOADING,
                               TaskStatus.INSTALLING, TaskStatus.VERIFYING, TaskStatus.ACTIVATING]),
                Task.start_time < timeout_time,
                Task.end_time.is_(None)
            )
        ).all()

    def _create_initial_progress(self, task_id: int) -> None:
        """创建初始进度记录"""
        initial_progress = TaskProgress(
            task_id=task_id,
            step_name="任务创建",
            step_type="init",
            status="created",
            progress=0,
            message="任务已创建，等待执行"
        )
        self.db.add(initial_progress)
        self.db.commit()

    def _add_progress_record(self, task_id: int, step_name: str, step_type: str,
                           status: str, message: str = None, error_message: str = None) -> TaskProgress:
        """添加进度记录"""
        progress = TaskProgress(
            task_id=task_id,
            step_name=step_name,
            step_type=step_type,
            status=status,
            message=message,
            error_message=error_message
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def _validate_status_transition(self, current_status: TaskStatus, new_status: TaskStatus) -> None:
        """验证状态转换是否合法"""
        valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.SCHEDULED, TaskStatus.CANCELLED],
            TaskStatus.SCHEDULED: [TaskStatus.DOWNLOADING, TaskStatus.CANCELLED],
            TaskStatus.DOWNLOADING: [TaskStatus.DOWNLOADED, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.DOWNLOADED: [TaskStatus.INSTALLING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.INSTALLING: [TaskStatus.INSTALLED, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.INSTALLED: [TaskStatus.VERIFYING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.VERIFYING: [TaskStatus.VERIFIED, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.VERIFIED: [TaskStatus.ACTIVATING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.ACTIVATING: [TaskStatus.ACTIVATED, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.ACTIVATED: [TaskStatus.COMPLETED, TaskStatus.ROLLBACK],
            TaskStatus.FAILED: [TaskStatus.PENDING],  # 重试
            TaskStatus.ROLLBACK: [TaskStatus.COMPLETED, TaskStatus.FAILED]
        }

        if new_status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"状态转换不合法: {current_status} -> {new_status}"
            )

    def _update_task_status_from_progress(self, task_id: int, step_type: str, step_status: str) -> None:
        """根据进度更新任务状态"""
        status_mapping = {
            "download": {
                "in_progress": TaskStatus.DOWNLOADING,
                "completed": TaskStatus.DOWNLOADED,
                "failed": TaskStatus.FAILED
            },
            "install": {
                "in_progress": TaskStatus.INSTALLING,
                "completed": TaskStatus.INSTALLED,
                "failed": TaskStatus.FAILED
            },
            "verify": {
                "in_progress": TaskStatus.VERIFYING,
                "completed": TaskStatus.VERIFIED,
                "failed": TaskStatus.FAILED
            },
            "activate": {
                "in_progress": TaskStatus.ACTIVATING,
                "completed": TaskStatus.ACTIVATED,
                "failed": TaskStatus.FAILED
            },
            "rollback": {
                "in_progress": TaskStatus.ROLLBACK,
                "completed": TaskStatus.COMPLETED,
                "failed": TaskStatus.FAILED
            }
        }

        if step_type in status_mapping and step_status in status_mapping[step_type]:
            new_status = status_mapping[step_type][step_status]
            self.db.query(Task).filter(Task.id == task_id).update({"status": new_status})
            self.db.commit()