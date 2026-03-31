# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Дефолтные значения
#DEFAULT_METADATA_URL = "http://192.168.80.137:8085"
#DEFAULT_NGINX_URL = "http://192.168.80.137:8095"
DEFAULT_PRESETS_DIR = "./presets"
DEFAULT_METADATA_TIMEOUT = 30

# Обязательные параметры
METADATA_BASE_URL = os.getenv("METADATA_URL")
if not METADATA_BASE_URL:
    raise ValueError("METADATA_URL must be set in .env or environment")

NGINX_BASE_URL = os.getenv("NGINX_URL")
if not NGINX_BASE_URL:
    raise ValueError("NGINX_URL must be set in .env or environment")

# Переменные с fallback на дефолты
PRESETS_DIR = Path(os.getenv("PRESETS_DIR", DEFAULT_PRESETS_DIR))
METADATA_TIMEOUT = int(os.getenv("METADATA_TIMEOUT", DEFAULT_METADATA_TIMEOUT))

# Директории для пресетов
COLLECTIONS_DIR = PRESETS_DIR / "collections"
USERS_DIR = PRESETS_DIR / "users"