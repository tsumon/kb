# ============================================================
# atguigu/import_process/nodes/node_pdf_to_md.py
# ============================================================
# 作用：PDF 转 Markdown 节点（NodePDFToMD）。
#       将 PDF 文件进行结构化解析，转换为 Markdown 格式文本。
#       使用 OCR 或文档解析工具提取文字、表格、图片引用。
#       当前为骨架代码，process() 只透传状态。
# ============================================================

# 导入抽象基类，复用日志/异常模板方法
from atguigu.import_process.base import NodeBase
# 导入状态类型，获得 IDE 补全支持
from atguigu.import_process.state import ImportGraphState

class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF 结构化解析
    职责：
    1. 读取 PDF 文件（从 state.pdf_path 获取路径）
    2. 调用文档解析工具（如 MinerU / PyMuPDF / pdfplumber）提取内容
    3. 将文字、表格、图片引用转换为 Markdown 格式
    4. 将转换后的 Markdown 文本存入 state.md_content
    5. 将输出的 .md 文件路径存入 state.md_path
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_pdf_to_md"
    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        PDF → Markdown 的核心转换逻辑（当前为骨架占位）
        预期实现：
        1. 检查 is_pdf_read_enabled，确认需要执行 PDF 转换
        2. 读取 state.pdf_path 的 PDF 文件
        3. 调用 MinerU / pdfplumber 等工具解析 PDF
        4. 生成 .md 文件并写入磁盘
        5. 将 md_path 和 md_content 写回 state

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        return state
