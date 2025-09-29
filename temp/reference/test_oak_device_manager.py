#!/usr/bin/env python3

"""
OAK设备管理器全面测试脚本
测试oak_device_manager.py模块的所有功能
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any

from oak_modules import OAKDeviceManager


class OAKDeviceManagerTester:
    """OAK设备管理器测试类"""
    
    def __init__(self):
        """初始化测试环境"""
        self.test_dir = Path("test_configs")
        self.test_dir.mkdir(exist_ok=True)
        self.test_results = []
        
        # 模拟设备数据
        self.mock_devices = [
            {"mxid": "MXID_LEFT_ABCDEFG123456", "state": "BOOTLOADER", "name": "OAK-D-1"},
            {"mxid": "MXID_RIGHT_HIJKLMN789012", "state": "BOOTLOADER", "name": "OAK-D-2"},
            {"mxid": "MXID_CENTER_OPQRSTU345678", "state": "BOOTLOADER", "name": "OAK-D-3"}
        ]
        
        print("🧪 OAK设备管理器测试环境初始化完成")
    
    def log_test_result(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if success else "❌ 失败"
        result = {
            "test": test_name,
            "success": success,
            "message": message
        }
        self.test_results.append(result)
        print(f"  {status}: {test_name} {message}")
    
    def test_initialization(self):
        """测试初始化功能"""
        print("\n📋 测试1: 初始化功能")
        
        try:
            # 测试默认初始化
            manager = OAKDeviceManager()
            self.log_test_result("默认初始化", True)
            
            # 测试自定义路径初始化
            custom_path = self.test_dir / "custom_config.json"
            manager_custom = OAKDeviceManager(str(custom_path))
            self.log_test_result("自定义路径初始化", True)
            
            # 验证初始配置结构
            expected_keys = {"config_version", "updated_at", "filter", "devices"}
            actual_keys = set(manager.config.keys())
            if expected_keys.issubset(actual_keys):
                self.log_test_result("初始配置结构", True)
            else:
                self.log_test_result("初始配置结构", False, f"缺少字段: {expected_keys - actual_keys}")
            
        except Exception as e:
            self.log_test_result("初始化测试", False, str(e))
    
    def test_device_discovery(self):
        """测试设备发现功能"""
        print("\n🔍 测试2: 设备发现功能")
        
        try:
            manager = OAKDeviceManager(str(self.test_dir / "discovery_test.json"))
            
            # 测试设备发现（可能没有实际设备）
            devices = manager.list_connected()
            self.log_test_result("设备发现调用", True, f"发现{len(devices)}个设备")
            
            # 验证返回数据结构
            if devices:
                device = devices[0]
                required_fields = {"mxid", "name", "state"}
                actual_fields = set(device.keys())
                if required_fields.issubset(actual_fields):
                    self.log_test_result("设备信息结构", True)
                else:
                    self.log_test_result("设备信息结构", False, f"缺少字段: {required_fields - actual_fields}")
            else:
                self.log_test_result("设备信息结构", True, "无设备连接，跳过结构验证")
                
        except Exception as e:
            self.log_test_result("设备发现测试", False, str(e))
    
    def test_alias_binding(self):
        """测试别名绑定功能"""
        print("\n🔗 测试3: 别名绑定功能")
        
        try:
            manager = OAKDeviceManager(str(self.test_dir / "binding_test.json"))
            
            # 测试正常绑定
            mxid1 = self.mock_devices[0]["mxid"]
            alias1 = "test_oak_left"
            manager.bind_alias(mxid1, alias1)
            self.log_test_result("正常绑定", True)
            
            # 测试双向查找
            found_mxid = manager.get_mxid(alias1)
            found_alias = manager.get_alias(mxid1)
            
            if found_mxid == mxid1 and found_alias == alias1:
                self.log_test_result("双向查找", True)
            else:
                self.log_test_result("双向查找", False, f"查找结果不匹配: {found_mxid}, {found_alias}")
            
            # 测试重复绑定检测
            try:
                manager.bind_alias(mxid1, "another_alias")
                self.log_test_result("重复MXid检测", False, "应该抛出异常")
            except ValueError:
                self.log_test_result("重复MXid检测", True)
            
            try:
                manager.bind_alias("ANOTHER_MXID_123456789", alias1)
                self.log_test_result("重复别名检测", False, "应该抛出异常")
            except ValueError:
                self.log_test_result("重复别名检测", True)
            
            # 测试无效输入
            try:
                manager.bind_alias("", "invalid_alias")
                self.log_test_result("空MXid检测", False, "应该抛出异常")
            except ValueError:
                self.log_test_result("空MXid检测", True)
                
        except Exception as e:
            self.log_test_result("别名绑定测试", False, str(e))
    
    def test_config_creation(self):
        """测试配置创建功能"""
        print("\n⚙️ 测试4: 配置创建功能")
        
        try:
            manager = OAKDeviceManager(str(self.test_dir / "creation_test.json"))
            
            # 测试create_new_config
            mxids = [dev["mxid"] for dev in self.mock_devices[:2]]
            aliases = ["left_oak", "right_oak"]
            kinematics_list = [
                {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2},
                {"Tx": -1600.0, "Ty": -800.0, "Tz": 1250.0, "Ry": 25.0, "Rz": -30.0}
            ]
            
            manager.create_new_config(
                mxids=mxids,
                aliases=aliases,
                kinematics_list=kinematics_list,
                filter_type="moving_average",
                filter_window=8
            )
            self.log_test_result("create_new_config", True)
            
            # 验证配置内容
            if len(manager.config["devices"]) == 2:
                self.log_test_result("设备数量正确", True)
            else:
                self.log_test_result("设备数量正确", False, f"期望2个，实际{len(manager.config['devices'])}个")
            
            # 测试add_device_config
            manager2 = OAKDeviceManager(str(self.test_dir / "add_device_test.json"))
            manager2.add_device_config(
                mxid=self.mock_devices[0]["mxid"],
                alias="single_oak",
                Tx=-1500.0, Ty=-760.0, Tz=1200.0, Ry=22.9, Rz=-25.2
            )
            self.log_test_result("add_device_config", True)
            
        except Exception as e:
            self.log_test_result("配置创建测试", False, str(e))
    
    def test_kinematics_management(self):
        """测试外参管理功能"""
        print("\n📐 测试5: 外参管理功能")
        
        try:
            manager = OAKDeviceManager(str(self.test_dir / "kinematics_test.json"))
            
            # 先绑定设备
            mxid = self.mock_devices[0]["mxid"]
            alias = "kinematics_test_oak"
            manager.bind_alias(mxid, alias)
            
            # 测试设置外参
            test_kinematics = {"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2}
            manager.set_kinematics(alias, **test_kinematics)
            self.log_test_result("设置外参", True)
            
            # 测试读取外参
            retrieved_kinematics = manager.get_kinematics(alias)
            if retrieved_kinematics == test_kinematics:
                self.log_test_result("读取外参", True)
            else:
                self.log_test_result("读取外参", False, f"数据不匹配")
            
            # 测试无效字段
            try:
                manager.set_kinematics(alias, InvalidField=123.0)
                self.log_test_result("无效字段检测", False, "应该抛出异常")
            except ValueError:
                self.log_test_result("无效字段检测", True)
                
        except Exception as e:
            self.log_test_result("外参管理测试", False, str(e))
    
    def test_config_validation(self):
        """测试配置校验功能"""
        print("\n✅ 测试6: 配置校验功能")
        
        try:
            manager = OAKDeviceManager(str(self.test_dir / "validation_test.json"))
            
            # 测试有效配置
            manager.create_new_config(
                mxids=[self.mock_devices[0]["mxid"]],
                aliases=["valid_oak"],
                kinematics_list=[{"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2}]
            )
            
            if manager.validate():
                self.log_test_result("有效配置校验", True)
            else:
                self.log_test_result("有效配置校验", False, "有效配置校验失败")
            
            # 测试无效滤波类型
            manager.config["filter"]["type"] = "invalid_filter"
            try:
                manager.validate()
                self.log_test_result("无效滤波类型检测", False, "应该抛出异常")
            except ValueError:
                self.log_test_result("无效滤波类型检测", True)
                
        except Exception as e:
            self.log_test_result("配置校验测试", False, str(e))
    
    def test_config_persistence(self):
        """测试配置持久化功能"""
        print("\n💾 测试7: 配置持久化功能")
        
        try:
            config_path = self.test_dir / "persistence_test.json"
            manager = OAKDeviceManager(str(config_path))
            
            # 创建测试配置
            manager.create_new_config(
                mxids=[self.mock_devices[0]["mxid"]],
                aliases=["persistence_oak"],
                kinematics_list=[{"Tx": -1500.0, "Ty": -760.0, "Tz": 1200.0, "Ry": 22.9, "Rz": -25.2}]
            )
            
            # 测试保存
            manager.save()
            if config_path.exists():
                self.log_test_result("配置保存", True)
            else:
                self.log_test_result("配置保存", False, "配置文件未创建")
            
            # 测试加载
            manager2 = OAKDeviceManager(str(config_path))
            loaded_config = manager2.load()
            
            if loaded_config and len(loaded_config.get("devices", [])) == 1:
                self.log_test_result("配置加载", True)
            else:
                self.log_test_result("配置加载", False, "加载的配置不正确")
                
        except Exception as e:
            self.log_test_result("配置持久化测试", False, str(e))
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始运行OAK设备管理器全面测试\n")
        
        # 运行所有测试方法
        test_methods = [
            self.test_initialization,
            self.test_device_discovery,
            self.test_alias_binding,
            self.test_config_creation,
            self.test_kinematics_management,
            self.test_config_validation,
            self.test_config_persistence
        ]
        
        for test_method in test_methods:
            try:
                test_method()
            except Exception as e:
                print(f"❌ 测试方法 {test_method.__name__} 执行失败: {e}")
        
        # 生成测试报告
        self.generate_test_report()
    
    def generate_test_report(self):
        """生成测试报告"""
        print("\n" + "="*60)
        print("📊 测试报告")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"通过率: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ 失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['test']}: {result['message']}")
        
        # 保存详细报告到文件
        report_path = self.test_dir / "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": {
                    "total": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "pass_rate": passed_tests/total_tests*100 if total_tests > 0 else 0
                },
                "details": self.test_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细报告已保存到: {report_path}")
    
    def cleanup(self):
        """清理测试环境"""
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
            print(f"🧹 测试环境已清理")
        except Exception as e:
            print(f"⚠️ 清理测试环境时出错: {e}")


def main():
    """主函数"""
    print("🎯 OAK设备管理器测试脚本")
    print("作者: OAK项目组")
    print("版本: 1.0.0")
    print("-" * 50)
    
    # 创建测试实例
    tester = OAKDeviceManagerTester()
    
    try:
        # 运行功能测试
        tester.run_all_tests()
        
        print(f"\n🎉 所有测试完成！")
        
        # 询问是否清理测试环境
        cleanup_choice = input("\n🧹 是否清理测试环境? [y/N]: ").strip().lower()
        if cleanup_choice in ['y', 'yes']:
            tester.cleanup()
        else:
            print("💾 测试文件保留在 test_configs/ 目录中")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中出现未预期的错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
