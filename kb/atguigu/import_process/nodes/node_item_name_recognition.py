# ============================================================
# atguigu/import_process/nodes/node_item_name_recognition.py
# ============================================================
# 作用：主体识别节点（NodeItemNameRecognition）。
#       使用 LLM 从文档内容中自动识别核心主体名称（如设备名、产品名），
#       将识别结果作为标签写入 state.item_name，便于后续分类检索。
#       当前 process() 已实现"把前 10 个切片拼成 LLM 输入摘要"，
#       调用 LLM 识别主体并写回 state.item_name 待接入。
# ============================================================
import json

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


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
        主体识别的核心逻辑（当前实现摘要拼接，LLM 识别待接入）
        预期实现：
        1. 从 state.md_content 取前 N 个字符作为 LLM 输入（摘要即可判断主体）
        2. 构造提示词："这段文档讲的是什么设备/产品？只回答名称"
        3. 调用 ChatOpenAI / init_chat_model 获取回答
        4. 将回答清洗后写入 state.item_name

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """

        # 校验输入：主体识别依赖"分块内容"和"文档标题"，缺失则无法继续
        chunks = state.get("chunks")
        file_title = state.get("file_title")
        if not chunks:
            raise ValueError("文档分块不存在，无法进行主体识别")
        if not file_title:
            raise ValueError("文档标题不存在，无法进行主体识别")

        # 取前 10 个切片：判断主体只需看文档开头（标题/摘要即可定名），不必全文
        chunks_k_list = chunks[:10]
        # 摘要上限：控制 LLM 输入的 token 量，防止超出上下文窗口
        max_len = 10000
        content_str = "\n"
        for idx, chunk in enumerate(chunks_k_list):
            # 每个切片标注来源（切片序号 + 文档标题 + 切片标题），便于 LLM 定位主体
            chunk_str = (
                f"[切片{idx}]\n{file_title}\n"
                f"{chunk.get('title')}\n{chunk.get('content')}\n"
            )

            # 先判断"加了这个切片会不会超限"，超过则整体跳过——保证切片不被截断
            if len(content_str) + len(chunk_str) > max_len:
                logger.info("内容过长，已截断")
                break
            content_str += chunk_str

        return state




if __name__ == '__main__':
    node = NodeItemNameRecognition()
    with open(r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\chunks.json", "r", encoding="utf-8") as f:
        chunks_json = json.load(f)


    init_state = {
        "chunks": chunks_json,
        "file_title":"hak180产品安全手册"
    }
    result = node(init_state)
    logger.info(json_format(result))