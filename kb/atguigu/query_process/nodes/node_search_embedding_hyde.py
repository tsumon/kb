# atguigu/query_process/nodes/node_search_embedding_hyde.py

import json
from langchain.chat_models import init_chat_model
from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import HYDE_PROMPT
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybird
class NodeSearchEmbeddingHyde(NodeBase):
    """
    节点功能：HyDE (Hypothetical Document Embedding)
    先让 LLM 生成假设性答案，再对答案进行向量检索，提高召回率。
    """
    # 检索参数
    TOP_K = 10  # 每个主体返回的 Top-K 条
    RANKER = (0.8, 0.2)  # 稠密:稀疏 加权比例
    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_search_embedding_hyde"

    def get_hyde_embedding_chunks(self, item_names, merged_query):
        embedding = get_bge_m3_embedding([merged_query])
        collection_name = MilvusConfig.chunks_collection
        dense_data = embedding.get('dense')[0]
        sparse_data = embedding.get('sparse')[0]


        expr = f"item_name in {json.dumps(item_names, ensure_ascii=False)}"
        reqs = create_reqs(
            dense_data=dense_data,
            sparse_data=sparse_data,
            dense_anns_field="dense_vector",
            sparse_anns_field="sparse_vector",
            expr=expr
        )
        res = search_hybird(
            collection_name=collection_name,
            reqs=reqs,
            ranker=self.RANKER,
            limit=self.TOP_K,
            output_fields=['id', 'title', 'file_title', 'content', 'item_name']
        )

        # 无检索结果时返回空，避免 res[0] 越界
        if not res:
            logger.warning("【%s】Milvus 无检索结果，返回空", self.name)
            return []

        hyde_embedding_chunks = [
            {
                **(item.get("entity") or {}),
                "score": item.get("distance"),
                "source": "local"
            }
            for item in res[0]
        ]
        return hyde_embedding_chunks

    # 假设性回答的截断长度，防止 merged_query 过长影响向量检索
    HYDE_ANSWER_MAX_LEN = 500

    def get_hyde_answer(self, rewritten_query):
        llm = init_chat_model(
            model=LLMConfig.llm_default_model,
            model_provider=LLMConfig.model_provider,
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base,
            temperature=LLMConfig.llm_default_temperature,
        )
        messages = [
            {"role": "user", "content": HYDE_PROMPT.format(rewritten_query=rewritten_query)}
        ]
        res = llm.invoke(messages)

        # content 偶尔是列表（多模态那种），先统一拉成字符串再拼接
        hyde_answer = res.content
        if not isinstance(hyde_answer, str):
            hyde_answer = json.dumps(hyde_answer, ensure_ascii=False)

        merged_query = f"{rewritten_query}{hyde_answer.strip()[:self.HYDE_ANSWER_MAX_LEN]}"
        return merged_query

    def get_rewritten_query(self, state):
        rewritten_query = state.get("rewritten_query")
        item_names = state.get("item_names")
        if not rewritten_query:
            logger.error("【%s】rewritten_query is None", self.name)
            raise ValueError("rewritten_query is None")
        if not item_names:
            # 商品名未确认（LLM 未提取出/确认失败）：跳过本地检索，交给 web 搜索兜底
            logger.warning("【%s】item_names 为空，跳过本地检索", self.name)
            return [], rewritten_query

        # 清洗空串项
        item_names = [item.strip() for item in item_names if item.strip()]
        if not item_names:
            logger.warning("【%s】item_names 清洗后为空，跳过本地检索", self.name)
            return [], rewritten_query
        return item_names, rewritten_query


    def process(self, state: QueryGraphState):
        # 获取重写的问题
        item_names, rewritten_query = self.get_rewritten_query(state)
        if not item_names:
            return {"hyde_embedding_chunks": []}
        # 生成假设性答案并合并原始问题
        merged_query = self.get_hyde_answer(rewritten_query)
        # 混合搜索获取切片
        hyde_embedding_chunks = self.get_hyde_embedding_chunks(item_names, merged_query)

        return {
            "hyde_embedding_chunks": hyde_embedding_chunks
        }






if __name__ == "__main__":
    init_state = {
        "rewritten_query": "关于BrotherHAK180烫金机如何使用",
        "item_names": ["BrotherHAK180烫金机"]
    }
    node_search_embedding_hyde = NodeSearchEmbeddingHyde()
    result = node_search_embedding_hyde(init_state)
    logger.info(json_format(result))