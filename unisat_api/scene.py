# scene.py

import requests
import warnings
import json
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

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
    
    def _classify_products(self) -> Tuple[List[str], List[str]]:
        """Возвращает (physical_products, virtual_products)"""
        physical = []
        virtual = []
        for product_name in self.products.keys():
            if product_name.startswith(('_', 'v_')):
                virtual.append(product_name)
            else:
                physical.append(product_name)
        return physical, virtual
    
    def _load_fragments(self):
        """Загружает фрагменты с сервера"""
        physical, _ = self._classify_products()
        if not physical:
            raise ValueError("No physical products found in scene")
        
        params = {
            "request": "GetSeanceProducts",
            "dt": self.dt,
            "satellite": self.satellite,
            "device": self.device,
            "station": self.station,
            "products": ','.join(physical),
            "bbox": ','.join(str(x) for x in self._params["bbox"])
        }
        
        query_string = urlencode(params)
        url = f"{self._base_url}?{query_string}"
        
        response = requests.get(url, timeout=self._timeout)
        response.raise_for_status()
        self._fragments = response.json()
    
    def get_fragments(self):
        """Возвращает список фрагментов с путями к файлам (только для физических продуктов)"""
        physical, virtual = self._classify_products()
        
        if virtual:
            warnings.warn(f"Virtual products skipped: {', '.join(virtual)}", UserWarning)
        
        if not physical:
            raise ValueError("No physical products found in scene")
        
        if self._fragments is None:
            self._load_fragments()
        
        result = []
        for frag in self._fragments:
            fragment = {}
            for product_type, files in frag["products_info"].items():
                if product_type in physical:
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

    def _save_params_json(self, target_dir: Path, operation: str, **extra_params) -> None:
        """Сохраняет параметры запроса и операции в _params.json"""
        params_file = target_dir / "_params.json"
        if params_file.exists():
            return
        
        params_data = {
            "query": self._params.copy(),
            "operation": {
                "name": operation,
                "timestamp": datetime.now().isoformat(),
                "package_version": "1.0.0",
                **extra_params
            }
        }
        
        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump(params_data, f, indent=2, ensure_ascii=False)

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
            словарь с информацией о скачивании
        """
        fragments = self.get_fragments()
        if not fragments:
            print("Нет фрагментов для скачивания")
            return None
        
        download_path = config.DOWNLOAD_DIR / download_subdir
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем _params.json
        self._save_params_json(download_path, "download", flat=flat)
        
        dt_str = self.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        
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
                        ext = Path(original_path).suffix
                        if not ext:
                            ext = ".tif"
                        filename = f"{dt_str}_frag{i}_{product_type}{ext}"
                        local_path = download_path / filename
                        rel_path = filename
                    else:
                        local_path = download_path / original_path
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        rel_path = original_path
                    
                    print(f"Скачивание: {product_type} -> {local_path}")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    log.write(f"{self.dt}|{self.satellite}|{self.device}|{self.station}|{i}|{product_type}|{original_path}|{rel_path}\n")
                    downloaded_files.append(str(local_path))
        
        print(f"\nФайлы сохранены в: {download_path}")
        print(f"Лог: {metadata_file}")
        
        return {
            "download_dir": str(download_path),
            "files": downloaded_files,
            "params_file": str(download_path / "_params.json"),
            "metadata_file": str(metadata_file)
        }

    # ============================================
    # МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ РАСТРОВЫХ ИЗОБРАЖЕНИЙ (PNG)
    # ============================================

    def _get_product_uid(self, product: str) -> str:
        """Возвращает uid продукта для запроса PNG"""
        if product not in self.products:
            raise ValueError(f"Product '{product}' not found in scene")
        return self.products[product]["id"]

    def _build_product_url(self, product: str, width: int, height: int) -> str:
        """Формирует URL для запроса PNG продукта"""
        bbox = self._params.get("bbox")
        if not bbox:
            raise ValueError("bbox not found in scene parameters")
        
        bbox_str = ",".join(str(x) for x in bbox)
        uid = self._get_product_uid(product)
        
        params = {
            "layers": "unisat",
            "db_pkg_mode": "hrsat",
            "FORMAT": "png",
            "WIDTH": width,
            "HEIGHT": height,
            "BBOX": bbox_str,
            "EXCEPTIONS": "xml",
            "SERVICE": "WMS",
            "REQUEST": "GetMap",
            "transparent": 1,
            "unisat_uids": uid,
            "server_id": "nffc_hrsatdb",
            "ukey": config.UKEY
        }
        
        query_string = urlencode(params)
        return f"{config.PRODUCT_BASE_URL}/get_map.pl?{query_string}"

    def get_product(
        self,
        *,
        product: str,
        products_subdir: str,
        max_size: Optional[int] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Получает растровый продукт (PNG) и сохраняет в файл.
        
        Args:
            product: имя продукта
            products_subdir: поддиректория внутри data/products/ (обязательный)
            max_size: максимальный размер по длинной стороне (пикселей)
            output_path: путь для сохранения (None → авто-имя)
        """
        bbox = self._params.get("bbox")
        if not bbox:
            raise ValueError("bbox not found in scene parameters")
        
        width_m = bbox[2] - bbox[0]
        height_m = bbox[3] - bbox[1]
        
        if max_size is not None:
            if width_m >= height_m:
                width = max_size
                height = int(max_size * height_m / width_m)
            else:
                height = max_size
                width = int(max_size * width_m / height_m)
            url = self._build_product_url(product, width, height)
        else:
            bbox_str = ",".join(str(x) for x in bbox)
            uid = self._get_product_uid(product)
            params = {
                "layers": "unisat",
                "db_pkg_mode": "hrsat",
                "FORMAT": "png",
                "BBOX": bbox_str,
                "EXCEPTIONS": "xml",
                "SERVICE": "WMS",
                "REQUEST": "GetMap",
                "transparent": 1,
                "unisat_uids": uid,
                "server_id": "nffc_hrsatdb",
                "ukey": config.UKEY
            }
            query_string = urlencode(params)
            url = f"{config.PRODUCT_BASE_URL}/get_map.pl?{query_string}"
        
        if output_path is None:
            save_path = config.PRODUCTS_DIR / products_subdir
            save_path.mkdir(parents=True, exist_ok=True)
            dt_str = self.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
            filename = f"{dt_str}_{product}.png"
            output_path = str(save_path / filename)
            rel_path = filename
        else:
            output_path = str(Path(output_path))
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            rel_path = Path(output_path).name
        
        # Сохраняем _params.json
        save_dir = Path(output_path).parent
        self._save_params_json(save_dir, "get_product", product=product, max_size=max_size)
        
        print(f"Получение продукта: {product} -> {output_path}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        metadata_file = save_dir / "_metadata.txt"
        file_exists = metadata_file.exists()
        with open(metadata_file, 'a', encoding='utf-8') as log:
            if not file_exists:
                log.write("dt|satellite|device|station|product|file\n")
            log.write(f"{self.dt}|{self.satellite}|{self.device}|{self.station}|{product}|{rel_path}\n")
        
        return output_path

    def get_products(
        self,
        *,
        products: List[str],
        products_subdir: str,
        max_size: Optional[int] = None
    ) -> List[str]:
        """
        Получает несколько продуктов и сохраняет в указанную директорию.
        
        Args:
            products: список имён продуктов
            products_subdir: поддиректория внутри data/products/ (обязательный)
            max_size: максимальный размер по длинной стороне (пикселей)
        """
        downloaded = []
        for product in products:
            if product not in self.products:
                warnings.warn(f"Product '{product}' not found in scene, skipping", UserWarning)
                continue
            path = self.get_product(product=product, products_subdir=products_subdir, max_size=max_size)
            downloaded.append(path)
        return downloaded

    def get_all_products(
        self,
        *,
        products_subdir: str,
        max_size: Optional[int] = None
    ) -> List[str]:
        """
        Получает все продукты сцены и сохраняет в указанную директорию.
        
        Args:
            products_subdir: поддиректория внутри data/products/ (обязательный)
            max_size: максимальный размер по длинной стороне (пикселей)
        """
        return self.get_products(products=list(self.products.keys()), products_subdir=products_subdir, max_size=max_size)