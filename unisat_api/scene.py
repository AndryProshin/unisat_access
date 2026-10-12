# scene.py

import requests
import warnings
import json
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from . import config
from .exceptions import NetworkError


class Scene:
    def __init__(
        self,
        data: dict,
        params: dict,
        base_url: str,
        timeout: int,
        products_info: Optional[dict] = None
    ):
        self._data = data
        self._params = params
        self._base_url = base_url
        self._timeout = timeout
        self._fragments = None
        self._products_info = products_info

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
        """Return (physical_products, virtual_products)."""
        physical = []
        virtual = []
        for product_name in self.products.keys():
            if product_name.startswith(('_', 'v_')):
                virtual.append(product_name)
            else:
                physical.append(product_name)
        return physical, virtual

    def get_resolution(self, product: str) -> Optional[float]:
        """
        Return native resolution (meters) for a product, or None.

        Physical products map to spectral bands via products_info:
        the product entry contains 'band' (single) or 'bands' (list),
        or 'channels' with nested 'band'/'bands' fields. The resolution
        of the product is the minimum resolution among its bands.

        Virtual products (v_*, _*) have no fragments and no resolution.
        """
        if not self._products_info:
            return None
        if product.startswith(('_', 'v_')):
            return None

        products = self._products_info.get("products") or {}
        bands = self._products_info.get("bands") or {}
        info = products.get(product)
        if not info:
            return None

        band_names: List[str] = []

        if "band" in info:
            band_names.append(info["band"])
        if "bands" in info:
            band_names.extend(info["bands"])

        channels = info.get("channels") or []
        for ch in channels:
            if "band" in ch:
                band_names.append(ch["band"])
            if "bands" in ch:
                band_names.extend(ch["bands"])

        resolutions = []
        for band_name in band_names:
            band = bands.get(band_name)
            if not band:
                continue
            res = band.get("resolution")
            if isinstance(res, (int, float)):
                resolutions.append(res)

        if not resolutions:
            return None
        return float(min(resolutions))

    def _load_fragments(self):
        """Load fragments from the server."""
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

        try:
            response = requests.get(url, timeout=self._timeout)
            response.raise_for_status()
            self._fragments = response.json()
        except requests.exceptions.ConnectionError:
            raise NetworkError(f"Metadata server unavailable: {self._base_url}") from None
        except requests.exceptions.Timeout:
            raise NetworkError(f"Timeout while requesting {self._base_url}") from None
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Error while requesting fragments: {e}") from None

    def get_fragments(self):
        """Return fragments with file paths (physical products only)."""
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
        """Return vsicurl path for a product."""
        fragments = self.get_fragments()
        product_file = fragments[fragment_index][product_type]
        return f"/vsicurl/{config.NGINX_BASE_URL}/{product_file}"

    def get_http_url(self, fragment_index: int, product_type: str) -> str:
        """Return http url for a product."""
        fragments = self.get_fragments()
        product_file = fragments[fragment_index][product_type]
        return f"{config.NGINX_BASE_URL}/{product_file}"

    def to_http(self, fragment: dict) -> dict:
        """Convert fragment with paths to fragment with http urls."""
        result = {}
        for product, path in fragment.items():
            result[product] = f"{config.NGINX_BASE_URL}/{path}"
        return result

    def to_vsicurl(self, fragment: dict) -> dict:
        """Convert fragment with paths to fragment with vsicurl."""
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
        """Save query and operation parameters to _params.json."""
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
        Download all scene files.

        Args:
            download_subdir: subdirectory name inside data/_download/
            flat: if True, all files go into one folder
                  if False, keep original structure product/04040/...

        Returns:
            dict with download info
        """
        fragments = self.get_fragments()
        if not fragments:
            print("No fragments to download")
            return None

        download_path = config.DOWNLOAD_DIR / download_subdir
        download_path.mkdir(parents=True, exist_ok=True)

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

                    print(f"Downloading: {product_type} -> {local_path}")

                    try:
                        response = requests.get(url, stream=True, timeout=self._timeout)
                        response.raise_for_status()
                    except requests.exceptions.ConnectionError:
                        raise NetworkError(f"NGINX server unavailable: {config.NGINX_BASE_URL}") from None
                    except requests.exceptions.Timeout:
                        raise NetworkError(f"Timeout while downloading {product_type}") from None
                    except requests.exceptions.RequestException as e:
                        raise NetworkError(f"Error downloading {product_type}: {e}") from None

                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    log.write(f"{self.dt}|{self.satellite}|{self.device}|{self.station}|{i}|{product_type}|{original_path}|{rel_path}\n")
                    downloaded_files.append(str(local_path))

        print(f"\nFiles saved to: {download_path}")
        print(f"Log: {metadata_file}")

        return {
            "download_dir": str(download_path),
            "files": downloaded_files,
            "params_file": str(download_path / "_params.json"),
            "metadata_file": str(metadata_file)
        }

    # ============================================
    # PNG PRODUCTS
    # ============================================

    def _get_product_uid(self, product: str) -> str:
        """Return product uid for PNG request."""
        if product not in self.products:
            raise ValueError(f"Product '{product}' not found in scene")
        return self.products[product]["id"]

    def _build_product_url(self, product: str, width: int, height: int) -> str:
        """Build URL for PNG product request."""
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
        Fetch a raster product (PNG) and save to file.

        Args:
            product: product name
            products_subdir: subdirectory inside data/_product/
            max_size: max size along the long side (pixels)
            output_path: explicit path (None -> auto name)
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

        save_dir = Path(output_path).parent
        self._save_params_json(save_dir, "get_product", product=product, max_size=max_size)

        print(f"Fetching product: {product} -> {output_path}")

        try:
            response = requests.get(url, stream=True, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise NetworkError(f"Product server unavailable: {config.PRODUCT_BASE_URL}") from None
        except requests.exceptions.Timeout:
            raise NetworkError(f"Timeout while fetching product {product}") from None
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Error fetching product {product}: {e}") from None

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
        Fetch several products and save to the given directory.

        Args:
            products: list of product names
            products_subdir: subdirectory inside data/_product/
            max_size: max size along the long side (pixels)
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
        Fetch all scene products and save to the given directory.

        Args:
            products_subdir: subdirectory inside data/_product/
            max_size: max size along the long side (pixels)
        """
        return self.get_products(products=list(self.products.keys()), products_subdir=products_subdir, max_size=max_size)