# ============================================================
# atguigu/import_process/nodes/node_import_milvus.py
# ============================================================
# 作用：导入向量库节点（NodeImportMilvus）。
#       将向量化后的文档数据批量写入 Milvus 向量数据库，
#       支持后续的相似度搜索和 RAG（检索增强生成）问答。
# ============================================================
import json

from pymilvus import DataType

from atguigu.config.config import MilvusConfig
from atguigu.import_process.base import NodeBase
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.milvus_client_tool import get_milvus_client


class NodeImportMilvus(NodeBase):
    """
    导入向量库节点：数据持久化
    职责：
    1. 连接 Milvus 向量数据库
    2. 创建或选择目标 Collection（集合）
    3. 将向量化后的 chunks 批量 insert 到集合
    4. 创建索引（IVF_FLAT + SPARSE_INVERTED_INDEX）以加速检索
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_import_milvus"
    name = "node_import_milvus"

    # ---------- 集合 schema 字段长度上限（需与各 VARCHAR 字段一致） ----------
    FILE_TITLE_MAX_LEN = 100
    TITLE_MAX_LEN = 100
    CONTENT_MAX_LEN = 5000
    ITEM_NAME_MAX_LEN = 100

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        Milvus 导入入口：取分片 → 准备集合 → 幂等写入。

        :param state: 工作流状态字典
        :return:     更新后的状态字典（写回带 id 的 chunks）
        """

        #step 1: 获取分片数据
        chunks, dim, file_title = self.get_chunks(state)
        #step 2: 创建或选择集合
        collection_name, milvus_client = self.build_milvus_collection(dim)
        #step 3: 插入数据
        self.insert_data(chunks, collection_name, file_title, milvus_client)
        return {"chunks": chunks}

    def build_milvus_collection(self, dim: int) -> tuple[str, object]:
        """
        获取或创建目标集合（幂等：已存在则直接复用）。

        :param dim: 稠密向量的维度（由首个 chunk 推断）
        :return:   (collection_name, milvus_client)
        """
        milvus_client = get_milvus_client()
        collection_name = MilvusConfig.chunks_collection
        if not milvus_client:
            logger.error("milvus_client初始化失败")
            raise Exception("milvus_client初始化失败")

        if not milvus_client.has_collection(collection_name):
            schema = milvus_client.create_schema(auto_id=True)
            schema.add_field(
                field_name="id",
                datatype=DataType.INT64,
                is_primary=True,
            ).add_field(
                field_name="file_title",
                datatype=DataType.VARCHAR,
                max_length=self.FILE_TITLE_MAX_LEN,
            ).add_field(
                field_name="title",
                datatype=DataType.VARCHAR,
                max_length=self.TITLE_MAX_LEN,
            ).add_field(
                field_name="content",
                datatype=DataType.VARCHAR,
                max_length=self.CONTENT_MAX_LEN,
            ).add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=self.ITEM_NAME_MAX_LEN,
            ).add_field(
                field_name="part",
                datatype=DataType.INT64,
            ).add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=dim,
            ).add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR,
            )

            index_params = milvus_client.prepare_index_params()
            # 稠密向量索引：IVF_FLAT + COSINE，nlist/nprobe 加速检索
            index_params.add_index(
                field_name="dense_vector",
                index_type="IVF_FLAT",
                metric_type="COSINE",
                params={"nlist": 128, "nprobe": 10},
            )
            # 稀疏向量索引：L2 归一化后内积 (IP) 等价于余弦相似度；
            # 关闭量化保持原始精度（BGE-M3 输出已是 fp16 半精度，不再二次压缩）
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP",
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

    def get_chunks(self, state: ImportGraphState) -> tuple[list, int, str]:

        chunks = state.get("chunks")
        if not chunks:
            logger.error("没有chunks")
            raise Exception("没有chunks")

        first = chunks[0]
        dim = len(first["dense_vector"])
        file_title = first.get("file_title")
        for chunk in chunks:
            if not chunk.get("item_name"):
                chunk["item_name"] = chunk.get("title") or file_title
        return chunks, dim, file_title

    def insert_data(self, chunks: list, collection_name: str, file_title: str, milvus_client) -> None:
        "幂等写入：先删除同文件标题的旧记录，再批量插入新分片，最后回填 id。"
        milvus_client.load_collection(collection_name=collection_name)
        safe_title = self._escape_filter_value(file_title)
        milvus_client.delete(
            collection_name=collection_name,
            filter=f"file_title == '{safe_title}'",
        )

        res = milvus_client.insert(collection_name=collection_name, data=chunks)
        logger.info(res)
        ids = res.get("ids")
        if ids:
            for chunk, chunk_id in zip(chunks, ids):
                chunk["id"] = chunk_id

    @staticmethod
    def _escape_filter_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


if __name__ == '__main__':
    chunks_path = r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\chunks.json"
    with open(chunks_path, "r", encoding="utf-8") as f:
        init_state = {"chunks": json.load(f)}

    result = NodeImportMilvus()(init_state)
    logger.info(json_format(result))