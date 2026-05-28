# parameters.py

import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urlencode

from . import config
from .exceptions import ParameterError, NetworkError, MetadataError
from .utils.validators import is_bbox, is_date_or_datetime


class Parameters:
    """
    Класс для работы с параметрами запросов.
    """
    
    _schema: Optional[Dict[str, Any]] = None
    _preset_valid: Optional[Dict[str, Any]] = None
    
    def __init__(
        self,
        collection: Optional[str] = None,
        user_preset: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            collection: имя коллекции (из presets/collections/)
            user_preset: имя пользовательского пресета (из presets/user_presets/)
            params: словарь параметров (переопределяют значения из пресета)
        """
        self._params: Dict[str, Any] = {}
        
        self._load_schema()
        
        # Загружаем пресет (приоритет: collection > user_preset)
        if collection:
            self._load_preset(collection, is_collection=True)
        elif user_preset:
            self._load_preset(user_preset, is_collection=False)
        
        if params:
            self._params.update(params)
        
        self._validate()

    def _load_schema(self) -> None:
        if self._schema is not None:
            return
        
        url = f"{config.METADATA_BASE_URL}?request=GetMetadataPars"
        
        try:
            response = requests.get(url, timeout=config.METADATA_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            self._schema = {
                "required": data.get("required", []),
                "valid": data.get("valid", {}),
                "desc": data.get("desc", {})
            }
        except requests.exceptions.ConnectionError:
            raise NetworkError(f"Сервер метаданных недоступен: {config.METADATA_BASE_URL}") from None
        except requests.exceptions.Timeout:
            raise NetworkError(f"Превышен таймаут при запросе к {config.METADATA_BASE_URL}") from None
        except requests.exceptions.RequestException as e:
            raise ParameterError(f"Ошибка получения схемы параметров: {e}") from None
        except Exception as e:
            raise ParameterError(f"Неожиданная ошибка: {e}") from None
    
    def _load_preset(self, preset_name: str, is_collection: bool) -> None:
        """Загружает пресет из соответствующей директории"""
        if is_collection:
            preset_path = config.COLLECTIONS_DIR / f"{preset_name}.json"
        else:
            preset_path = config.USER_PRESETS_DIR / f"{preset_name}.json"
        
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset not found: {preset_path}")
        
        with open(preset_path, 'r', encoding='utf-8') as f:
            preset_data = json.load(f)
            
            # Сохраняем _valid отдельно, если есть
            if "_valid" in preset_data:
                self._preset_valid = preset_data.pop("_valid")
            
            self._params = {k: v for k, v in preset_data.items() if v is not None}

    def _validate(self) -> None:
        """Validate parameters against schema"""
        if not self._schema:
            return
        
        errors = []
        valid = self._schema.get("valid", {})
        required = self._schema.get("required", [])
        desc = self._schema.get("desc", {})
        
        # Check required parameters
        for param_name in required:
            if param_name not in self._params:
                errors.append(f"Required parameter '{param_name}' is missing")
        
        # Validate each parameter
        for param_name, param_value in self._params.items():
            if param_name not in valid:
                errors.append(
                    f"Parameter '{param_name}' is not allowed. "
                )
                continue
            
            param_type = valid[param_name]
            param_desc = desc.get(param_name, param_name)
            
            # Type validation using utility functions
            if param_type == "LIST" and not isinstance(param_value, list):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a list, "
                    f"got {type(param_value).__name__}"
                )
            elif param_type == "NUMBER" and not isinstance(param_value, (int, float)):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a number, "
                    f"got {type(param_value).__name__}"
                )
            elif param_type == "STRING" and not isinstance(param_value, str):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a string, "
                    f"got {type(param_value).__name__}"
                )
            elif param_type == "BOOL" and not isinstance(param_value, bool):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a boolean, "
                    f"got {type(param_value).__name__}"
                )
            elif param_type == "BBOX" and not is_bbox(param_value):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a BBOX: "
                    f"(minx, miny, maxx, maxy)"
                )
            elif param_type == "DATE_OR_DATETIME" and not is_date_or_datetime(param_value):
                errors.append(
                    f"Parameter '{param_name}' ({param_desc}) must be a date or datetime, "
                    f"got {param_value}"
                )
            
            # Проверка допустимых значений из пресета (_valid)
            if self._preset_valid and param_name in self._preset_valid:
                allowed = self._preset_valid[param_name]
                if isinstance(allowed, list):
                    if isinstance(param_value, list):
                        for item in param_value:
                            if item not in allowed:
                                errors.append(
                                    f"Parameter '{param_name}' value '{item}' is not allowed. "
                                    f"Allowed: {allowed}"
                                )
                    else:
                        if param_value not in allowed:
                            errors.append(
                                f"Parameter '{param_name}' value '{param_value}' is not allowed. "
                                f"Allowed: {allowed}"
                            )
        
        if errors:
            print(f"Parameter error:\n{chr(10).join(errors)}")
            print(self.get_parameters_description())
            sys.exit(1)
    
    def save(self, name: str) -> None:
        """Save current parameters as a new user preset"""
        filepath = config.USER_PRESETS_DIR / f"{name}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Если есть _valid, сохраняем его
        data_to_save = self._params.copy()
        if self._preset_valid:
            data_to_save["_valid"] = self._preset_valid
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)
    
    def to_dict(self) -> Dict[str, Any]:
        return self._params.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._params.get(key, default)
    
    def set(self, key: str, value: Any) -> 'Parameters':
        self._params[key] = value
        self._validate()
        return self
    
    def get_schema(self) -> Dict[str, Any]:
        return self._schema.copy() if self._schema else {}
    
    def get_required_params(self) -> List[str]:
        return self._schema.get("required", []) if self._schema else []
    
    def get_param_description(self, param_name: str) -> str:
        if self._schema:
            return self._schema.get("desc", {}).get(param_name, param_name)
        return param_name
    
    def get_parameters_description(self) -> str:
        """
        Returns formatted description of all parameters.
        Required parameters are marked with asterisk (*).
        """
        if not self._schema:
            return "Schema not loaded"
        
        valid = self._schema.get("valid", {})
        desc = self._schema.get("desc", {})
        required = set(self._schema.get("required", []))
        
        if not valid:
            return "No parameters defined"
        
        lines = []
        max_name_len = max(len(name) for name in valid.keys())
        
        for param_name, param_type in sorted(valid.items()):
            param_desc = desc.get(param_name, "")
            required_mark = "*" if param_name in required else " "
            type_str = param_type.replace("_", " ").lower()
            
            lines.append(
                f"  {required_mark} {param_name:<{max_name_len}} : {type_str:<18} {param_desc}"
            )
        
        return "\n".join(lines)
    
    def keys(self) -> List[str]:
        return list(self._params.keys())
    
    def __getitem__(self, key: str) -> Any:
        return self._params[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        self._params[key] = value
        self._validate()
    
    def __contains__(self, key: str) -> bool:
        return key in self._params

    def __repr__(self) -> str:
        """Краткое представление объекта"""
        return f"Parameters({len(self._params)} params, presets_dir={config.PRESETS_DIR})"

    def __str__(self) -> str:
        """Человекочитаемое представление параметров"""
        if not self._params:
            return "Parameters (empty)"
        
        lines = ["Parameters:"]
        max_key_len = max(len(key) for key in self._params.keys())
        
        for key, value in sorted(self._params.items()):
            # Форматируем значение для красивого вывода
            if isinstance(value, list):
                if len(value) > 5:
                    value_str = f"[{', '.join(str(v) for v in value[:5])}, ...] ({len(value)} items)"
                else:
                    value_str = str(value)
            elif isinstance(value, dict):
                value_str = "{...}" if len(value) > 3 else str(value)
            elif isinstance(value, str):
                if len(value) > 60:
                    value_str = f"'{value[:57]}...'"
                else:
                    value_str = f"'{value}'"
            else:
                value_str = str(value)
            
            lines.append(f"  {key:<{max_key_len}} : {value_str}")
        
        return "\n".join(lines)
    
    @classmethod
    def list_presets(cls) -> Dict[str, List[str]]:
        """Возвращает словарь с разделением по типам пресетов"""
        result = {
            "collections": [],
            "user_presets": []
        }
        
        if config.COLLECTIONS_DIR.exists():
            result["collections"] = sorted([f.stem for f in config.COLLECTIONS_DIR.glob("*.json")])
        
        if config.USER_PRESETS_DIR.exists():
            result["user_presets"] = sorted([f.stem for f in config.USER_PRESETS_DIR.glob("*.json")])
        
        return result

    # ============================================
    # СПРАВОЧНАЯ ИНФОРМАЦИЯ О ПРОДУКТАХ (GetDeviceProductsInfo)
    # ============================================

    def get_products_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить справочную информацию о продуктах и каналах для всех приборов,
        указанных в параметрах (ключ 'devices').
        
        Returns:
            Словарь вида {device_name: {'bands': ..., 'products': ..., 'vproducts': ...}}
            Всегда возвращает словарь, даже если прибор один.
        
        Example:
            >>> params = Parameters(collection="sentinel2_boa")
            >>> info = params.get_products_info()
            >>> for device, data in info.items():
            ...     print(f"{device}: {len(data['bands'])} bands")
        """
        devices = self._get_devices_from_params()
        
        result = {}
        for device in devices:
            result[device] = self._fetch_products_info(device)
        return result
    
    def print_products_info(self):
        """
        Печатает справочную информацию о продуктах и каналах в читаемом виде.
        Выводит данные для всех приборов, указанных в параметрах.
        """
        data = self.get_products_info()
        
        for device, device_data in data.items():
            print(f"\n{'=' * 80}")
            print(f"DEVICE: {device}")
            print(f"{'=' * 80}")
            self._print_products_info_recursive(device_data)
    
    def _print_products_info_recursive(self, data: Any, indent: int = 0):
        """
        Рекурсивно печатает структуру данных в читаемом виде.
        Простой иерархический вывод без лишних разделителей.
        """
        prefix = "  " * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    print(f"{prefix}{key}:")
                    self._print_products_info_recursive(value, indent + 1)
                else:
                    print(f"{prefix}{key}: {value}")
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    print(f"{prefix}[{i}]:")
                    self._print_products_info_recursive(item, indent + 1)
                else:
                    print(f"{prefix}[{i}]: {item}")
        
        else:
            print(f"{prefix}{data}")
    
    def _get_devices_from_params(self) -> List[str]:
        """Извлекает список устройств из параметров (ключ 'devices')"""
        devices_param = self._params.get("devices")
        if not devices_param:
            raise ParameterError(
                "Cannot get products info: 'devices' parameter is not set. "
                "Please ensure your preset/collection includes 'devices'."
            )
        if isinstance(devices_param, list):
            return devices_param
        return [devices_param]
    
    def _fetch_products_info(self, device: str) -> Dict[str, Any]:
        """Выполняет запрос GetDeviceProductsInfo к серверу метаданных."""
        base_url = config.METADATA_BASE_URL.rstrip('/')
        
        params = {
            "request": "GetDeviceProductsInfo",
            "device": device
        }
        
        # Опционально: фильтрация по продуктам
        if "products" in self._params:
            products_param = self._params["products"]
            if isinstance(products_param, list):
                params["products"] = ','.join(str(p) for p in products_param)
            else:
                params["products"] = str(products_param)
        
        query_string = urlencode(params)
        full_url = f"{base_url}?{query_string}"
        
        try:
            response = requests.get(full_url, timeout=config.METADATA_TIMEOUT)
            response.raise_for_status()
            
            # Сервер возвращает CP1251, а requests думает, что это UTF-8
            # Пробуем декодировать как CP1251
            try:
                # Декодируем тело как CP1251
                decoded_content = response.content.decode('cp1251')
                return json.loads(decoded_content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Если не получилось, пробуем как UTF-8
                return response.json()
            
        except requests.exceptions.ConnectionError:
            raise NetworkError(f"Сервер метаданных недоступен: {base_url}") from None
        except requests.exceptions.Timeout:
            raise NetworkError(f"Превышен таймаут при запросе к {base_url}") from None
        except requests.exceptions.RequestException as e:
            raise MetadataError(f"Ошибка получения информации об устройстве {device}: {e}") from None
        except Exception as e:
            raise MetadataError(f"Неожиданная ошибка: {e}") from None