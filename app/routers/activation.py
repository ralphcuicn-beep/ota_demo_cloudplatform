from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.activation_service import ActivationService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/activation", tags=["activation"])

@router.post("/task/{task_id}/start")
async def start_activation(
    task_id: str,
    activation_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """开始激活"""
    service = ActivationService(db)
    return service.start_activation(task_id, activation_config)

@router.post("/task/{task_id}/step/{step_name}")
async def execute_activation_step(
    task_id: str,
    step_name: str,
    step_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """执行激活步骤"""
    service = ActivationService(db)
    return service.execute_activation_step(task_id, step_name, step_data)

@router.post("/task/{task_id}/complete")
async def complete_activation(
    task_id: str,
    completion_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """完成激活"""
    service = ActivationService(db)
    return service.complete_activation(task_id, completion_data)

@router.post("/task/{task_id}/rollback/start")
async def start_rollback(
    task_id: str,
    rollback_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """开始回滚"""
    service = ActivationService(db)
    return service.start_rollback(task_id, rollback_config)

@router.post("/task/{task_id}/rollback/step/{step_name}")
async def execute_rollback_step(
    task_id: str,
    step_name: str,
    step_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """执行回滚步骤"""
    service = ActivationService(db)
    return service.execute_rollback_step(task_id, step_name, step_data)

@router.post("/task/{task_id}/rollback/complete")
async def complete_rollback(
    task_id: str,
    completion_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """完成回滚"""
    service = ActivationService(db)
    return service.complete_rollback(task_id, completion_data)

@router.get("/task/{task_id}/status")
async def get_activation_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取激活状态"""
    service = ActivationService(db)
    return service.get_activation_status(task_id)

@router.post("/task/{task_id}/cancel")
async def cancel_activation(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消激活"""
    service = ActivationService(db)
    return service.cancel_activation(task_id)

@router.get("/task/{task_id}/pre-check")
async def activation_pre_check(
    task_id: str,
    db: Session = Depends(get_db)
):
    """激活前检查"""
    from app.services.task_service import TaskService
    from app.models import Vehicle

    task_service = TaskService(db)
    task = task_service.get_task_by_task_id(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    vehicle = db.query(Vehicle).filter(Vehicle.id == task.vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="车辆不存在"
        )

    service = ActivationService(db)
    is_ready = service._check_activation_conditions(vehicle, {})

    return {
        "is_ready": is_ready,
        "vehicle_status": vehicle.status,
        "vehicle_conditions": vehicle.capabilities,
        "message": "车辆状态适合激活" if is_ready else "车辆状态不适合激活"
    }

@router.get("/task/{task_id}/steps")
async def get_activation_steps(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取激活步骤"""
    from app.services.task_service import TaskService
    from app.models import SoftwareVersion

    task_service = TaskService(db)
    task = task_service.get_task_by_task_id(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    software_version = db.query(SoftwareVersion).filter(
        SoftwareVersion.id == task.software_version_id
    ).first()

    if not software_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="软件版本不存在"
        )

    service = ActivationService(db)
    return {
        "activation_steps": service._get_activation_steps(software_version),
        "rollback_steps": service._get_rollback_steps(software_version)
    }

@router.post("/task/{task_id}/force-rollback")
async def force_rollback(
    task_id: str,
    rollback_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """强制回滚"""
    service = ActivationService(db)

    # 获取任务
    from app.services.task_service import TaskService
    task_service = TaskService(db)
    task = task_service.get_task_by_task_id(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 强制设置任务状态为失败，允许回滚
    task_service.update_task(task.id, {"status": "failed"})

    # 开始回滚
    return service.start_rollback(task_id, rollback_config)