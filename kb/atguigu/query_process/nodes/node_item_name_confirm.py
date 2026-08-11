# atguigu/query_process/nodes/node_item_name_confirm.py

import json

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import ITEM_NAME_EXTRACT_SYSTEM_PROMPT, ITEM_NAME_EXTRACT_TEMPLATE
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import create_reqs, search_hybird
from atguigu.tool.mongo_client_tool import add_or_update_history, get_recent_history_list, update_item_names_and_query


class NodeItemNameConfirm(NodeBase):
    """
    商品名确认。

    从问题里扒出商品名，去向量库里比对一下，
    确认到具体哪款产品最好；拿不准就反问用户让他选。
    """

    name: str = "node_item_name_confirm"

    # 相似度阈值
    CONFIRM_THRESHOLD = 0.85
    OPTION_THRESHOLD = 0.6

    # 获取历史内容
    @staticmethod
    def get_history_content(state):
        session_id = state.get("session_id")
        if not session_id:
            logger.error("session_id不能为空")
            raise ValueError("session_id不能为空")

        original_query = state.get("original_query")
        if not original_query:
            logger.error("original_query不能为空")
            raise ValueError("original_query不能为空")

        # 这次提问先落库，拿到 message_id，后面回填要用
        message_id = add_or_update_history(session_id, "user", original_query)

        # 最近 10 条拼成字符串，连用户带助手的话一起喂给大模型
        history_list = get_recent_history_list(session_id, limit=10)
        history_content = "".join(
            f"{history.get('role')}: {history.get('text')}\n"
            for history in history_list
        )
        return history_content, message_id, original_query, session_id

    # 从历史内容里扒商品名
    @staticmethod
    def get_item_names(history_content, original_query):
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider="openai",
            api_key=LLMConfig.openai_api_key,
            base_url=LLMConfig.openai_base,
            temperature=LLMConfig.llm_default_temperature,
        )
        messages = [
            {"role": "system", "content": ITEM_NAME_EXTRACT_SYSTEM_PROMPT},
            {"role": "user",
             "content": ITEM_NAME_EXTRACT_TEMPLATE.format(history_text=history_content, original_query=original_query)},
        ]
        res = llm.invoke(input=messages)

        # content 偶尔会是列表（多模态那种），先统一拉成字符串再往下走
        res_json = res.content
        if not isinstance(res_json, str):
            res_json = json.dumps(res_json, ensure_ascii=False)

        # 模型抽风会包一层 ```json ```，扒掉再说
        if res_json.startswith("```json"):
            res_json = res_json.replace("```json", "").replace("```", "")

        # 解析挂了就当没识别出来，别把流程带崩
        try:
            res_dict = json.loads(res_json)
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.error(f"商品名提取结果解析失败: {e}")
            return [], original_query

        item_names = res_dict.get("item_names")
        rewritten_query = res_dict.get("rewritten_query")

        # 商品名里常混进空格换行，洗一遍
        item_names = [
            item_name.replace(" ", "").replace("\n", "").replace("\t", "")
            for item_name in (item_names or [])
        ]
        # 没改写就退回原始问题
        if not rewritten_query:
            rewritten_query = original_query
        return item_names, rewritten_query

    # 批量向量化，去向量库比对
    @staticmethod
    def get_final_search_item_names(item_names):
        # 先批量向量化，省得一个个调
        embeddings = get_bge_m3_embedding(item_names)
        collection_name = MilvusConfig.item_name_collection

        final_search_item_names = []
        for idx, item_name in enumerate(item_names):
            # 取当前这个名字的稠密 + 稀疏向量
            dense_data = embeddings.get("dense")[idx]
            sparse_data = embeddings.get("sparse")[idx]

            # 稠密稀疏一起查，命中率更高
            reqs = create_reqs(
                dense_data=dense_data,
                sparse_data=sparse_data,
                dense_anns_field="dense_vector",
                sparse_anns_field="sparse_vector",
            )

            # Top10，稠密稀疏按 8:2 加权
            res = search_hybird(
                collection_name=collection_name,
                reqs=reqs,
                ranker=(0.8, 0.2),
                limit=10,
                output_fields=["item_name"],
            )

            # 捋成 [原始名, 库里的标准名, 分数] 方便后面判断
            search_item_names = [
                {
                    "original_item_name": item_name,
                    "search_item_name": item.get("entity", {}).get("item_name", ""),
                    "score": item.get("distance"),
                }
                for item in res[0]
            ]
            final_search_item_names.extend(search_item_names)
        return final_search_item_names
    # 对比结果排序，分高的直接信，中等列出来让用户挑

    # 对齐商品名
    @staticmethod
    def align_item_names(final_search_item_names):
        # 分高的直接信，中等列出来让用户挑
        confirm_item_names = [
            item.get("search_item_name")
            for item in final_search_item_names
            if item.get("score") >= NodeItemNameConfirm.CONFIRM_THRESHOLD
        ]
        option_item_names = [
            item.get("search_item_name")
            for item in final_search_item_names
            if NodeItemNameConfirm.OPTION_THRESHOLD <= item.get("score") < NodeItemNameConfirm.CONFIRM_THRESHOLD
        ]

        if confirm_item_names:
            return "", confirm_item_names
        if option_item_names:
            return f"请确认你要咨询的商品是这些的哪一个？{','.join(option_item_names)}", []
        return "对不起，我无法识别你要咨询的商品名称，请重新提问。", []

    # 回填历史
    @staticmethod
    def handler_history(answer, final_item_names, message_id, rewritten_query, session_id):
        # 有回答（反问/拒识）就把助手这句也存进去
        if answer:
            message_id = add_or_update_history(session_id, "assistant", answer)

        # 不管有没有回答，最近 10 条都回填上商品名和改写后的问题
        history_list = get_recent_history_list(session_id, limit=10)
        ids = [history.get("_id") for history in history_list]
        if ids:
            update_item_names_and_query(ids, final_item_names, rewritten_query)
        return message_id

    def process(self, state: QueryGraphState):
        # 先把历史读出来、当前问题存库
        history_content, message_id, original_query, session_id = self.get_history_content(state)

        # 让大模型提商品名 + 重写问题
        item_names, rewritten_query = self.get_item_names(history_content, original_query)

        answer, final_item_names = "", []
        if item_names:
            # 有商品名才值得去向量库查一把
            final_search_item_names = self.get_final_search_item_names(item_names)

            # 按分数定结果：确认 / 反问 / 拒识
            answer, final_item_names = self.align_item_names(final_search_item_names)

        # 收尾：写历史，把结果带出去
        message_id = self.handler_history(answer, final_item_names, message_id, rewritten_query, session_id)

        return {
            "message_id": message_id,
            "original_query": original_query,
            "answer": answer,
            "item_names": final_item_names,
            "rewritten_query": rewritten_query,
            "history": get_recent_history_list(session_id, limit=10),
        }


if __name__ == '__main__':
    # 先塞几条测试数据
    session_id = "test_001"
    add_or_update_history(session_id, "user", "咨询下烫金机。")
    add_or_update_history(session_id, "assistant", "您好。请问是哪个型号")
    add_or_update_history(session_id, "user", "hak180")
    add_or_update_history(session_id, "assistant", "具体有什么问题呢？")

    init_state = {
        "session_id": "test_001",
        "original_query": "咋用？",
    }

    node = NodeItemNameConfirm()
    result = node(init_state)
    logger.info(json_format(result))