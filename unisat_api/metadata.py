# metadata.py

import requests

from . import config
from .exceptions import ParameterError, MetadataError
from .parameters import Parameters
from .scene import Scene


from urllib.parse import urlencode

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
        except Exception as e:
            raise MetadataError(f"Failed to load metadata: {e}")
    
    def __len__(self) -> int:
        return len(self._raw_json["DATA"])
    
    def __iter__(self):
        for data in self._raw_json["DATA"]:
            yield Scene(data, self.params.to_dict(), config.METADATA_BASE_URL, config.METADATA_TIMEOUT)
    
    def __getitem__(self, idx: int):
        data = self._raw_json["DATA"][idx]
        return Scene(data, self.params.to_dict(), config.METADATA_BASE_URL, config.METADATA_TIMEOUT)
    
    @property
    def raw_json(self):
        return self._raw_json