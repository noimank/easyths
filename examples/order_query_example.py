"""
委托查询操作示例

演示如何使用 order_query 操作查询股票委托订单信息
"""
import asyncio
import json
from src.automation.base_operation import operation_registry
from src.automation.operation_manager import OperationManager


async def main():
    # 初始化操作管理器
    config = {
        'plugin_dirs': ['src/automation/operations'],
        'auto_load': True
    }
    manager = OperationManager(config)
    manager.load_plugins()

    # 获取操作注册表
    registry = operation_registry

    # 检查 order_query 操作是否已注册
    order_query_class = registry.get_operation_class('order_query')
    if not order_query_class:
        print("❌ order_query 操作未找到，请确保已正确注册")
        return

    print("✅ order_query 操作已成功注册")

    # 创建操作实例
    order_query = await registry.get_operation_instance('order_query')

    # 示例1: 查询所有委托
    print("\n--- 示例1: 查询所有委托 ---")
    params1 = {
        "query_type": "all",
        "return_type": "str"
    }

    # 验证参数
    is_valid = await order_query.validate(params1)
    print(f"参数验证: {'✅ 通过' if is_valid else '❌ 失败'}")

    # 示例2: 查询特定股票的委托
    print("\n--- 示例2: 查询特定股票委托 ---")
    params2 = {
        "query_type": "all",
        "stock_code": "000001",
        "return_type": "json"
    }

    is_valid = await order_query.validate(params2)
    print(f"参数验证: {'✅ 通过' if is_valid else '❌ 失败'}")

    # 示例3: 查询买入委托
    print("\n--- 示例3: 查询买入委托 ---")
    params3 = {
        "query_type": "buy",
        "return_type": "dict"
    }

    is_valid = await order_query.validate(params3)
    print(f"参数验证: {'✅ 通过' if is_valid else '❌ 失败'}")

    # 示例4: 查询卖出委托
    print("\n--- 示例4: 查询卖出委托 ---")
    params4 = {
        "query_type": "sell",
        "return_type": "markdown"
    }

    is_valid = await order_query.validate(params4)
    print(f"参数验证: {'✅ 通过' if is_valid else '❌ 失败'}")

    # 显示操作元数据
    print("\n--- 操作元数据 ---")
    metadata = order_query.metadata
    print(f"名称: {metadata.name}")
    print(f"版本: {metadata.version}")
    print(f"描述: {metadata.description}")
    print(f"作者: {metadata.author}")
    print(f"操作名称: {metadata.operation_name}")

    print("\n--- 支持的参数 ---")
    for param_name, param_info in metadata.parameters.items():
        print(f"{param_name}:")
        for key, value in param_info.items():
            print(f"  {key}: {value}")

    print("\n✅ 委托查询操作示例完成")

    # 列出所有已注册的操作
    print("\n--- 所有已注册的操作 ---")
    operations = registry.list_operations()
    for op_name, op_metadata in operations.items():
        print(f"- {op_name}: {op_metadata.description}")


if __name__ == "__main__":
    asyncio.run(main())