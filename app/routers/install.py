from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.install_service import InstallService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/install", tags=["install"])

@router.post("/task/{task_id}/start")
async def start_installation(
    task_id: str,
    install_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """开始安装"""
    service = InstallService(db)
    return service.start_installation(task_id, install_config)

@router.post("/task/{task_id}/step/{step_name}")
async def execute_install_step(
    task_id: str,
    step_name: str,
    step_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """执行安装步骤"""
    service = InstallService(db)
    return service.execute_install_step(task_id, step_name, step_data)

@router.post("/task/{task_id}/verify")
async def verify_installation(
    task_id: str,
    verification_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """验证安装结果"""
    service = InstallService(db)
    return service.verify_installation(task_id, verification_data)

@router.get("/task/{task_id}/status")
async def get_install_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取安装状态"""
    service = InstallService(db)
    return service.get_install_status(task_id)

@router.post("/task/{task_id}/cancel")
async def cancel_installation(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """取消安装"""
    service = InstallService(db)
    return service.cancel_installation(task_id)

@router.get("/task/{task_id}/steps")
async def get_install_steps(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取安装步骤"""
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

    install_service = InstallService(db)
    return install_service._get_install_steps(software_version)

@router.post("/task/{task_id}/pre-check")
async def pre_install_check(
    task_id: str,
    db: Session = Depends(get_db)
):
    """安装前检查"""
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

    install_service = InstallService(db)
    is_ready = install_service._check_vehicle_install_conditions(vehicle)

    return {
        "is_ready": is_ready,
        "vehicle_status": vehicle.status,
        "vehicle_conditions": vehicle.capabilities,
        "message": "车辆状态适合安装" if is_ready else "车辆状态不适合安装"
    }