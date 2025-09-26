from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging
from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, software, task, download, install, activation, status

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")

    # 创建上传目录
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info("上传目录创建完成")

    yield

    # 关闭时清理资源
    logger.info("应用关闭")

# 创建FastAPI应用
app = FastAPI(
    title="OTA Cloud Platform",
    description="完整的OTA云平台系统，支持软件包管理、任务发布、下载安装、激活回滚等功能",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加可信主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # 生产环境应该设置具体的主机
)

# 静态文件服务
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    logger.error(f"请求验证错误: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body,
            "message": "请求参数验证失败"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    logger.error(f"HTTP异常: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "message": "请求处理失败"
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "message": "服务器内部错误"
        }
    )

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    logger.info(f"请求 {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"响应状态码: {response.status_code}")
    return response

# 根路径
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "OTA Cloud Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "services": {
            "database": "healthy",
            "redis": "healthy"
        }
    }

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(software.router, prefix="/api")
app.include_router(task.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(install.router, prefix="/api")
app.include_router(activation.router, prefix="/api")
app.include_router(status.router, prefix="/api")

# 如果直接运行此文件
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )