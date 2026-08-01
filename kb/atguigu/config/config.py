import os
from dotenv import load_dotenv
load_dotenv()


class MineruConfig:
    mineru_token = os.getenv("MINERU_TOKEN")
    mineru_base_url = os.getenv("MINERU_BASE_URL")




class OPENAIConfig:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("MODEL_NAME")

