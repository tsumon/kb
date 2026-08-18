# atguigu/query_process/nodes/node_answer_output.py
import re

from langchain.chat_models import init_chat_model

from atguigu.config.config import LLMConfig
from atguigu.config.prompt import ANSWER_PROMPT
from atguigu.query_process.base import NodeBase
from atguigu.query_process.state import QueryGraphState
from atguigu.tool.mongo_client_tool import add_or_update_history
from atguigu.tool.task_utils import put_data


class NodeAnswerOutput(NodeBase):
    """
    节点功能: 答案生成
    """

    name: str = "node_answer_output"

    def process(self, state: QueryGraphState):
        answer = state.get('answer')
        task_id = state.get('task_id')
        if answer:
            # 意图识别路径已经得到答案，直接放队列，后期sse推送到前端
            put_data(task_id, "delta", {"delta": answer})
            # 意图识别路径没有 reranked_docs，无图可提；也要发 final，否则前端永远等不到结束
            put_data(task_id, "final", {"answer": answer, "image_urls": []})
        else:
            # 组装 prompt，返回切片、商品名等信息
            chunks, item_names, prompt, rewritten_query = self.format_prompt(state)
            # 大模型流式生成答案
            answer = self.generat_answer(prompt, task_id)
            # 识别 chunks 中的图片 URL
            images = self.get_image_urls(chunks, state)
            # 答案写入历史记录，并把图片推送前端
            self.write_history(answer, images, item_names, rewritten_query, state, task_id)

        return {
            'answer': answer
        }

    def format_prompt(self, state):
        """拼接检索切片与历史对话，组装 ANSWER_PROMPT。"""
        chunks = state.get("reranked_docs")
        chunk_content = ""
        for i, chunk in enumerate(chunks):
            title = chunk.get("title")
            content = chunk.get("content")
            url = chunk.get("url")
            source = chunk.get("source")
            context = f"[{i}][{source}][{title}][{url}]\n{content}\n\n"
            chunk_content += context

        history = state.get("history")
        for h in history:
            h_content = f"[{h['role']}]{h['text']}\n\n"
            chunk_content += h_content

        item_names = state.get("item_names")
        item_names_str = ", ".join(item_names)

        rewritten_query = state.get("rewritten_query")

        prompt = ANSWER_PROMPT.format(
            context=chunk_content,
            history=history,
            item_names=item_names_str,
            question=rewritten_query)

        # 防止 prompt 超长
        prompt = prompt[:10000]
        return chunks, item_names, prompt, rewritten_query

    def generat_answer(self, prompt, task_id):
        """流式调用大模型生成答案，边生成边推送到前端。"""
        llm = init_chat_model(
            model=LLMConfig.item_model,
            model_provider=LLMConfig.model_provider,
            base_url=LLMConfig.openai_base,
            api_key=LLMConfig.openai_api_key,
            temperature=0.0
        )
        message = [{"role": "user", "content": prompt}]
        res = llm.stream(input=message)
        answer = ""  # 完整答案，存到 state
        for r in res:
            # 流式输出，答案放入队列，后续sse推送
            put_data(task_id, "delta", {"delta": r.content})
            answer += r.content
        return answer

    def get_image_urls(self, chunks, state):
        """识别 chunks 中的图片 URL。

        图片提取覆盖所有本地检索结果：reranked_docs 可能被 web 结果挤掉，
        但本地检索到的图片仍应作为附图展示。
        """
        seen = set()  # 用于去重，避免同一张图片重复出现
        md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        image_docs = list(chunks)
        for key in ("embedding_chunks", "hyde_embedding_chunks"):
            for doc in state.get(key) or []:
                if doc.get("source", "local") == "local":
                    image_docs.append(doc)
        for doc in image_docs:
            # 检查 text 字段中的 Markdown 图片 (主要针对 Local Chunk)
            text = doc.get("content")
            for img_url in md_img_pattern.findall(text):
                img_url = img_url.strip()
                if img_url and img_url not in seen:
                    seen.add(img_url)
        return list(seen)

    def write_history(self, answer, images, item_names, rewritten_query, state, task_id):
        """答案写入 MongoDB 历史，并推送 final 事件（含图片）。"""
        if answer:
            session_id = state.get('session_id')
            add_or_update_history(
                session_id=session_id,
                role="assistant",
                text=answer,
                rewritten_query=rewritten_query,
                item_names=item_names,
                image_urls=images
            )
        put_data(task_id, 'final', {"answer": answer, "image_urls": images})
