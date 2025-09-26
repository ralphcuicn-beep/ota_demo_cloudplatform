from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.download_service import DownloadService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/download", tags=["download"])

@router.get("/task/{task_id}/url")
async def get_download_url(
    task_id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取下载链接"""
    service = DownloadService(db)
    return service.get_download_url(task_id, authorization)

@router.get("/{task_id}/{download_token}")
async def download_file(
    task_id: str,
    download_token: str,
    chunk_number: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db)
):
    """下载文件"""
    service = DownloadService(db)
    return service.download_file(task_id, download_token, chunk_number)

@router.post("/{task_id}/verify")
async def verify_download_integrity(
    task_id: str,
    verification_data: Dict[str, str],
    db: Session = Depends(get_db)
):
    """验证下载完整性"""
    received_hash = verification_data.get("received_hash")
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少received_hash参数"
        )

    service = DownloadService(db)
    return service.verify_download_integrity(task_id, received_hash)

@router.get("/task/{task_id}/info")
async def get_download_info(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取下载信息"""
    service = DownloadService(db)
    return service.get_download_info(task_id)

@router.post("/task/{task_id}/prepare")
async def prepare_download_environment(
    task_id: str,
    db: Session = Depends(get_db)
):
    """准备下载环境"""
    service = DownloadService(db)
    return service.prepare_download_environment(task_id)

@router.post("/task/{task_id}/resume")
async def resume_download(
    task_id: str,
    resume_data: Dict[str, int],
    db: Session = Depends(get_db)
):
    """恢复下载"""
    last_chunk = resume_data.get("last_chunk")
    if last_chunk is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少last_chunk参数"
        )

    service = DownloadService(db)
    return service.resume_download(task_id, last_chunk)

@router.post("/task/{task_id}/cancel")
async def cancel_download(
    task_id: str,
    db: Session = Depends(get_db)
):
    """取消下载"""
    service = DownloadService(db)
    return service.cancel_download(task_id)

@router.get("/task/{task_id}/stream")
async def stream_download(
    task_id: str,
    range_header: Optional[str] = Header(None, alias="Range"),
    db: Session = Depends(get_db)
):
    """流式下载"""
    service = DownloadService(db)

    # 获取任务信息
    from app.services.task_service import TaskService
    task_service = TaskService(db)
    task = task_service.get_task_by_task_id(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 获取软件版本
    from app.services.software_service import SoftwareService
    software_service = SoftwareService(db)
    software_version = software_service.get_software_version(task.software_version_id)

    if not software_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="软件版本不存在"
        )

    # 验证文件完整性
    if not software_service.verify_file_integrity(software_version.file_path, software_version.file_hash):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件完整性验证失败"
        )

    # 增加下载计数
    software_service.increment_download_count(software_version.id)

    # 返回文件响应
    return FileResponse(
        path=software_version.file_path,
        filename=software_version.file_name,
        media_type='application/octet-stream'
    )