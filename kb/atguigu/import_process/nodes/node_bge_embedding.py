# ============================================================
# atguigu/import_process/nodes/node_bge_embedding.py
# ============================================================
# 作用：混合向量化节点（NodeBGEEmbedding）。
#       使用 BGE-M3 嵌入模型将文档切片转换为向量，
#       支持稠密向量 + 稀疏向量的混合检索，提升语义搜索的召回率。
# ============================================================
import json
import os

from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


class NodeBGEEmbedding(NodeBase):
    """
    混合向量化节点：使用 BGE-M3 模型将文档切片转换为向量。
    一个模型同时输出稠密（dense）与稀疏（sparse）两种向量，支持混合检索。
    """

    name = "node_bge_embedding"

    BATCH_SIZE = 3 # 每批编码的切片数量：控制显存占用与整体效率

    def process(self, state: ImportGraphState):
        """
        混合向量化入口：校验 → 分批向量化 → 备份 → 写回 state。
        BGE-M3 一次输出稠密 + 稀疏两种向量；编码文本为 item_name + content，
        携带主体语义以提升检索效果。备份文件为 {"chunks": [...]} 的 dict。
        """
        chunks = state.get("chunks", "")
        if not chunks:
            logger.error("chunks不能为空")
            raise ValueError("chunks不能为空")

        # 分批调用 BGE-M3 编码，向量写回每个切片
        for start in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[start:start + self.BATCH_SIZE]
            texts = [f"{chunk.get('item_name', '')}{chunk.get('content', '')}" for chunk in batch]
            embedding = get_bge_m3_embedding(texts)
            for idx, chunk in enumerate(batch):
                chunk["dense_vector"] = embedding.get("dense")[idx]
                chunk["sparse_vector"] = embedding.get("sparse")[idx]

        # 备份向量化后的 chunks，便于下游节点 / 测试读取
        with open(r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\chunks.json","w", encoding="utf-8") as f:
            f.write(json_format(chunks))
        return {"chunks": chunks}

if __name__ == '__main__':
    node = NodeBGEEmbedding()
    # 读取同目录下的 chunks 文件（由 node_document_split 备份产出）
    chunks_path = r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\chunks.json"
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    result = node({"chunks": chunks})
    logger.info(json_format(result))