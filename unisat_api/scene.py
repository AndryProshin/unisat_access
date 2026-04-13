# scene.py

import requests
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from . import config


class Scene:
    def __init__(self, data: dict, params: dict, base_url: str, timeout: int):
        self._data = data
        self._params = params
        self._base_url = base_url
        self._timeout = timeout
        self._fragments = None
    
    @property
    def dt(self) -> str:
        return self._data["common"]["dt"]
    
    @property
    def satellite(self) -> str:
        return self._data["common"]["satellite"]
    
    @property
    def device(self) -> str:
        return self._data["common"]["device"]
    
    @property
    def station(self) -> str:
        return self._data["common"]["station"]
    
    @property
    def products(self) -> dict:
        return self._data["products"]
    
    def _load_fragments(self):
        """Загружает фрагменты с сервера"""
        params = {
            "request": "GetSeanceProducts",
            "dt": self.dt,
            "satellite": self.satellite,
            "device": self.device,
            "station": self.station,
            "products": ','.join(self.products.keys()),
            "bbox": ','.join(str(x) for x in self._params["bbox"])
        }
        
        query_string = urlencode(params)
        url = f"{self._base_url}?{query_string}"
        
        response = requests.get(url, timeout=self._timeout)
        response.raise_for_status()
        self._fragments = response.json()
    
    def get_fragments(self):
        """Возвращает список фрагментов с путями к файлам"""
        if self._fragments is None:
            self._load_fragments()
        
        result = []
        for frag in self._fragments:
            fragment = {}
            for product_type, files in frag["products_info"].items():
                fragment[product_type] = files["product_file"]
            result.append(fragment)
        
        return result

    def get_vsicurl(self, fragment_index: int, product_type: str) -> str:
        """Возвращает vsicurl для конкретного продукта"""
        fragments = self.get_fragments()
        product_file = fragments[fragment_index][product_type]
        return f"/vsicurl/{config.NGINX_BASE_URL}/{product_file}"

    def get_http_url(self, fragment_index: int, product_type: str) -> str:
        """Возвращает http url для конкретного продукта"""
        fragments = self.get_fragments()
        product_file = fragments[fragment_index][product_type]
        return f"{config.NGINX_BASE_URL}/{product_file}"

    def to_http(self, fragment: dict) -> dict:
        """Преобразует фрагмент с путями в фрагмент с http url"""
        result = {}
        for product, path in fragment.items():
            result[product] = f"{config.NGINX_BASE_URL}/{path}"
        return result

    def to_vsicurl(self, fragment: dict) -> dict:
        """Преобразует фрагмент с путями в фрагмент с vsicurl"""
        result = {}
        for product, path in fragment.items():
            result[product] = f"/vsicurl/{config.NGINX_BASE_URL}/{path}"
        return result

    def to_dict(self) -> dict:
        return {
            "dt": self.dt,
            "satellite": self.satellite,
            "device": self.device,
            "station": self.station,
            "products": self.products,
            "fragments": self._fragments
        }


    def download(
        self,
        download_subdir: str,
        flat: bool = False
    ) -> Dict[str, Any]:
        """
        Скачивает все файлы сцены.
        
        Args:
            download_subdir: имя поддиректории внутри data/download/ (обязательный параметр)
            flat: если True, все файлы в одну папку с именами YYYYMMDD_hhmmss_<frag_num>_<product>.<ext>
                если False, сохраняет оригинальную структуру product/04040/...
        
        Returns:
            словарь с информацией о скачивании:
            {
                "download_dir": путь к директории,
                "files": список скачанных файлов,
                "params_file": путь к _params.json,
                "metadata_file": путь к _metadata.txt
            }
        """
        fragments = self.get_fragments()
        if not fragments:
            print("Нет фрагментов для скачивания")
            return None
        
        # Определяем директорию скачивания
        download_path = config.DOWNLOAD_DIR / download_subdir
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Формируем базовое имя для файлов
        dt_str = self.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        
        # Сохраняем параметры запроса в JSON
        params_file = download_path / "_params.json"
        if not params_file.exists():
            import json
            download_params = {
                "query": self._params.copy(),
                "download": {
                    "operation": "download",
                    "flat": flat,
                    "timestamp": datetime.now().isoformat(),
                    "package_version": "1.0.0"
                }
            }
            with open(params_file, 'w', encoding='utf-8') as f:
                json.dump(download_params, f, indent=2, ensure_ascii=False)
        
        # Лог-файл для метаданных
        metadata_file = download_path / "_metadata.txt"
        file_exists = metadata_file.exists()
        
        downloaded_files = []
        
        with open(metadata_file, 'a', encoding='utf-8') as log:
            if not file_exists:
                log.write("dt|satellite|device|station|fragment|product|original_path|local_path\n")
            
            for i, frag in enumerate(fragments):
                http_frag = self.to_http(frag)
                
                for product_type, url in http_frag.items():
                    original_path = frag.get(product_type, "")
                    if not original_path:
                        continue
                    
                    if flat:
                        # Извлекаем оригинальное расширение из пути
                        ext = Path(original_path).suffix
                        if not ext:
                            ext = ".tif"
                        filename = f"{dt_str}_frag{i}_{product_type}{ext}"
                        local_path = download_path / filename
                    else:
                        # Оригинальная структура
                        local_path = download_path / original_path
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    print(f"Скачивание: {product_type} -> {local_path}")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    log.write(f"{self.dt}|{self.satellite}|{self.device}|{self.station}|{i}|{product_type}|{original_path}|{local_path}\n")
                    downloaded_files.append(str(local_path))
        
        print(f"\nФайлы сохранены в: {download_path}")
        print(f"Лог: {metadata_file}")
        print(f"Параметры: {params_file}")
        
        return {
            "download_dir": str(download_path),
            "files": downloaded_files,
            "params_file": str(params_file),
            "metadata_file": str(metadata_file)
        }