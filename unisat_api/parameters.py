# parameters.py

import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from . import config
from .exceptions import ParameterError
from .utils.validators import is_bbox, is_date_or_datetime

class Parameters:
    """
    Класс для работы с параметрами запросов.
    """
    
    _schema: Optional[Dict[str, Any]] = None
    
    def __init__(self, preset: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        self._params: Dict[str, Any] = {}
        
        self._load_schema()
        
        if preset:
            self._load_preset(preset)
        
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
        except requests.RequestException as e:
            raise ParameterError(f"Failed to get parameter schema: {e}")
        except Exception as e:
            raise ParameterError(f"Error loading schema: {e}")
    
    def _load_preset(self, preset_name: str) -> None:
        preset_path = config.PRESETS_DIR / f"{preset_name}.json"
        
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset not found: {preset_path}")
        
        with open(preset_path, 'r', encoding='utf-8') as f:
            preset_data = json.load(f)
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
#                    f"Allowed parameters: {', '.join(sorted(valid.keys()))}"
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
        
        if errors:
            print(f"Parameter error:\n{chr(10).join(errors)}")
            print(self.get_parameters_description())
            sys.exit(1)

#            raise ParameterError("\n".join(errors))
    
    def save(self, name: str) -> None:
        """Save current parameters as a new preset"""
        filepath = config.PRESETS_DIR / f"{name}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._params, f, indent=2, ensure_ascii=False, default=str)
    
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
    def list_presets(cls) -> List[str]:
        """Возвращает список доступных имён пресетов"""
        presets_dir = config.PRESETS_DIR
        if not presets_dir.exists():
            return []
        return [f.stem for f in presets_dir.glob("*.json")]