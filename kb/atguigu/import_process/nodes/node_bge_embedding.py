# ============================================================
# atguigu/import_process/nodes/node_bge_embedding.py
# ============================================================
# 作用：混合向量化节点（NodeBGEEmbedding）。
#       使用 BGE-M3 嵌入模型将文档切片转换为向量，
#       支持稠密向量 + 稀疏向量的混合检索，提升语义搜索的召回率。
# ============================================================
import json

·from atguigu.import_process.base import NodeBase
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
        混合向量化入口：校验 → 分批向量化。

        :param state: 工作流状态字典
        :return:     更新后的状态字典（chunks 已带 dense_vector / sparse_vector）
        """
        chunks = self.get_chunks(state)
        self.embed_chunks(chunks)
        return {"chunks": chunks}

    def get_chunks(self, state: ImportGraphState) :
        """校验并取出待向量化的切片列表。"""
        chunks = state.get("chunks", "")
        if not chunks:
            logger.error("chunks不能为空")
            raise ValueError("chunks不能为空")
        return chunks

    def embed_chunks(self, chunks: list):
        """分批调用 BGE-M3 编码切片，并把稠密 / 稀疏向量写回每个切片。"""
        for batch in self.iter_batches(chunks):
            texts = [self.build_embedding_text(chunk) for chunk in batch]
            embeddings = get_bge_m3_embedding(texts)
            for chunk, dense, sparse in zip(batch, embeddings["dense"], embeddings["sparse"]):
                chunk["dense_vector"] = dense
                chunk["sparse_vector"] = sparse

    def iter_batches(self, chunks: list):
        """按 BATCH_SIZE 分批切片，每次产出固定大小的子列表。"""
        for start in range(0, len(chunks), self.BATCH_SIZE):
            yield chunks[start:start + self.BATCH_SIZE]

    def build_embedding_text(self, chunk: dict) -> str:
        """组装编码文本：主体名 + 切片正文，携带主体语义以提升检索效果。"""
        return f"{chunk.get('item_name', '')}{chunk.get('content', '')}"


if __name__ == '__main__':
    node = NodeBGEEmbedding()
    # 读取同目录下的 chunks 文件（由 node_document_split 备份产出）
    chunks_path = r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\chunks.json"
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    result = node({"chunks": chunks})
    logger.info(json_format(result))