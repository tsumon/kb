# ============================================================
# atguigu/import_process/nodes/node_document_split.py
# ============================================================
# 作用：文档切分节点（NodeDocumentSplit）。
#       将长篇 Markdown 文本按语义边界智能切割为小块（chunks），
#       每块大小适中便于向量化后存入 Milvus 进行相似度检索。
#       当前为骨架代码，process() 只透传状态。
# ============================================================
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


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

    # 返回md文档内容，标题，路径对象
    def get_md_content(self,state): # 获取md文档内容
        md_path = state.get("md_path")
        if not md_path:
            logger.error("无md文档路径")
            raise Exception("无md文档路径")

        md_path_obj = Path(md_path)
        if not md_path_obj.exists():
            logger.error("md文档不存在")
            raise Exception("md文档不存在")

        file_title = state.get("file_title", "") or md_path_obj.stem # 获取md文档标题

        with open(md_path, "r", encoding="utf-8") as f: # 读取md文档内容
            md_content = f.read()

        if not md_content:
            logger.error("md文档内容为空")
            raise Exception("md文档内容为空")

        # 因不同操作系统换行符不统一，故先处理，统一换行符
        md_content = md_content.replace("\r\n", "\n").replace("\r","\n")
        return md_content, file_title, md_path_obj

    #md内容进行切割，根据标题合并section
    def get_section_list(self, md_content,file_title):
        md_line_list = md_content.split("\n") # 按行切分

        code_patten = r"^(`{3,}|~{3,})"
        title_patten = r'^\s*#{1,6}\s+.+'
        is_in_block = False
        marker = None
        current_idx = 0

        section_list = []
        for idx, line in enumerate(md_line_list):
            line = line.strip()
            match = re.match(code_patten, line)
            #判断行是否为标题，先判断是否在代码块内
            if match:
                if not is_in_block:
                    is_in_block = True
                    marker = match.group(1)
                    logger.info(f"代码块开始：{marker}")
                else:
                    if marker == match.group(1):
                        is_in_block = False
                        marker = None
                        logger.info(f"代码块结束：{marker}")
            #不在代码块内，判断是否为标题
            if not is_in_block and re.match(title_patten, line):  #符合标题正则，且在代码块外
                temp_list = md_line_list[current_idx:idx]
                content = "\n".join(temp_list)
                section_dict = {
                    "title":temp_list[0] if content.startswith('#') else "无标题",
                    "content":content,
                    "file_title":file_title,
                }
                section_list.append(section_dict)
                current_idx = idx # 更新当前索引

        # 循环中忽略了最后一个标题以及内容，所以需要单独处理
        section_list.append({
            "title":md_line_list[current_idx],
            "content":"\n".join(md_line_list[current_idx:]),
            "file_title":file_title,
        })
        return section_list


    # 接收已按标题切分好的章节列表，对每个章节的正文部分（去除标题后）进行二次切分（若正文超过 max_length），
    # 使每个切片长度不超过阈值，同时保证标题前缀被添加到每个切片内容中。
    # 此外，还会将表格内容（HTML标签 <table）整体保留，避免切碎；
    # 最终将处理后的所有切片写入 chunks.json 文件备份。
    def get_final_section_list(self, section_list,md_path_obj,file_title):
        #长切短合
        max_length = 300 # 最大长度
        over_lap = 30 # 重叠长度
        final_section_list = []

        spliter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
            chunk_size=max_length,
            chunk_overlap=over_lap
        )

        for section in section_list:
            content = section["content"]
            title = section["title"]

            real_content = content[len(title):] if content.startswith(title) else content
            #真实的内容 = content -title，得到真实内容后，再切分，完成后，在每个chuck前添加title

            if len(real_content) < max_length: # 如果真实内容长度小于阈值，则直接添加
                final_section_list.append({
                    **section,
                    "part":0
                })
                continue
            if "<table" in real_content: # 如果真实内容包含表格，则保留表格
                final_section_list.append({
                    **section,
                    "part":0
                })
                continue

            #真正切分
            splite_chunk_list = spliter.split_text(real_content)
            for idx, splite_chunk in enumerate(splite_chunk_list):
                final_section_list.append({
                    **section,
                    "content": title + "\n\n" + splite_chunk,
                    "part":idx
                })
        logger.info(json_format(final_section_list))

        # 备份chunks列表到json文件
        with open(md_path_obj.parent / "chunks.json", 'w', encoding='utf-8') as f:
            f.write(json_format(final_section_list))

        return final_section_list


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

        # 第一步：获取md文档内容，标题，路径对象
        md_content, file_title, md_path_obj = self.get_md_content(state)

        #第二步：md内容进行切割，根据标题合并section，
        section_list = self.get_section_list(md_content,file_title)

        final_section_list = self.get_final_section_list(section_list, md_path_obj, file_title)

        return {
            "chunks": final_section_list,
        }




if __name__ == '__main__':
    node = NodeDocumentSplit()
    init_state = {
        "md_path": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\hak180产品安全手册_new.md",
        "file_title":"hak180产品安全手册"
    }
    result = node(init_state)
    logger.info(json_format(result))