# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Defaults
DEFAULT_PRESETS_DIR = "./presets"
DEFAULT_METADATA_TIMEOUT = 30

# Required parameters
METADATA_BASE_URL = os.getenv("METADATA_URL")
if not METADATA_BASE_URL:
    raise ValueError("METADATA_URL must be set in .env or environment")

NGINX_BASE_URL = os.getenv("NGINX_URL")
if not NGINX_BASE_URL:
    raise ValueError("NGINX_URL must be set in .env or environment")

PRODUCT_BASE_URL = os.getenv("PRODUCT_BASE_URL")
if not PRODUCT_BASE_URL:
    raise ValueError("PRODUCT_BASE_URL must be set in .env or environment")

UKEY = os.getenv("UKEY")
if not UKEY:
    raise ValueError("UKEY must be set in .env or environment")

# Optional with defaults
PRESETS_DIR = Path(os.getenv("PRESETS_DIR", DEFAULT_PRESETS_DIR))
METADATA_TIMEOUT = int(os.getenv("METADATA_TIMEOUT", DEFAULT_METADATA_TIMEOUT))

# Preset directories
COLLECTIONS_DIR = PRESETS_DIR / "collections"
USER_PRESETS_DIR = PRESETS_DIR / "user_presets"

# Project root and data directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("UNISAT_DATA_DIR", PROJECT_ROOT / "data"))

# Predefined directories
DOWNLOAD_DIR = DATA_DIR / "_download"
PRODUCTS_DIR = DATA_DIR / "_product"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)