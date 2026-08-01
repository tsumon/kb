# ============================================================
# atguigu/import_process/nodes/node_item_name_recognition.py
# ============================================================
# 作用：主体识别节点（NodeItemNameRecognition）。
#       使用 LLM 从文档内容中自动识别核心主体名称（如设备名、产品名），
#       将识别结果作为标签写入 state.item_name，便于后续分类检索。
#       当前为骨架代码，process() 只透传状态。
# ============================================================

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState

class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    职责：
    1. 读取 state.md_content（或 state.file_title）
    2. 调用 LLM 进行 NER（命名实体识别），提取设备/产品名称
    3. 将识别出的主体名称写入 state.item_name
    示例：输入"万用表2025产品手册"，识别出 item_name = "万用表"
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_item_name_recognition"
    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        主体识别的核心逻辑（当前为骨架占位）
        预期实现：
        1. 从 state.md_content 取前 N 个字符作为 LLM 输入（摘要即可判断主体）
        2. 构造提示词："这段文档讲的是什么设备/产品？只回答名称"
        3. 调用 ChatOpenAI / init_chat_model 获取回答
        4. 将回答清洗后写入 state.item_name

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        return state
