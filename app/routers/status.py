from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.status_service import StatusService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/status", tags=["status"])

@router.post("/vehicle/{vin}/report")
async def report_vehicle_status(
    vin: str,
    status_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """上报车辆状态"""
    service = StatusService(db)
    return service.report_vehicle_status(vin, status_data)

@router.post("/vehicle/{vin}/ecu/{ecu_id}/report")
async def report_ecu_status(
    vin: str,
    ecu_id: str,
    ecu_status: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """上报ECU状态"""
    service = StatusService(db)
    return service.report_ecu_status(vin, ecu_id, ecu_status)

@router.post("/task/{task_id}/progress")
async def report_task_progress(
    task_id: str,
    progress_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """上报任务进度"""
    service = StatusService(db)
    return service.report_task_progress(task_id, progress_data)

@router.post("/vehicle/{vin}/heartbeat")
async def report_heartbeat(
    vin: str,
    heartbeat_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """上报心跳"""
    service = StatusService(db)
    return service.report_heartbeat(vin, heartbeat_data)

@router.get("/vehicle/{vin}")
async def get_vehicle_status(
    vin: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取车辆状态"""
    service = StatusService(db)
    return service.get_vehicle_status(vin)

@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务状态"""
    service = StatusService(db)
    return service.get_task_status(task_id)

@router.get("/system")
async def get_system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取系统状态"""
    service = StatusService(db)
    return service.get_system_status()

@router.get("/vehicles/offline")
async def check_offline_vehicles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查离线车辆"""
    service = StatusService(db)
    return service.check_offline_vehicles()

@router.get("/vehicles/summary")
async def get_vehicles_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取车辆概览"""
    from app.models.vehicle import VehicleStatus

    vehicles = db.query(VehicleStatus).all()

    summary = {
        "total": len(vehicles),
        "online": 0,
        "offline": 0,
        "updating": 0,
        "error": 0,
        "maintenance": 0
    }

    for vehicle in vehicles:
        summary[vehicle.status.value] += 1

    return summary

@router.get("/tasks/summary")
async def get_tasks_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务概览"""
    from app.models.task import TaskStatus

    tasks = db.query(TaskStatus).all()

    summary = {
        "total": len(tasks),
        "pending": 0,
        "scheduled": 0,
        "downloading": 0,
        "downloaded": 0,
        "installing": 0,
        "installed": 0,
        "verifying": 0,
        "verified": 0,
        "activating": 0,
        "activated": 0,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "rollback": 0
    }

    for task in tasks:
        summary[task.status.value] += 1

    return summary

@router.get("/alerts")
async def get_system_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取系统告警"""
    service = StatusService(db)
    system_status = service.get_system_status()
    return system_status.get("alerts", [])

@router.post("/batch/vehicle-status")
async def batch_report_vehicle_status(
    batch_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """批量上报车辆状态"""
    service = StatusService(db)
    results = []

    for vehicle_data in batch_data:
        try:
            vin = vehicle_data.get("vin")
            if vin:
                result = service.report_vehicle_status(vin, vehicle_data)
                results.append({"vin": vin, "status": "success"})
            else:
                results.append({"vin": "unknown", "status": "failed", "error": "Missing VIN"})
        except Exception as e:
            results.append({"vin": vehicle_data.get("vin", "unknown"), "status": "failed", "error": str(e)})

    return {
        "total": len(batch_data),
        "success": len([r for r in results if r["status"] == "success"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }

@router.post("/batch/task-progress")
async def batch_report_task_progress(
    batch_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """批量上报任务进度"""
    service = StatusService(db)
    results = []

    for progress_data in batch_data:
        try:
            task_id = progress_data.get("task_id")
            if task_id:
                result = service.report_task_progress(task_id, progress_data)
                results.append({"task_id": task_id, "status": "success"})
            else:
                results.append({"task_id": "unknown", "status": "failed", "error": "Missing task_id"})
        except Exception as e:
            results.append({"task_id": progress_data.get("task_id", "unknown"), "status": "failed", "error": str(e)})

    return {
        "total": len(batch_data),
        "success": len([r for r in results if r["status"] == "success"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }