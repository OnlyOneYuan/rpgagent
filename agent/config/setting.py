from enum import StrEnum
import os
from dotenv import load_dotenv

# 加载 .env 文件（默认会寻找当前目录下的 .env 文件）
load_dotenv()
api_key = os.getenv("API_KEY")
base_url = os.getenv("API_BASE", "127.0.0.1:7777")
model_name = os.getenv("MODEL_NAME")



class Authorize(StrEnum):
    KEY     = api_key
    URL     = base_url
    MODEL   = model_name

class Path(StrEnum):
    """
    Path constants
    """
    LABELS = r".agent/config/labels.json"
    SKILLS = r"./agent/tools"


