# metadata.py

import requests
from urllib.parse import urlencode

from . import config
from .exceptions import MetadataError, NetworkError
from .parameters import Parameters
from .scene import Scene


class Metadata:
    def __init__(self, params: Parameters):
        self.params = params
        self._raw_json = None
        self._load()
    
    def _load(self):
        base_url = config.METADATA_BASE_URL.rstrip('/')
        
        params_dict = self.params.to_dict()
        
        # Преобразуем списки в строки через запятую
        for key, value in params_dict.items():
            if isinstance(value, list):
                params_dict[key] = ','.join(str(v) for v in value)
        
        query_string = urlencode(params_dict)
        full_url = f"{base_url}?request=GetMetadata&{query_string}"
        
        try:
            response = requests.get(full_url, timeout=config.METADATA_TIMEOUT)
            response.raise_for_status()
            self._raw_json = response.json()
        except requests.exceptions.ConnectionError:
            raise NetworkError(f"Сервер метаданных недоступен: {base_url}") from None
        except requests.exceptions.Timeout:
            raise NetworkError(f"Превышен таймаут при запросе к {base_url}") from None
        except requests.exceptions.RequestException as e:
            raise MetadataError(f"Ошибка загрузки метаданных: {e}") from None
        except Exception as e:
            raise MetadataError(f"Неожиданная ошибка: {e}") from None

    def _make_scene(self, data: dict) -> Scene:
        """
        Build a Scene, wiring in the products info slice for its device.

        Products info is cached inside Parameters (one entry per device),
        so this does not perform any network calls by itself.
        """
        device = data.get("common", {}).get("device")
        device_info = self.params.get_products_info().get(device)
        return Scene(
            data,
            self.params.to_dict(),
            config.METADATA_BASE_URL,
            config.METADATA_TIMEOUT,
            products_info=device_info,
        )
    
    def __len__(self) -> int:
        return len(self._raw_json["DATA"])
    
    def __iter__(self):
        for data in self._raw_json["DATA"]:
            yield self._make_scene(data)
    
    def __getitem__(self, idx: int):
        data = self._raw_json["DATA"][idx]
        return self._make_scene(data)
    
    @property
    def raw_json(self):
        return self._raw_json