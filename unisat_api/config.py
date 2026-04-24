# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Дефолтные значения
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
USER_PRESETS_DIR = PRESETS_DIR / "user_presets"

# ========== НОВОЕ: определяем корень проекта и директорию data ==========
# Корень проекта (директория, содержащая unisat_api)
# __file__ = /path/to/unisat_access/unisat_api/config.py
# .parent = /path/to/unisat_access/unisat_api/
# .parent.parent = /path/to/unisat_access/
PROJECT_ROOT = Path(__file__).parent.parent

# Директория для данных (можно переопределить через переменную окружения)
DATA_DIR = Path(os.getenv("UNISAT_DATA_DIR", PROJECT_ROOT / "data"))
DOWNLOAD_DIR = DATA_DIR / "download"
PROCESSED_DIR = DATA_DIR / "processed"

# Создаём директории, если их нет
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_BASE_URL = os.getenv("PRODUCT_BASE_URL")
if not PRODUCT_BASE_URL:
    raise ValueError("PRODUCT_BASE_URL must be set in .env or environment")

UKEY = os.getenv("UKEY")
if not UKEY:
    raise ValueError("UKEY must be set in .env or environment")