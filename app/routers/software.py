from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.software import SoftwareCreate, SoftwareUpdate, SoftwareResponse, SoftwareVersionCreate, SoftwareVersionUpdate, SoftwareVersionResponse
from app.services.software_service import SoftwareService
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/software", tags=["software"])

@router.post("/", response_model=SoftwareResponse)
async def create_software(
    software: SoftwareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建软件产品"""
    service = SoftwareService(db)
    return service.create_software(software, current_user.id)

@router.get("/", response_model=List[SoftwareResponse])
async def get_software_list(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取软件产品列表"""
    service = SoftwareService(db)
    return service.get_software_list(skip, limit)

@router.get("/{software_id}", response_model=SoftwareResponse)
async def get_software(
    software_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取软件产品详情"""
    service = SoftwareService(db)
    software = service.get_software(software_id)
    if not software:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="软件产品不存在"
        )
    return software

@router.put("/{software_id}", response_model=SoftwareResponse)
async def update_software(
    software_id: int,
    software_update: SoftwareUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新软件产品"""
    service = SoftwareService(db)
    return service.update_software(software_id, software_update)

@router.delete("/{software_id}")
async def delete_software(
    software_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除软件产品"""
    service = SoftwareService(db)
    service.delete_software(software_id)
    return {"message": "软件产品删除成功"}

@router.post("/{software_id}/versions", response_model=SoftwareVersionResponse)
async def upload_software_version(
    software_id: int,
    file: UploadFile = File(...),
    version: str = Form(...),
    version_code: Optional[str] = Form(None),
    release_notes: Optional[str] = Form(None),
    min_supported_version: Optional[str] = Form(None),
    max_supported_version: Optional[str] = Form(None),
    target_ecu_types: Optional[str] = Form(None),
    security_requirements: Optional[str] = Form(None),
    rollback_info: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传软件版本"""
    import json

    version_data = SoftwareVersionCreate(
        version=version,
        version_code=version_code,
        release_notes=release_notes,
        min_supported_version=min_supported_version,
        max_supported_version=max_supported_version,
        target_ecu_types=json.loads(target_ecu_types) if target_ecu_types else None,
        security_requirements=json.loads(security_requirements) if security_requirements else None,
        rollback_info=json.loads(rollback_info) if rollback_info else None
    )

    service = SoftwareService(db)
    return service.upload_software_version(software_id, file, version_data, current_user.id)

@router.get("/{software_id}/versions", response_model=List[SoftwareVersionResponse])
async def get_software_versions(
    software_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取软件版本列表"""
    service = SoftwareService(db)
    return service.get_software_versions(software_id)

@router.get("/versions/{version_id}", response_model=SoftwareVersionResponse)
async def get_software_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取软件版本详情"""
    service = SoftwareService(db)
    version = service.get_software_version(version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="软件版本不存在"
        )
    return version

@router.put("/versions/{version_id}", response_model=SoftwareVersionResponse)
async def update_software_version(
    version_id: int,
    version_update: SoftwareVersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新软件版本"""
    service = SoftwareService(db)
    return service.update_software_version(version_id, version_update)

@router.delete("/versions/{version_id}")
async def delete_software_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除软件版本"""
    service = SoftwareService(db)
    service.delete_software_version(version_id)
    return {"message": "软件版本删除成功"}

@router.post("/versions/{version_id}/activate", response_model=SoftwareVersionResponse)
async def activate_software_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """激活软件版本"""
    service = SoftwareService(db)
    return service.activate_software_version(version_id)