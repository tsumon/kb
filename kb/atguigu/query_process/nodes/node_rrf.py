# atguigu/query_process/nodes/node_rrf.py

from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger

class NodeRrf(NodeBase):
    """
    节点功能：Reciprocal Rank Fusion
    将多路召回的结果（向量、HyDE）进行加权融合排序。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_rrf"

    RRF_K = 60
    TOP_K = 10
    WEIGHT_EMBEDDING = 1
    WEIGHT_HYDE = 1

    @staticmethod
    def get_chunk_id(chunk):

        return chunk.get("id")

    def fuse(self, final_dict: dict, chunks: list, weight: float):
        """
        把一路召回结果按 RRF 公式累加进融合字典。

        分数 = 该路权重 / (k + 排名)，同一 chunk 出现在多路时分数累加。
        无唯一标识的 chunk 无法融合，直接跳过。
        """
        for idx, chunk in enumerate(chunks, start=1):
            chunk_id = self.get_chunk_id(chunk)
            if not chunk_id:
                continue

            contribution = weight / (self.RRF_K + idx)

            if chunk_id in final_dict:
                final_dict[chunk_id]["score"] += contribution
            else:
                # 拷贝一份，避免污染上游 state 里的原始数据
                new_chunk = dict(chunk)
                new_chunk["score"] = contribution
                final_dict[chunk_id] = new_chunk

    def process(self, state: QueryGraphState):

        # 各路召回缺失或为空时按空处理，不拖垮整个流程
        embedding_chunks = state.get("embedding_chunks") or []
        hyde_embedding_chunks = state.get("hyde_embedding_chunks") or []

        final_chunks_dict = {}
        self.fuse(final_chunks_dict, embedding_chunks, self.WEIGHT_EMBEDDING)
        self.fuse(final_chunks_dict, hyde_embedding_chunks, self.WEIGHT_HYDE)

        if not final_chunks_dict:
            logger.warning("【%s】无任何可融合的检索结果，返回空", self.name)
            return {"rrf_chunks": []}

        rrf_chunks = sorted(
            final_chunks_dict.values(),
            key=lambda x: x["score"],
            reverse=True,
        )
        logger.info("【%s】融合完成，共 %d 条，返回 Top-%d", self.name, len(rrf_chunks), self.TOP_K)
        return {"rrf_chunks": rrf_chunks[:self.TOP_K]}



if __name__ == "__main__":
    from atguigu.tool.json_format_tool import json_format

    init_state = {
        "embedding_chunks": [
            {
                "id": 468283442034639151,
                "title": "## HAK 180 烫金机",
                "file_title": "hak180产品安全手册",
                "content": "产品安全手册（含使用说明）……",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8348,
                "source": "local",
            },
            {
                "id": 468283442034639152,
                "title": "## HAK 180 烫金机",
                "file_title": "hak180产品安全手册",
                "content": "关于设备的维护……",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8282,
                "source": "local",
            },
        ],
        "hyde_embedding_chunks": [
            {
                "id": 468283442034639151,  # 与 embedding 重叠，用于验证融合
                "title": "## HAK 180 烫金机",
                "file_title": "hak180产品安全手册",
                "content": "产品安全手册（含使用说明）……",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8560,
                "source": "local",
            },
            {
                "id": 468283442034639155,
                "title": "## 设备",
                "file_title": "hak180产品安全手册",
                "content": "关于设备的警告……",
                "item_name": "BrotherHAK180烫金机",
                "score": 0.8215,
                "source": "local",
            },
        ],
    }

    node_rrf = NodeRrf()
    result = node_rrf(init_state)
    logger.info(json_format(result))
