# atguigu/query_process/nodes/node_search_embedding.py

import json
from atguigu.config.config import MilvusConfig
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybird



class NodeSearchEmbedding(NodeBase):
    """
    节点功能：基于已确认主体名+改写后的用户问题，执行Milvus向量数据库混合检索
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding"

    # 检索参数
    TOP_K = 10  # 每个主体返回的 Top-K 条
    RANKER = (0.8, 0.2)  # 稠密:稀疏 加权比例

    @staticmethod
    def get_query_embeddings(rewritten_query):
        """
        向量化改写后的问题，返回 (稠密向量, 稀疏向量)。
        """
        embeddings = get_bge_m3_embedding([rewritten_query])
        return embeddings.get("dense")[0], embeddings.get("sparse")[0]

    @staticmethod
    def build_search_expr(item_names) -> str:
        """
        组装标量字段过滤表达式：item_name in [...]

        json.dumps 自带转义，无需手动处理；ensure_ascii=False 保持中文可读。
        """
        return f"item_name in {json.dumps(item_names, ensure_ascii=False)}"

    def search_milvus(self, dense_data, sparse_data, expr):
        """
        执行 Milvus 混合检索，返回原始检索结果。
        """
        reqs = create_reqs(
            dense_data=dense_data,
            sparse_data=sparse_data,
            dense_anns_field="dense_vector",
            sparse_anns_field="sparse_vector",
            expr=expr,
        )

        return search_hybird(
            collection_name=MilvusConfig.chunks_collection,
            reqs=reqs,
            ranker=self.RANKER,
            limit=self.TOP_K,
            output_fields=['id', 'title', 'file_title', 'content', 'item_name'],
        )

    @staticmethod
    def build_embedding_chunks(res) -> list:
        """
        把 Milvus 原始检索结果整理成 embedding_chunks 结构。
        无结果时返回空列表。
        """
        if not res:
            logger.warning("【%s】Milvus 无检索结果，返回空", NodeSearchEmbedding.name)
            return []

        return [
            {
                **(item.get("entity") or {}),
                "score": item.get("distance"),
                "source": "local",
            }
            for item in res[0]
        ]


    def process(self, state: QueryGraphState):
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """
        rewritten_query = state.get("rewritten_query")
        item_names = state.get("item_names")
        if not rewritten_query:
            logger.error(" rewritten_query is None")
            raise ValueError("rewritten_query is None")

        if not item_names:
            # 商品名未确认（LLM 未提取出/确认失败）：跳过本地检索，交给 web 搜索兜底
            logger.warning("【%s】item_names 为空，跳过本地检索", self.name)
            return {"embedding_chunks": []}

        # 1. 向量化改写后的问题
        dense_data, sparse_data = self.get_query_embeddings(rewritten_query)

        # 2. 组装标量过滤表达式
        expr = self.build_search_expr(item_names)

        # 3. 执行混合检索
        res = self.search_milvus(dense_data, sparse_data, expr)

        # 4. 整理成节点输出格式
        return {"embedding_chunks": self.build_embedding_chunks(res)}




if __name__ == "__main__":
    init_state = {
        "rewritten_query": "Brother 180烫金机怎么用",
        "item_names": ["BrotherHAK180烫金机"]
    }
    node_search_embedding = NodeSearchEmbedding()
    result = node_search_embedding(init_state)
    logger.info(json_format(result))