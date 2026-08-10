# ============================================================
# atguigu/import_process/main_graph.py
# ============================================================
# 作用：定义文档导入流程的主工作流图（LangGraph StateGraph）。
#       编排 PDF→Markdown→图片处理→文档切分→主体识别→向量嵌入→Milvus入库
#       共 7 个节点的线性流水线，入口节点根据文件类型做条件路由。

# LangGraph 常量：END 表示工作流终止节点
from langgraph.constants import END
# LangGraph 核心：StateGraph 有状态工作流图构建器
from langgraph.graph import StateGraph
# 各流程节点类（每个节点封装一个处理步骤）
from atguigu.import_process.nodes.node_bge_embedding import NodeBGEEmbedding          # BGE 向量嵌入节点
from atguigu.import_process.nodes.node_document_split import NodeDocumentSplit        # 文档切分节点
from atguigu.import_process.nodes.node_entry import NodeEntry                         # 入口路由节点
from atguigu.import_process.nodes.node_import_milvus import NodeImportMilvus          # Milvus 入库节点
from atguigu.import_process.nodes.node_item_name_recognition import NodeItemNameRecognition  # 主体识别节点
from atguigu.import_process.nodes.node_md_img import NodeMDImg                        # Markdown 图片处理节点
from atguigu.import_process.nodes.node_pdf_to_md import NodePDFToMD                   # PDF 转 Markdown 节点
# 工作流共享状态类型（TypedDict，定义所有节点间传递的字段）
from atguigu.import_process.state import ImportGraphState
# JSON 格式化工具（用于美化输出日志）
from atguigu.tool.json_format_tool import json_format
# 全局彩色日志实例
from atguigu.tool.logger import logger


# 主图运行器：封装工作流图的构建、编译与执行
class MainGraphRunner:

    def __init__(self):
        self.builder = StateGraph(state_schema=ImportGraphState)
        self.add_nodes()
        self.add_edges()
        self.graph = None

    def add_nodes(self):
        """向图中注册所有处理节点（名称 + 可调用实例）。

        节点执行顺序由 add_edges() 中的边决定，此处仅为注册。
        每个节点都是 NodeBase 子类实例，通过 __call__ 方法执行。
        """
        self.builder.add_node(NodeEntry.name, NodeEntry())
        self.builder.add_node(NodePDFToMD.name, NodePDFToMD())
        self.builder.add_node(NodeMDImg.name, NodeMDImg())
        self.builder.add_node(NodeDocumentSplit.name, NodeDocumentSplit())
        self.builder.add_node(NodeItemNameRecognition.name, NodeItemNameRecognition())
        self.builder.add_node(NodeBGEEmbedding.name, NodeBGEEmbedding())
        self.builder.add_node(NodeImportMilvus.name, NodeImportMilvus())

    def add_edges(self):

        # 设置入口节点：工作流从 NodeEntry 开始执行
        self.builder.set_entry_point(NodeEntry.name)
        # 入口之后的条件路由：根据文件类型决定下一步
        # after_entry_router 返回下一个节点名称 或 END
        self.builder.add_conditional_edges(NodeEntry.name, self.after_entry_router)
        # 以下为线性流水线：前一个节点的输出直接流入下一个节点
        self.builder.add_edge(NodePDFToMD.name, NodeMDImg.name)                       # PDF→MD 完成后 → 图片处理
        self.builder.add_edge(NodeMDImg.name, NodeDocumentSplit.name)                  # 图片处理完成后 → 文档切分
        self.builder.add_edge(NodeDocumentSplit.name, NodeItemNameRecognition.name)    # 切分完成后 → 主体识别
        self.builder.add_edge(NodeItemNameRecognition.name, NodeBGEEmbedding.name)     # 识别完成后 → 向量嵌入
        self.builder.add_edge(NodeBGEEmbedding.name, NodeImportMilvus.name)            # 嵌入完成后 → Milvus 入库
        self.builder.add_edge(NodeImportMilvus.name, END)                              # 入库完成后 → 工作流结束

    def after_entry_router(self, state: ImportGraphState):

        # 读取状态中的 Markdown 启用标志（默认 False）
        is_md_read_enabled = state.get("is_md_read_enabled", False)
        # 读取状态中的 PDF 启用标志（默认 False）
        is_pdf_read_enabled = state.get("is_pdf_read_enabled", False)

        # PDF 文件：路由到 PDF 转 Markdown 节点
        if is_pdf_read_enabled:
            return NodePDFToMD.name
        # Markdown 文件：跳过 PDF 转换，直接进入图片处理节点
        elif is_md_read_enabled:
            return NodeMDImg.name
        # 都不启用：直接终止工作流
        else:
            return END

    def run(self, state: ImportGraphState):
        """编译并执行工作流图（首次调用时懒编译，后续复用已编译的图）。

        :param state: 初始状态字典，至少包含 local_file_path 字段
        :return: 工作流执行完毕后的最终状态字典
        """
        # 懒编译：只有首次调用时才编译图，后续调用复用编译结果
        if not self.graph:
            self.graph = self.builder.compile()
        # invoke 是 LangGraph 的同步执行入口，传入初始状态，返回最终状态
        return self.graph.invoke(state)

    @classmethod
    def create_and_run(cls, state):
        """类方法快捷入口：一行代码完成「创建实例 → 执行工作流」。

        等价于 MainGraphRunner().run(state)，适合简洁调用场景。

        :param state: 初始状态字典
        :return: 工作流最终状态字典
        """
        return cls().run(state)


# 模块直接运行入口（用于测试 / 单文件调试）
if __name__ == '__main__':
    # 构造初始状态：指定要导入的 PDF 文件路径
    init_state = {
        "local_file_path": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf"
    }
    # 一键运行整个文档导入流水线
    result = MainGraphRunner.create_and_run(init_state)
    # 将最终结果格式化后输出到日志
    logger.info(json_format(result))
