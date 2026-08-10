# ============================================================
# atguigu/import_process/nodes/node_entry.py
# ============================================================
# 作用：入口节点（NodeEntry），工作流的第一个节点。
#       负责任务分发：根据输入文件的类型（PDF/MD）决定后续走哪条路径。
#       当前为骨架代码，process() 只透传状态。
# ============================================================
from pathlib import Path
from unittest import result

# 导入抽象基类 NodeBase，提供日志/异常包装
from atguigu.import_process.base import NodeBase
# 导入状态类型定义，用于类型注解和 IDE 自动补全
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.logger import logger


class NodeEntry(NodeBase):
    """
    入口节点：任务分发
    职责：
    1. 接收原始输入（文件路径、任务参数）
    2. 判断文件类型（PDF / MD），设置 is_pdf_read_enabled / is_md_read_enabled
    3. 决定后续工作流走哪条分支路径
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_entry"
    name = "node_entry"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        入口节点的核心逻辑（当前为骨架占位）
        预期实现：
        1. 从 state 中取出 local_file_path
        2. 根据文件后缀判断是 pdf 还是 md
        3. 设置 is_pdf_read_enabled / is_md_read_enabled 标记
        4. 提取 file_title（文件名去后缀）

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        local_file_path = state.get("local_file_path","")#防御性编程

        if not local_file_path:
            # 判断路径字符串是否提供
            logger.error("local_file_path is empty")
            raise ValueError("local_file_path is empty")
        local_file_path_obj = Path(local_file_path)

        if not local_file_path_obj.exists():
            # 判断路径文件是否存在
            logger.error("local_file_path is not exists")
            raise ValueError("local_file_path is not exists")
        #logger.info(f"local_file_path 文件开始进行入口判断")
        #判断文件是md还是pdf或其他,进行state赋值,后期可以根据这些值进行路由添加条件边

        file_title = local_file_path_obj.stem  #取文件名没后缀, .name是带后缀
        suffix = local_file_path_obj.suffix #取文件格式
        # 本地输出目录：默认取文件所在目录，供下游节点存放中间产物（md/zip/解压目录等）
        local_dir = str(local_file_path_obj.parent)
        if suffix.lower() == ".md":
            return {
                "file_title": file_title,
                "md_path": str(local_file_path_obj),
                "local_dir": local_dir,
                "is_md_read_enabled": True
            }
        elif suffix.lower() == ".pdf":
            return {
                "file_title": file_title,
                "pdf_path": str(local_file_path_obj),
                "local_dir": local_dir,
                "is_pdf_read_enabled": True
            }
        else:
            logger.error("不支持的文件类型")
            raise ValueError(f"不支持的文件类型:{suffix}")

if __name__ == '__main__':
    node = NodeEntry()
    init_state = {
        "local_file_path": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf"
    }
    result = node(init_state)
    logger.info(result)