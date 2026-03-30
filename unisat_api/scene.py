# scene.py

import requests
from urllib.parse import urlencode
from pathlib import Path

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
        """Возвращает список фрагментов с путями к tif файлам"""
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
    

    def download(self, base_dir: str = "download", flat: bool = False) -> str:
        """
        Скачивает все файлы сцены.
        
        Args:
            base_dir: базовая директория для сохранения
            flat: если True, все файлы в одну папку с именами YYYYMMDD_hhmmss_<frag_num>_<product>.tif
                если False, сохраняет оригинальную структуру product/04040/...
        """
        fragments = self.get_fragments()
        if not fragments:
            print("Нет фрагментов для скачивания")
            return None
        
        base_path = Path(base_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        
        log_file = base_path / "metadata.txt"
        
        # Формируем базовое имя для файлов
        dt_str = self.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]  # YYYYMMDD_hhmmss
        
        with open(log_file, 'a', encoding='utf-8') as log:
            for i, frag in enumerate(fragments):
                http_frag = self.to_http(frag)
                
                for product_type, url in http_frag.items():
                    original_path = frag.get(product_type, "")
                    if not original_path:
                        continue
                    
                    if flat:
                        # Имя файла: YYYYMMDD_hhmmss_fragN_product.tif
                        filename = f"{dt_str}_frag{i}_{product_type}.tif"
                        local_path = base_path / filename
                    else:
                        # Оригинальная структура
                        local_path = base_path / original_path
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    print(f"Скачивание: {product_type} -> {local_path}")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    log.write(f"{self.dt}|{self.satellite}|{self.device}|{self.station}|{i}|{product_type}|{original_path}|{local_path}\n")
        
        print(f"\nФайлы сохранены в: {base_path}")
        print(f"Лог: {log_file}")
        return str(base_path)