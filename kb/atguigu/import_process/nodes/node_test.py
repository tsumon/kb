# ============================================================
# atguigu/import_process/nodes/node_test.py
# ============================================================
# 作用：测试节点（NodeTest）。
#       提供一个可独立运行的模板，用于验证：
#       1. NodeBase 的日志和异常包装是否正常工作
#       2. 单个节点的 process() 逻辑是否正确
#       3. 工作流状态在不同节点间的传递是否符合预期
# ============================================================

# json 模块：将 Python 对象序列化为 JSON 字符串，方便打印调试状态
import json
# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState
# 导入全局彩色日志实例
from atguigu.tool.logger import logger

class NodeTest(NodeBase):
    """
    节点功能：测试
    这是一个最小可运行的节点示例，
    开发者可以复制此文件快速创建新节点
    """

    # 覆盖基类的 name 属性，标识节点名称为 "node_test"
    name: str = "node_test"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        测试节点的示例逻辑：仅打印一行日志
        开发者可在此处实验新功能，验证通过后再迁移到正式节点

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        # 使用 f-string 格式化日志，方便追踪是哪个节点输出的
        logger.info(f"【{self.name}】节点逻辑")
        return state

# ----------------------------------------------------------
# 模块自测入口：当直接运行此文件时执行单元测试
# 用法：python -m atguigu.import_process.nodes.node_test
# ----------------------------------------------------------
if __name__ == "__main__":
    # 初始化图状态 —— 模拟工作流传入一个 PDF 文件路径
    # init_state 是一个普通 dict（Python 的 TypedDict 在运行时就是 dict）
    init_state = {"local_file_path": r"D:\doc\hak180产品安全手册.pdf"}

    # 创建测试节点实例（会触发 __init__ 中的 name 检查）
    node_test = NodeTest()
    # 调用节点（NodeBase 的 __call__ 包装 → 自动打印开始/完成日志 → 调用 process）
    result = node_test(init_state)
    # 将返回的状态字典序列化为 JSON 字符串（ensure_ascii=False 保留中文，indent=4 格式化缩进）
    json_state = json.dumps(result, ensure_ascii=False, indent=4)
    # 输出 JSON 格式的状态，便于检查节点是否正确处理了状态数据
    logger.info(json_state)
