# ============================================================
# atguigu/import_process/state.py
# ============================================================
# 作用：定义 LangGraph 工作流的状态类型 ImportGraphState。
#       类型化字典（TypedDict）让 IDE 提供自动补全和类型检查，
#       同时保持运行时就是普通 dict，兼容 LangGraph 引擎。
# ============================================================

# TypedDict：类型化字典，为普通 dict 的键指定类型，获得 IDE 补全 + 类型校验
from typing import TypedDict

class ImportGraphState(TypedDict):
    """
    图的状态定义，包含所有节点产生和消费的数据字段
    作用：作为 LangGraph 工作流中节点间传递的"共享数据总线"
          每个节点读取需要的字段，处理后写回新的字段
    """

    # ---------- 任务标识 ----------
    task_id: str
    # 任务唯一 ID（UUID），用于追踪日志和执行记录，贯穿整个工作流生命周期

    # ---------- 流程控制标记 ----------
    is_md_read_enabled: bool
    # 是否启用 Markdown 读取路径（True = 直接读 .md 文件，跳过 PDF 解析）

    is_pdf_read_enabled: bool
    # 是否启用 PDF 读取路径（True = 输入 PDF，需要先转换为 .md）

    # ---------- 文件路径相关 ----------
    local_dir: str
    # 当前工作目录或输出目录（所有中间文件和最终结果都放在此路径下）

    local_file_path: str
    # 原始输入文件的完整路径（用户上传的 PDF 或 Markdown 文件路径）

    file_title: str
    # 文件标题（由文件名去掉后缀得到，例如 "产品手册.pdf" → "产品手册"）

    pdf_path: str
    # PDF 文件路径（当输入为 PDF 时保存，用于后续的结构化解析）

    md_path: str
    # Markdown 文件路径（PDF 转换后或直接输入的 .md 文件位置）

    # ---------- 内容数据 ----------
    md_content: str
    # Markdown 的全文内容（字符串形式，用于后续的分片和向量化）

    chunks: list
    # 文档切片列表（将长文本按语义/策略切成的小段，每段是一个子文档）

    item_name: str
    # 识别主体的名称（例如：万用表、传感器、PLC 等设备名称）

    # ---------- 数据库关联 ----------
    embeddings_content: list
    # 包含向量数据的列表，准备写入 Milvus 向量数据库
    # 列表中的每个元素包含：原始文本 + 对应向量 + 元数据
