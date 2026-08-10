# ============================================================
# atguigu/import_process/nodes/node_item_name_recognition.py
# ============================================================
# 作用：主体识别节点（NodeItemNameRecognition）。
#       使用 LLM 从文档内容中自动识别核心主体名称（如设备名、产品名），
#       将识别结果写入 state.item_name，便于后续分类检索。
# ============================================================
import json
from pathlib import Path

from langchain.chat_models import init_chat_model
from pymilvus import DataType

from atguigu.config.config import LLMConfig, MilvusConfig
from atguigu.config.prompt import ITEM_NAME_SYSTEM_PROMPT, ITEM_NAME_USER_PROMPT_TEMPLATE
# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.bgem3_client_tool import get_bge_m3_embedding
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client


class NodeItemNameRecognition(NodeBase):
    """
    主体识别节点：主体识别与标签提取
    职责：
    1. 读取 state.chunks 前若干切片 + state.file_title 拼接摘要
    2. 调用 LLM 进行 NER（命名实体识别），提取设备/产品名称
    3. 将识别出的主体名称写入 state.item_name，并向量化保存到 Milvus
    示例：输入"万用表2025产品手册"，识别出 item_name = "万用表"
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_item_name_recognition"
    name = "node_item_name_recognition"

    # 参与识别的切片数量上限：判断主体只需看文档开头，不必读全文
    HEAD_CHUNKS = 10
    # 摘要字符数上限：控制 LLM 输入的 token 量，防止超出上下文窗口
    CONTEXT_MAX_LEN = 10000
    # 商品名称字段在 Milvus 中的最大长度（VARCHAR max_length）
    ITEM_NAME_MAX_LEN = 100

    def process(self, state: ImportGraphState) :
        """
        主体识别的核心逻辑（步骤拆分）：
        1. 校验输入：chunks / file_title 必须存在
        2. 拼接摘要：取前若干切片拼接成 LLM 输入
        3. LLM 识别主体名称，并清洗 / 回退
        4. 准备 Milvus 集合（不存在则创建）
        5. 幂等写入：删除同名旧数据后，向量化插入

        :param state: 工作流状态字典
        :return:     更新后的状态字典
        """
        chunks, file_title = self.get_chunks(state)
        content_str = self.build_context(chunks, file_title)
        item_name = self.recognize_item_name(file_title, content_str)
        self.save_item_name(item_name, file_title)


        # 给每个切片打上 item_name 标签，便于下游节点向量化入库时带上主体名称
        for chunk in chunks:
            chunk["item_name"] = item_name

        # 写回状态，供下游节点使用
        state["item_name"] = item_name
        state["chunks"] = chunks

        # 备份打标后的 chunks，便于下游节点 / 测试读取
        local_dir = state.get("local_dir")
        if local_dir:
            backup_path = Path(local_dir) / "item_name_chunks.json"
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(json_format(chunks))

        return state

    # 步骤一：校验输入
    def get_chunks(self, state: ImportGraphState):
        """
        校验主体识别依赖的输入：分块内容 + 文档标题，缺失则无法继续。
        :return: (chunks, file_title)
        """
        chunks = state.get("chunks")
        file_title = state.get("file_title")
        if not chunks:
            raise ValueError("文档分块不存在，无法进行主体识别")
        if not file_title:
            raise ValueError("文档标题不存在，无法进行主体识别")
        return chunks, file_title

    # 步骤二：拼接摘要
    def build_context(self, chunks, file_title) -> str:
        """
        取前若干切片拼接成摘要，控制 LLM 输入规模。
        判断主体只需看文档开头（标题/摘要即可定名），不必全文。
        若加入某切片会超出上限则整体跳过，保证切片不被截断。
        """
        chunks_k_list = chunks[: self.HEAD_CHUNKS]
        content_str = ""  # 给最终拼接的摘要文本设一个初始换行符
        for idx, chunk in enumerate(chunks_k_list, start=1):
            # 每个切片标注来源（切片序号 + 文档标题 + 切片标题），便于 LLM 定位主体
            title = chunk.get("title")
            content = chunk.get("content")
            chunk_str = f"[切片{idx}]\n{file_title}\n{title}\n{content}\n"

            # 先判断"加了这个切片会不会超限"，超过则整体跳过——保证切片不被截断
            if len(content_str) + len(chunk_str) > self.CONTEXT_MAX_LEN:
                logger.info("内容过长，已截断")
                break
            content_str += chunk_str

        return content_str[: self.CONTEXT_MAX_LEN]

    # 步骤三：LLM 识别主体名称
    def recognize_item_name(self, file_title: str, context: str) -> str:
        """
        调用 LLM 识别商品名称，并做清洗 / 回退处理。
        - 清洗：去除空白与换行，避免脏字符混入商品名称
        - 回退：未识别出则用文档标题兜底（标题可能也无意义，但不阻塞入库）
        - 截断：限制到字段上限，避免超长 insert 报错
        """
        llm = init_chat_model(
            model = LLMConfig.item_model,
            model_provider = LLMConfig.model_provider,
            api_key = LLMConfig.openai_api_key,
            base_url = LLMConfig.openai_base,
            temperature = LLMConfig.llm_default_temperature,
        )

        messages = [
            {"role": "system", "content": ITEM_NAME_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ITEM_NAME_USER_PROMPT_TEMPLATE.format(file_title=file_title, context=context)
            }
        ]
        res = llm.invoke(messages)
        # LLM 可能返回 None 或结构异常，先兜底成空串再清洗，避免 AttributeError
        item_name = (res.content or "") if res else ""
        item_name = item_name.replace(" ", "").replace("\n", "").replace("\t", "")

        if not item_name:
            item_name = file_title

        return item_name[: self.ITEM_NAME_MAX_LEN]

    # 步骤四：准备 Milvus 集合（自包含：拿 client + 定集合名 + 创建）
    def create_milvus_collection(self):
        """
        创建商品主体集合（不存在则创建）并返回 (collection_name, milvus_client)。
        幂等：集合已存在则直接返回；返回 client 供调用方复用，避免重复连接。

        字段设计：
        - id 自增主键 + item_name / file_title 元数据 + 稠密 / 稀疏向量字段
        - dense 用 IVF_FLAT + COSINE（暴力检索 + nlist/nprobe 加速）
        - sparse 用 SPARSE_INVERTED_INDEX，metric 用 IP：
          normalize=True（L2 归一化）后内积等价于余弦相似度；
          quantization="none" 关闭量化，BGE-M3 输出的 fp16 向量不再二次压缩
        """
        milvus_client = get_milvus_client()
        if not milvus_client:
            logger.error("初始化milvus_client失败")
            raise Exception("初始化milvus_client失败")

        collection_name = MilvusConfig.item_name_collection
        if not milvus_client.has_collection(collection_name):  # 集合存在则直接返回
            schema = milvus_client.create_schema(
                auto_id=True,
            )
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True,
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=self.ITEM_NAME_MAX_LEN,
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=100,
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=1024,
            ).add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
            )

            index_params = milvus_client.prepare_index_params()
            # 添加稠密向量索引
            index_params.add_index(
                field_name="dense_vector",
                index_type="IVF_FLAT",  # 暴力检索
                metric_type="COSINE",
                params={"nlist": 128, "nprobe": 10},  # 提升召回效率
            )
            # 添加稀疏向量索引
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",  # L2 归一化后内积等价于余弦
                params={
                    "inverted_index_algo": "DAAT_MAXSCORE",  # 高效的稀疏检索算法
                    "normalize": True,
                    "quantization": "none",
                },
            )

            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )

        return collection_name, milvus_client

    # 步骤五：幂等写入 Milvus
    def save_item_name(self, item_name: str, file_title: str):
        """
        将识别出的商品名称向量化写入 Milvus：
        1. 准备/复用集合连接；集合加载后才能执行删除/查询；load 幂等
        2. 幂等删除同名历史数据，再插入，保证不产生重复主体
        3. BGE-M3 编码 item_name → 稠密 + 稀疏向量，写入集合
        """
        collection_name, milvus_client = self.create_milvus_collection()
        milvus_client.load_collection(collection_name)

        # 转义过滤表达式中的特殊字符：先转反斜杠，再转双引号，最后转单引号（顺序不能乱）
        safe_item_name = item_name.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
        milvus_client.delete(
            collection_name=collection_name,
            filter=f"item_name == '{safe_item_name}'",
        )

        # BGE-M3 编码 item_name → 稠密 + 稀疏向量，写入集合
        embedding = get_bge_m3_embedding([item_name])
        milvus_client.insert(
            collection_name=collection_name,
            data=[{
                "item_name": item_name,
                "file_title": file_title,
                "dense_vector": embedding.get("dense")[0],
                "sparse_vector": embedding.get("sparse")[0],
            }],
        )





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