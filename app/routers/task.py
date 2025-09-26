from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskProgressCreate, TaskProgressResponse
from app.services.task_service import TaskService
from app.core.auth import get_current_user
from app.models.user import User
from app.models.task import TaskStatus

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建OTA任务"""
    service = TaskService(db)
    return service.create_task(task, current_user.id)

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    vehicle_id: Optional[int] = Query(None, description="车辆ID"),
    status: Optional[TaskStatus] = Query(None, description="任务状态"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="限制数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务列表"""
    service = TaskService(db)
    return service.get_tasks(vehicle_id, status, skip, limit)

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务详情"""
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    return task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新任务"""
    service = TaskService(db)
    return service.update_task(task_id, task_update)

@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除任务"""
    service = TaskService(db)
    service.delete_task(task_id)
    return {"message": "任务删除成功"}

@router.post("/{task_id}/execute", response_model=TaskResponse)
async def execute_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """执行任务"""
    service = TaskService(db)
    return service.execute_task(task_id)

@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消任务"""
    service = TaskService(db)
    return service.cancel_task(task_id)

@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重试任务"""
    service = TaskService(db)
    return service.retry_task(task_id)

@router.get("/{task_id}/progress", response_model=List[TaskProgressResponse])
async def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务进度"""
    service = TaskService(db)
    return service.get_task_progress(task_id)

@router.post("/{task_id}/progress", response_model=TaskProgressResponse)
async def add_task_progress(
    task_id: int,
    progress: TaskProgressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """添加任务进度"""
    service = TaskService(db)
    return service.add_progress_record(task_id, progress)

@router.get("/vehicle/{vehicle_id}/active", response_model=TaskResponse)
async def get_vehicle_active_task(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取车辆的活跃任务"""
    service = TaskService(db)
    task = service.get_vehicle_active_task(vehicle_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="车辆没有活跃任务"
        )
    return task

@router.get("/admin/timeout", response_model=List[TaskResponse])
async def get_timeout_tasks(
    timeout_hours: int = Query(24, ge=1, le=168, description="超时小时数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取超时任务（管理员）"""
    service = TaskService(db)
    return service.get_timeout_tasks(timeout_hours)