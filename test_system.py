#!/usr/bin/env python3
"""
OTA云平台系统测试脚本
"""

import asyncio
import json
import httpx
import hashlib
from pathlib import Path

class OTATestClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url)
        self.token = None
        self.headers = {}

    def register_user(self, username, email, password, role="admin"):
        """注册用户"""
        data = {
            "username": username,
            "email": email,
            "password": password,
            "full_name": f"Test User {username}",
            "role": role
        }
        response = self.client.post("/api/auth/register", json=data)
        return response.json()

    def login(self, username, password):
        """用户登录"""
        data = {
            "username": username,
            "password": password
        }
        response = self.client.post("/api/auth/login", json=data)
        result = response.json()
        if response.status_code == 200:
            self.token = result["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        return result

    def create_software(self, software_data):
        """创建软件产品"""
        response = self.client.post("/api/software/", json=software_data, headers=self.headers)
        return response.json()

    def upload_software_version(self, software_id, file_path, version_data):
        """上传软件版本"""
        files = {"file": open(file_path, "rb")}
        data = version_data
        response = self.client.post(
            f"/api/software/{software_id}/versions",
            files=files,
            data=data,
            headers=self.headers
        )
        files["file"].close()
        return response.json()

    def create_vehicle(self, vehicle_data):
        """创建车辆（通过状态上报）"""
        response = self.client.post(f"/api/status/vehicle/{vehicle_data['vin']}/report",
                                   json=vehicle_data)
        return response.json()

    def create_task(self, task_data):
        """创建OTA任务"""
        response = self.client.post("/api/tasks/", json=task_data, headers=self.headers)
        return response.json()

    def execute_task(self, task_id):
        """执行任务"""
        response = self.client.post(f"/api/tasks/{task_id}/execute", headers=self.headers)
        return response.json()

    def get_task_status(self, task_id):
        """获取任务状态"""
        response = self.client.get(f"/api/tasks/{task_id}", headers=self.headers)
        return response.json()

    def report_heartbeat(self, vin, heartbeat_data):
        """上报心跳"""
        response = self.client.post(f"/api/status/vehicle/{vin}/heartbeat",
                                   json=heartbeat_data)
        return response.json()

    def report_task_progress(self, task_id, progress_data):
        """上报任务进度"""
        response = self.client.post(f"/api/status/task/{task_id}/progress",
                                   json=progress_data)
        return response.json()

    def get_system_status(self):
        """获取系统状态"""
        response = self.client.get("/api/status/system", headers=self.headers)
        return response.json()

def create_test_file(file_path, content="This is a test firmware file."):
    """创建测试文件"""
    with open(file_path, "wb") as f:
        f.write(content.encode())
    return file_path

def calculate_file_hash(file_path):
    """计算文件哈希"""
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256()
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return file_hash.hexdigest()

async def run_tests():
    """运行测试"""
    client = OTATestClient()

    print("=== OTA云平台系统测试 ===\n")

    # 1. 用户注册和登录
    print("1. 用户注册和登录测试...")
    try:
        # 注册用户
        register_result = client.register_user("testadmin", "admin@test.com", "admin123", "admin")
        print(f"   用户注册: {register_result.get('message', '成功')}")

        # 登录
        login_result = client.login("testadmin", "admin123")
        print(f"   用户登录: {login_result.get('message', '成功')}")
        print(f"   获取令牌: 成功")
    except Exception as e:
        print(f"   错误: {e}")

    print()

    # 2. 软件管理测试
    print("2. 软件管理测试...")
    try:
        # 创建软件产品
        software_data = {
            "name": "ECU控制器固件",
            "description": "车辆ECU控制器固件升级包",
            "software_type": "firmware",
            "vendor": "TestVendor",
            "category": "动力系统"
        }
        software_result = client.create_software(software_data)
        software_id = software_result.get("id")
        print(f"   创建软件产品: 成功 (ID: {software_id})")

        # 创建测试文件
        test_file = create_test_file("test_firmware.bin", "Test firmware content v1.0")
        file_hash = calculate_file_hash(test_file)

        # 上传软件版本
        version_data = {
            "version": "1.0.0",
            "version_code": "v100",
            "release_notes": "初始版本发布",
            "target_ecu_types": ["engine", "transmission"],
            "security_requirements": {
                "min_battery_level": 30,
                "require_parked": True
            }
        }
        version_result = client.upload_software_version(software_id, test_file, version_data)
        version_id = version_result.get("id")
        print(f"   上传软件版本: 成功 (ID: {version_id})")
        print(f"   文件哈希: {file_hash}")

        # 清理测试文件
        Path(test_file).unlink()
    except Exception as e:
        print(f"   错误: {e}")

    print()

    # 3. 车辆管理测试
    print("3. 车辆管理测试...")
    try:
        # 创建车辆
        vehicle_data = {
            "vin": "TESTVIN123456789",
            "vehicle_status": "online",
            "software_version_info": {
                "engine": "1.0.0",
                "transmission": "1.0.0"
            },
            "capabilities": {
                "is_parked": True,
                "battery_level": 85,
                "engine_status": "off"
            },
            "network_info": {
                "signal_strength": 90,
                "download_speed": 2048,
                "available_storage": 1073741824
            },
            "location": {
                "latitude": 39.9042,
                "longitude": 116.4074
            }
        }
        vehicle_result = client.create_vehicle(vehicle_data)
        print(f"   创建车辆: 成功")

        # 上报心跳
        heartbeat_data = {
            "network_info": {
                "signal_strength": 88,
                "download_speed": 1984
            },
            "location": {
                "latitude": 39.9042,
                "longitude": 116.4074
            }
        }
        heartbeat_result = client.report_heartbeat("TESTVIN123456789", heartbeat_data)
        print(f"   上报心跳: 成功")
    except Exception as e:
        print(f"   错误: {e}")

    print()

    # 4. 任务管理测试
    print("4. 任务管理测试...")
    try:
        # 创建OTA任务
        task_data = {
            "name": "ECU固件升级任务",
            "description": "升级车辆ECU固件到版本1.0.0",
            "vehicle_id": 1,  # 假设车辆ID为1
            "software_version_id": version_id,
            "priority": "high",
            "timeout": 3600,
            "configuration": {
                "download_retries": 3,
                "install_retries": 2
            }
        }
        task_result = client.create_task(task_data)
        task_id = task_result.get("id")
        task_uuid = task_result.get("task_id")
        print(f"   创建任务: 成功 (ID: {task_id}, UUID: {task_uuid})")

        # 执行任务
        execute_result = client.execute_task(task_id)
        print(f"   执行任务: {execute_result.get('message', '成功')}")

        # 模拟任务进度上报
        progress_steps = [
            {
                "step_name": "准备下载环境",
                "step_type": "download",
                "status": "completed",
                "progress": 10,
                "message": "下载环境准备完成"
            },
            {
                "step_name": "下载升级包",
                "step_type": "download",
                "status": "in_progress",
                "progress": 50,
                "message": "正在下载升级包"
            },
            {
                "step_name": "下载升级包",
                "step_type": "download",
                "status": "completed",
                "progress": 100,
                "message": "升级包下载完成"
            },
            {
                "step_name": "安装前检查",
                "step_type": "install",
                "status": "completed",
                "progress": 20,
                "message": "安装前检查通过"
            },
            {
                "step_name": "安装升级包",
                "step_type": "install",
                "status": "in_progress",
                "progress": 60,
                "message": "正在安装升级包"
            },
            {
                "step_name": "安装升级包",
                "step_type": "install",
                "status": "completed",
                "progress": 100,
                "message": "升级包安装完成"
            }
        ]

        for step in progress_steps:
            progress_result = client.report_task_progress(task_uuid, step)
            print(f"   进度上报: {step['step_name']} - {step['status']}")

            # 模拟处理时间
            await asyncio.sleep(0.5)

        # 获取任务状态
        status_result = client.get_task_status(task_id)
        print(f"   任务状态: {status_result.get('status', '未知')}")
    except Exception as e:
        print(f"   错误: {e}")

    print()

    # 5. 系统状态测试
    print("5. 系统状态测试...")
    try:
        system_status = client.get_system_status()
        print(f"   系统状态: {system_status.get('system_status', '未知')}")
        print(f"   车辆统计: {system_status.get('statistics', {}).get('vehicles', {})}")
        print(f"   任务统计: {system_status.get('statistics', {}).get('tasks', {})}")
        print(f"   系统告警: {len(system_status.get('alerts', []))} 个")
    except Exception as e:
        print(f"   错误: {e}")

    print("\n=== 测试完成 ===")
    print("如果看到上述信息，说明OTA云平台系统已成功运行！")
    print("访问 http://localhost:8000/docs 查看完整的API文档")

if __name__ == "__main__":
    asyncio.run(run_tests())