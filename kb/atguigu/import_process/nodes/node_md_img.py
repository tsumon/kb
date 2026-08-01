# ============================================================
# atguigu/import_process/nodes/node_md_img.py
# ============================================================
# 作用：Markdown 图片处理节点（NodeMDImg）。
#       对 Markdown 中的图片进行多模态理解：
#       调用视觉语言模型（VLM）描述图片内容，生成图片摘要替代纯图片链接。
#       当前为骨架代码，process() 只透传状态。
# ============================================================

# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState

class NodeMDImg(NodeBase):
    """
    Markdown 图片处理节点：多模态图片理解
    职责：
    1. 从 Markdown 内容中提取所有图片引用（![]() 语法）
    2. 将图片发送给视觉语言模型（VLM / GPT-4o 等）
    3. 用模型生成的图片描述文本替换或补充原始图片链接
    4. 将增强后的 Markdown 写回 state.md_content
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_md_img"
    name = "node_md_img"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        Markdown 图片 → 文本描述的核心逻辑（当前为骨架占位）
        预期实现：
        1. 从 state.md_content 中正则匹配所有 ![](url) 或 <img> 标签
        2. 下载或读取本地图片文件
        3. 调用 VLM（如 GPT-4o）生成图片描述
        4. 将描述文本插入 Markdown，替代或补充图片链接
        5. 将处理后的 Markdown 写回 state.md_content

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        return state
