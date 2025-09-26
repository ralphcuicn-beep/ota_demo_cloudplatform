from pydantic import BaseSettings, Field
from typing import Optional
import os

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = Field(default="sqlite:///./ota_platform.db", env="DATABASE_URL")

    # Redis配置
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # JWT配置
    SECRET_KEY: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # 文件上传配置
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=1024 * 1024 * 1024, env="MAX_FILE_SIZE")  # 1GB

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")

    # 安全配置
    SECURITY_HASH_ITERATIONS: int = Field(default=100000, env="SECURITY_HASH_ITERATIONS")

    # OTA特定配置
    VEHICLE_HEARTBEAT_TIMEOUT: int = Field(default=300, env="VEHICLE_HEARTBEAT_TIMEOUT")  # 5分钟
    TASK_TIMEOUT_HOURS: int = Field(default=24, env="TASK_TIMEOUT_HOURS")  # 24小时

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()