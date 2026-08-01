# ============================================================
# atguigu/import_process/nodes/node_document_split.py
# ============================================================
# 作用：文档切分节点（NodeDocumentSplit）。
#       将长篇 Markdown 文本按语义边界智能切割为小块（chunks），
#       每块大小适中便于向量化后存入 Milvus 进行相似度检索。
#       当前为骨架代码，process() 只透传状态。
# ============================================================

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState

class NodeDocumentSplit(NodeBase):
    """
    文档切分节点：智能文档切片
    职责：
    1. 读取 state.md_content 中的 Markdown 全文
    2. 按标题层级（H1/H2/H3）、段落、Token 数等策略进行语义切分
    3. 生成切片列表，每个切片包含：文本内容 + 元数据（来源、页码等）
    4. 将切片列表写入 state.chunks
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_document_split"
    name = "node_document_split"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        文档切分的核心逻辑（当前为骨架占位）
        预期实现：
        1. 使用 LangChain 的 MarkdownHeaderTextSplitter 按标题切分
        2. 对大段文本用 RecursiveCharacterTextSplitter 二次切分
        3. 保留每个切片的元数据（来源文件、章节标题、chunk 序号等）
        4. 将切片列表存入 state.chunks

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        return state
