import os
from dotenv import load_dotenv
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env"))
load_dotenv(dotenv_path=env_path, override=True)

class MineruConfig:
    mineru_token = os.getenv("MINERU_TOKEN")
    mineru_base_url = os.getenv("MINERU_BASE_URL")




class LLMConfig:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    # .env 中的键名为 OPENAI_API_BASE，保留 OPENAI_BASE_URL 作为兼容回退
    openai_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("MODEL_NAME")
    llm_default_temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE"))
    llm_default_model = os.getenv("LLM_DEFAULT_MODEL")
    vl_model = os.getenv("VL_MODEL")
    item_model = os.getenv("ITEM_MODEL")
    model_provider = os.getenv("MODEL_PROVIDER")




class MinIOConfig:
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket_name = os.getenv("MINIO_BUCKET_NAME")
    minio_img_dir = os.getenv("MINIO_IMG_DIR")



class EmbeddingConfig:
    bge_m3_path=os.getenv("BGE_M3_PATH")
    bge_m3=os.getenv("BGE_M3")
    bge_device=os.getenv("BGE_DEVICE")
    bge_fp16=True if os.getenv("BGE_FP16") in ("True",1,True,"1") else False


class MilvusConfig:
    milvus_url = os.getenv('MILVUS_URL')
    chunks_collection = os.getenv('CHUNKS_COLLECTION')
    item_name_collection = os.getenv('ITEM_NAME_COLLECTION')


class MongoConfig:
    # mongo 服务地址
    mongo_url = os.getenv('MONGO_URL')
    mongo_db_name = os.getenv('MONGO_DB_NAME')


class McpConfig:
    mcp_base_url=os.getenv("MCP_DASHSCOPE_BASE_URL")
    api_key=os.getenv("OPENAI_API_KEY")


class RerankConfig:
    rerank_base_url=os.getenv('RERANK_BASE_URL')
    rerank_api_key=os.getenv('OPENAI_API_KEY')
