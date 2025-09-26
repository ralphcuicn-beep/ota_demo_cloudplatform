import os
import json
import hashlib
import secrets
from typing import Optional, List, Tuple
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.config import settings
from app.models import Software, SoftwareVersion, User
from app.schemas.software import SoftwareCreate, SoftwareUpdate, SoftwareVersionCreate, SoftwareVersionUpdate
from app.models.software import SoftwareStatus

class SoftwareService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)

    def create_software(self, software_data: SoftwareCreate, user_id: int) -> Software:
        """创建软件产品"""
        # 检查名称是否已存在
        existing = self.db.query(Software).filter(Software.name == software_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="软件名称已存在"
            )

        db_software = Software(
            **software_data.dict(),
            created_by=user_id
        )
        self.db.add(db_software)
        self.db.commit()
        self.db.refresh(db_software)
        return db_software

    def get_software(self, software_id: int) -> Optional[Software]:
        """获取软件产品"""
        return self.db.query(Software).filter(Software.id == software_id).first()

    def get_software_list(self, skip: int = 0, limit: int = 100) -> List[Software]:
        """获取软件产品列表"""
        return self.db.query(Software).offset(skip).limit(limit).all()

    def update_software(self, software_id: int, software_data: SoftwareUpdate) -> Optional[Software]:
        """更新软件产品"""
        db_software = self.get_software(software_id)
        if not db_software:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件产品不存在"
            )

        for field, value in software_data.dict(exclude_unset=True).items():
            setattr(db_software, field, value)

        self.db.commit()
        self.db.refresh(db_software)
        return db_software

    def delete_software(self, software_id: int) -> bool:
        """删除软件产品"""
        db_software = self.get_software(software_id)
        if not db_software:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件产品不存在"
            )

        # 检查是否有关联的版本
        version_count = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.software_id == software_id
        ).count()

        if version_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该软件产品下存在版本，无法删除"
            )

        self.db.delete(db_software)
        self.db.commit()
        return True

    def upload_software_version(self,
                              software_id: int,
                              file: UploadFile,
                              version_data: SoftwareVersionCreate,
                              user_id: int) -> SoftwareVersion:
        """上传软件版本"""
        # 验证软件是否存在
        software = self.get_software(software_id)
        if not software:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件产品不存在"
            )

        # 验证版本是否已存在
        existing_version = self.db.query(SoftwareVersion).filter(
            SoftwareVersion.software_id == software_id,
            SoftwareVersion.version == version_data.version
        ).first()

        if existing_version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="版本已存在"
            )

        # 验证文件大小
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置到文件开头

        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小超过限制 ({settings.MAX_FILE_SIZE} bytes)"
            )

        # 创建软件目录
        software_dir = self.upload_dir / str(software_id)
        software_dir.mkdir(exist_ok=True)

        # 生成安全文件名
        file_extension = Path(file.filename).suffix
        safe_filename = f"{secrets.token_hex(8)}{file_extension}"
        file_path = software_dir / safe_filename

        # 计算文件哈希
        file_hash = hashlib.sha256()
        while chunk := file.file.read(8192):
            file_hash.update(chunk)

        final_hash = file_hash.hexdigest()
        file.file.seek(0)

        # 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        # 生成数字签名（简化版，实际应用中应使用真实的数字签名）
        signature = self._generate_signature(file_path, final_hash)

        # 创建版本记录
        db_version = SoftwareVersion(
            software_id=software_id,
            file_path=str(file_path),
            file_name=file.filename,
            file_size=file_size,
            file_hash=final_hash,
            signature=signature,
            created_by=user_id,
            **version_data.dict()
        )

        self.db.add(db_version)
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def get_software_version(self, version_id: int) -> Optional[SoftwareVersion]:
        """获取软件版本"""
        return self.db.query(SoftwareVersion).filter(SoftwareVersion.id == version_id).first()

    def get_software_versions(self, software_id: int) -> List[SoftwareVersion]:
        """获取软件版本列表"""
        return self.db.query(SoftwareVersion).filter(
            SoftwareVersion.software_id == software_id
        ).all()

    def update_software_version(self, version_id: int, version_data: SoftwareVersionUpdate) -> Optional[SoftwareVersion]:
        """更新软件版本"""
        db_version = self.get_software_version(version_id)
        if not db_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        for field, value in version_data.dict(exclude_unset=True).items():
            if field in ['target_ecu_types', 'security_requirements', 'rollback_info']:
                setattr(db_version, field, json.dumps(value) if value else None)
            else:
                setattr(db_version, field, value)

        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def delete_software_version(self, version_id: int) -> bool:
        """删除软件版本"""
        db_version = self.get_software_version(version_id)
        if not db_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 删除文件
        if os.path.exists(db_version.file_path):
            os.remove(db_version.file_path)

        self.db.delete(db_version)
        self.db.commit()
        return True

    def activate_software_version(self, version_id: int) -> SoftwareVersion:
        """激活软件版本"""
        db_version = self.get_software_version(version_id)
        if not db_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="软件版本不存在"
            )

        # 检查是否可以激活
        if db_version.status == SoftwareStatus.ACTIVE:
            return db_version

        # 可以添加更多的激活条件检查

        db_version.status = SoftwareStatus.ACTIVE
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def _generate_signature(self, file_path: str, file_hash: str) -> str:
        """生成数字签名（简化版）"""
        # 实际应用中应使用真实的数字签名算法
        signature_data = f"{file_path}:{file_hash}:{secrets.token_hex(16)}"
        return hashlib.sha256(signature_data.encode()).hexdigest()

    def verify_file_integrity(self, file_path: str, expected_hash: str) -> bool:
        """验证文件完整性"""
        if not os.path.exists(file_path):
            return False

        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)

        return file_hash.hexdigest() == expected_hash

    def increment_download_count(self, version_id: int) -> None:
        """增加下载计数"""
        self.db.query(SoftwareVersion).filter(
            SoftwareVersion.id == version_id
        ).update({"download_count": SoftwareVersion.download_count + 1})
        self.db.commit()