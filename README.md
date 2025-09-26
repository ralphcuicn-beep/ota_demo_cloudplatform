# OTA Cloud Platform

完整的OTA云平台系统，支持软件包管理、任务发布、下载安装、激活回滚等功能。

## 功能特性

### 1. 软件包上传
- 支持多种软件类型（固件、软件、配置文件）
- 文件完整性校验（SHA-256）
- 数字签名验证
- 版本管理
- 安全存储

### 2. 任务发布
- 支持定时任务
- 任务优先级管理
- 车辆状态检查
- 任务执行跟踪
- 失败重试机制

### 3. 下载升级包
- 分块下载支持
- 断点续传
- 下载进度跟踪
- 文件完整性验证
- 网络状况检查

### 4. 安装和校验
- 多步骤安装流程
- 实时进度上报
- 安装前条件检查
- 完整性校验
- 真实性验证

### 5. 激活和回滚
- 双备份分区支持
- 安全激活流程
- 自动回滚机制
- 回滚状态跟踪
- 版本恢复

### 6. 状态上报
- 车辆心跳监控
- ECU状态跟踪
- 任务进度上报
- 系统状态统计
- 异常告警

## 技术栈

- **后端框架**: FastAPI
- **数据库**: SQLite (可配置PostgreSQL/MySQL)
- **认证**: JWT
- **文件存储**: 本地文件系统 (可配置云存储)
- **缓存**: Redis (可选)
- **加密**: bcrypt, SHA-256

## 项目结构

```
ota_demo_cloudplatform/
├── app/
│   ├── core/               # 核心配置
│   │   ├── auth.py         # 认证模块
│   │   ├── config.py       # 配置管理
│   │   └── database.py     # 数据库配置
│   ├── models/            # 数据模型
│   │   ├── software.py     # 软件相关模型
│   │   ├── task.py         # 任务相关模型
│   │   ├── vehicle.py      # 车辆相关模型
│   │   └── user.py         # 用户相关模型
│   ├── schemas/           # Pydantic模型
│   │   ├── software.py     # 软件相关Schema
│   │   ├── task.py         # 任务相关Schema
│   │   └── user.py         # 用户相关Schema
│   ├── services/          # 业务逻辑
│   │   ├── software_service.py    # 软件服务
│   │   ├── task_service.py        # 任务服务
│   │   ├── download_service.py    # 下载服务
│   │   ├── install_service.py     # 安装服务
│   │   ├── activation_service.py  # 激活服务
│   │   └── status_service.py      # 状态服务
│   ├── routers/           # API路由
│   │   ├── auth.py         # 认证路由
│   │   ├── software.py     # 软件路由
│   │   ├── task.py         # 任务路由
│   │   ├── download.py     # 下载路由
│   │   ├── install.py      # 安装路由
│   │   ├── activation.py   # 激活路由
│   │   └── status.py       # 状态路由
│   └── main.py            # 主应用文件
├── uploads/               # 文件上传目录
├── requirements.txt        # 依赖包
├── run.py                 # 启动脚本
└── README.md             # 项目说明
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv ota_env

# 激活虚拟环境
# Windows:
ota_env\Scripts\activate
# Linux/Mac:
source ota_env/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=sqlite:///./ota_platform.db

# Redis配置
REDIS_URL=redis://localhost:6379

# JWT配置
SECRET_KEY=your-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 文件上传配置
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=1073741824

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

### 3. 启动应用

```bash
# 启动开发服务器
python run.py

# 或者使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API使用示例

### 1. 用户认证

```bash
# 用户注册
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "admin123",
    "full_name": "系统管理员",
    "role": "admin"
  }'

# 用户登录
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

### 2. 软件管理

```bash
# 创建软件产品
curl -X POST "http://localhost:8000/api/software/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ECU固件",
    "description": "发动机控制单元固件",
    "software_type": "firmware",
    "vendor": "Bosch",
    "category": "动力系统"
  }'

# 上传软件版本
curl -X POST "http://localhost:8000/api/software/1/versions" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@firmware.bin" \
  -F "version=1.0.0" \
  -F "version_code=v100" \
  -F "release_notes=修复已知问题"
```

### 3. 任务管理

```bash
# 创建OTA任务
curl -X POST "http://localhost:8000/api/tasks/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ECU升级任务",
    "description": "升级车辆ECU固件到最新版本",
    "vehicle_id": 1,
    "software_version_id": 1,
    "priority": "high"
  }'

# 执行任务
curl -X POST "http://localhost:8000/api/tasks/1/execute" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. 状态上报

```bash
# 上报车辆心跳
curl -X POST "http://localhost:8000/api/status/vehicle/VIN123/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{
    "network_info": {
      "signal_strength": 85,
      "download_speed": 1024
    },
    "location": {
      "latitude": 39.9042,
      "longitude": 116.4074
    }
  }'

# 上报任务进度
curl -X POST "http://localhost:8000/api/status/task/TASK123/progress" \
  -H "Content-Type: application/json" \
  -d '{
    "step_name": "下载升级包",
    "step_type": "download",
    "status": "in_progress",
    "progress": 50,
    "message": "正在下载第2个分块"
  }'
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进项目。
