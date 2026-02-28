"""
别名管理DTO使用示例

演示如何使用别名管理相关的DTO进行配置管理。
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from oak_vision_system.core.dto.device_config_dto import (
    AliasBindingDTO,
    AliasHistoryDTO,
    AliasManagerConfigDTO,
    DeviceManagerConfigDTO
)


def example_1_create_alias_binding():
    """示例1：创建别名绑定"""
    print("=" * 60)
    print("示例1：创建别名绑定")
    print("=" * 60)
    
    # 创建左相机的别名绑定
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=[
            "14442C10D13D0D0000",
            "14442C10D13D0D0001",
            "14442C10D13D0D0002"
        ],
        device_label="左侧主相机"
    )
    
    print(f"✅ 创建别名: {left_binding.alias}")
    print(f"   设备标签: {left_binding.device_label}")
    print(f"   可用MXid数量: {left_binding.mxid_count}")
    print(f"   可用MXid列表: {left_binding.get_mxids_display()}")
    print(f"   创建时间: {left_binding.created_time_str}")
    
    # 验证
    if left_binding.validate():
        print("✅ 别名绑定验证通过")
    else:
        print(f"❌ 验证失败: {left_binding.get_validation_errors()}")
    
    print()


def example_2_alias_manager_config():
    """示例2：创建别名管理器配置"""
    print("=" * 60)
    print("示例2：创建别名管理器配置")
    print("=" * 60)
    
    # 创建别名管理器配置
    alias_config = AliasManagerConfigDTO(
        predefined_aliases=["left_camera", "right_camera"],
        strict_mode=True,
        max_history_entries=1000
    )
    
    # 添加左相机绑定
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=["14442C10D13D0D0000", "14442C10D13D0D0001"],
        device_label="左侧主相机"
    )
    alias_config.bindings["left_camera"] = left_binding
    
    # 添加右相机绑定
    right_binding = AliasBindingDTO(
        alias="right_camera",
        available_mxids=["14442C10D13D0D0002"],
        device_label="右侧相机"
    )
    alias_config.bindings["right_camera"] = right_binding
    
    print(f"✅ 别名管理器配置创建成功")
    print(f"   别名总数: {alias_config.alias_count}")
    print(f"   预定义别名: {alias_config.predefined_aliases}")
    print(f"   严格模式: {alias_config.strict_mode}")
    print(f"   MXid总数（去重）: {alias_config.total_mxid_count}")
    
    # 验证
    if alias_config.validate():
        print("✅ 配置验证通过")
    else:
        print(f"❌ 验证失败: {alias_config.get_validation_errors()}")
    
    print()


def example_3_query_operations():
    """示例3：查询操作"""
    print("=" * 60)
    print("示例3：查询操作")
    print("=" * 60)
    
    # 创建配置
    alias_config = AliasManagerConfigDTO()
    
    # 添加绑定
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=["14442C10D13D0D0000", "14442C10D13D0D0001"],
    )
    alias_config.bindings["left_camera"] = left_binding
    
    # 查询操作
    print("1. 检查别名是否存在")
    print(f"   has_alias('left_camera'): {alias_config.has_alias('left_camera')}")
    print(f"   has_alias('center_camera'): {alias_config.has_alias('center_camera')}")
    
    print("\n2. 获取可用MXid列表")
    available = alias_config.get_available_mxids("left_camera")
    print(f"   left_camera的可用MXid: {available}")
    
    print("\n3. 检查MXid是否被使用")
    mxid = "14442C10D13D0D0000"
    if alias_config.has_mxid(mxid):
        aliases = alias_config.get_aliases_by_mxid(mxid)
        print(f"   MXid '{mxid[-8:]}' 被以下别名使用: {aliases}")
    
    print()


def example_4_conflict_detection():
    """示例4：冲突检测"""
    print("=" * 60)
    print("示例4：冲突检测")
    print("=" * 60)
    
    # 创建配置
    alias_config = AliasManagerConfigDTO()
    
    # 创建两个别名，都激活同一个MXid（模拟冲突）
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=["14442C10D13D0D0000"]
    )
    left_binding.active_mxid = "14442C10D13D0D0000"  # 激活
    
    right_binding = AliasBindingDTO(
        alias="right_camera",
        available_mxids=["14442C10D13D0D0000"]  # 同一个MXid
    )
    right_binding.active_mxid = "14442C10D13D0D0000"  # 也激活
    
    alias_config.bindings["left_camera"] = left_binding
    alias_config.bindings["right_camera"] = right_binding
    
    # 获取冲突报告
    report = alias_config.get_conflict_report()
    
    if report["has_conflicts"]:
        print("❌ 检测到配置冲突！")
        print(f"   冲突数量: {report['conflict_count']}")
        print("   冲突详情:")
        for detail in report["conflict_details"]:
            print(f"     - {detail}")
    else:
        print("✅ 无配置冲突")
    
    # 验证也会检测冲突
    print("\n尝试验证配置...")
    if not alias_config.validate():
        print("❌ 配置验证失败:")
        for error in alias_config.get_validation_errors():
            print(f"   - {error}")
    
    print()


def example_5_history_tracking():
    """示例5：历史记录追踪"""
    print("=" * 60)
    print("示例5：历史记录追踪")
    print("=" * 60)
    
    # 创建历史记录
    history1 = AliasHistoryDTO(
        alias="left_camera",
        operation="create",
        reason="初始化配置",
        operator="admin"
    )
    
    history2 = AliasHistoryDTO(
        alias="left_camera",
        operation="add_mxid",
        mxid="14442C10D13D0D0001",
        reason="添加备用设备",
        operator="admin"
    )
    
    history3 = AliasHistoryDTO(
        alias="left_camera",
        operation="remove_mxid",
        mxid="14442C10D13D0D0000",
        old_value="14442C10D13D0D0000",
        reason="设备损坏",
        operator="admin"
    )
    
    # 添加到配置
    alias_config = AliasManagerConfigDTO()
    alias_config.history.extend([history1, history2, history3])
    
    print(f"✅ 历史记录总数: {alias_config.history_count}")
    print("\n历史记录详情:")
    for i, record in enumerate(alias_config.history, 1):
        print(f"\n{i}. {record.get_summary()}")
    
    print()


def example_6_device_manager_integration():
    """示例6：集成到DeviceManagerConfigDTO"""
    print("=" * 60)
    print("示例6：集成到DeviceManagerConfigDTO")
    print("=" * 60)
    
    # 创建完整的设备管理器配置
    config = DeviceManagerConfigDTO()
    
    # 配置别名绑定
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=["14442C10D13D0D0000", "14442C10D13D0D0001"],
        device_label="左侧主相机"
    )
    config.alias_manager.bindings["left_camera"] = left_binding
    
    # 模拟运行时：设置激活的MXid
    left_binding.active_mxid = "14442C10D13D0D0000"
    
    print("✅ DeviceManagerConfigDTO 配置创建成功")
    print(f"   配置版本: {config.config_version}")
    
    # 使用便捷接口查询
    print("\n使用便捷接口查询:")
    print(f"1. 检查别名是否存在")
    print(f"   has_alias('left_camera'): {config.has_alias('left_camera')}")
    
    print(f"\n2. 获取激活的MXid")
    active_mxid = config.get_mxid_by_alias("left_camera")
    print(f"   left_camera的激活MXid: {active_mxid}")
    
    print(f"\n3. 获取可用MXid列表")
    available = config.get_available_mxids_by_alias("left_camera")
    print(f"   left_camera的可用MXid: {available}")
    
    print(f"\n4. 反向查询：通过MXid获取别名")
    alias = config.get_alias_by_mxid(active_mxid, check_active_only=True)
    print(f"   MXid '{active_mxid}' 对应的别名: {alias}")
    
    print(f"\n5. 获取所有别名绑定")
    all_bindings = config.get_all_alias_bindings()
    print(f"   所有别名绑定: {all_bindings}")
    
    # 验证整个配置
    print("\n验证整个配置...")
    if config.validate():
        print("✅ 配置验证通过")
    else:
        print(f"❌ 验证失败: {config.get_validation_errors()}")
    
    print()


def example_7_serialization():
    """示例7：JSON序列化和反序列化"""
    print("=" * 60)
    print("示例7：JSON序列化和反序列化")
    print("=" * 60)
    
    # 创建配置
    config = DeviceManagerConfigDTO()
    
    # 添加别名绑定
    left_binding = AliasBindingDTO(
        alias="left_camera",
        available_mxids=["14442C10D13D0D0000"],
        device_label="左侧主相机"
    )
    config.alias_manager.bindings["left_camera"] = left_binding
    
    # 序列化为字典
    print("1. 序列化为字典")
    config_dict = config.to_dict()
    print(f"   ✅ 配置已序列化")
    print(f"   别名管理器键: {list(config_dict['alias_manager'].keys())}")
    
    # 反序列化
    print("\n2. 从字典反序列化")
    restored_config = DeviceManagerConfigDTO.from_dict(config_dict)
    print(f"   ✅ 配置已恢复")
    print(f"   别名数量: {restored_config.alias_manager.alias_count}")
    print(f"   left_camera的可用MXid: {restored_config.get_available_mxids_by_alias('left_camera')}")
    
    # 验证恢复的配置
    if restored_config.validate():
        print("   ✅ 恢复的配置验证通过")
    else:
        print(f"   ❌ 验证失败: {restored_config.get_validation_errors()}")
    
    print()


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("别名管理DTO使用示例")
    print("=" * 60 + "\n")
    
    try:
        example_1_create_alias_binding()
        example_2_alias_manager_config()
        example_3_query_operations()
        example_4_conflict_detection()
        example_5_history_tracking()
        example_6_device_manager_integration()
        example_7_serialization()
        
        print("=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

