# ============================================================
# atguigu/import_process/nodes/node_bge_embedding.py
# ============================================================
# 作用：混合向量化节点（NodeBGEEmbedding）。
#       使用 BGE-M3 嵌入模型将文档切片转换为高维向量（embedding），
#       支持稠密向量 + 稀疏向量的混合检索，提升语义搜索的召回率。
#       当前为骨架代码，process() 只透传状态。
# ============================================================

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState

class NodeBGEEmbedding(NodeBase):
    """
    混合向量化节点：使用 BGE-M3 模型将文本转换为向量
    职责：
    1. 遍历 state.chunks 中的每个文档切片
    2. 调用 BGE-M3 嵌入模型进行向量编码
    3. 生成稠密向量（dense embedding）+ 稀疏向量（sparse embedding）
    4. 将文本 + 向量 + 元数据组装后存入 state.embeddings_content
    BGE-M3 特点：一个模型同时输出稠密和稀疏两种向量，支持混合检索
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_bge_embedding"
    name = "node_bge_embedding"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        BGE 向量化的核心逻辑（当前为骨架占位）
        预期实现：
        1. 加载 BGE-M3 模型（通过 HuggingFaceEmbeddings 或 FlagEmbedding）
        2. 对 state.chunks 逐条 encode，生成稠密向量
        3. 生成稀疏向量（lexical weights），用于 BM25 风格的词汇匹配
        4. 将每条结果的 text/vector/sparse_vector/metadata 存入 state.embeddings_content

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        return state
