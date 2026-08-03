import os
from dotenv import load_dotenv
load_dotenv()


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

