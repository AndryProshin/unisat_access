# config.py

from pathlib import Path

# Базовый URL сервиса метаданных (без параметра request)
METADATA_BASE_URL = "http://192.168.80.137:8085"
#METADATA_BASE_URL = "http://193.232.9.177:8085"

# Таймаут запросов (секунды)
METADATA_TIMEOUT = 10

# Директория с пресетами
PRESETS_DIR = Path("./presets")

NGINX_BASE_URL = "http://192.168.80.137:8095/unisat_hrsat"

