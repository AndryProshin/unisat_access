"""
Спектральные индексы для спутниковых данных.

Универсальный инструмент для вычисления любых спектральных индексов.
Не содержит сенсор-специфичных предустановок.

Позволяет:
- Создавать пользовательские индексы через формулу
- Вычислять предустановленные индексы (сенсор-специфичные - в других модулях)
- Работать с масками облачности
- Сохранять результаты в GeoTIFF
- Опционально сохранять PNG-превью
"""

import json
import csv
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from unisat_api.scene import Scene
from unisat_api import config
from processing.gdal.utils import read_raster, write_geotiff, get_raster_statistics, array_to_png
from processing.gdal.scene import GDALScene


# ============================================
# КЛАСС: СПЕКТРАЛЬНЫЙ ИНДЕКС
# ============================================

class SpectralIndex:
    """
    Определение спектрального индекса.
    
    Параметры
    ---------
    name : str
        Название индекса (например, "NDVI")
    expression : str
        Формула вычисления с использованием имён из bands.
        Доступны: np, sqrt, log, log10, exp, abs, where, min, max
    bands : Dict[str, str]
        Маппинг имён в формуле -> имена продуктов в сцене
    scale : float, default=1
        Множитель результата (например, 10000 для int16)
    output_range : tuple, optional
        Клиппинг результата (min, max)
    no_data : float, default=np.nan
        Значение для NoData пикселей
    
    Пример
    -------
    >>> ndvi = SpectralIndex(
    ...     name="NDVI",
    ...     expression="(nir - red) / (nir + red)",
    ...     bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
    ...     scale=10000
    ... )
    """
    
    def __init__(
        self,
        name: str,
        expression: str,
        bands: Dict[str, str],
        scale: float = 1.0,
        output_range: Optional[tuple] = None,
        no_data: float = np.nan
    ):
        self.name = name
        self.expression = expression
        self.bands = bands
        self.scale = scale
        self.output_range = output_range
        self.no_data = no_data
    
    def evaluate(self, band_data: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Вычислить индекс по формуле.
        
        Параметры
        ---------
        band_data : Dict[str, np.ndarray]
            Словарь с массивами для каждого имени из bands
        
        Возвращает
        ----------
        np.ndarray
            Результат вычисления
        """
        namespace = band_data.copy()
        namespace.update({
            'np': np,
            'sqrt': np.sqrt,
            'log': np.log,
            'log10': np.log10,
            'exp': np.exp,
            'abs': np.abs,
            'where': np.where,
            'min': np.minimum,
            'max': np.maximum
        })
        
        result = eval(self.expression, {"__builtins__": {}}, namespace)
        result = result * self.scale
        
        if self.output_range:
            result = np.clip(result, self.output_range[0], self.output_range[1])
        
        return result.astype(np.float32)
    
    def __repr__(self) -> str:
        return f"SpectralIndex('{self.name}', expression='{self.expression}')"


# ============================================
# КЛАСС: КАЛЬКУЛЯТОР ИНДЕКСОВ
# ============================================

class IndexCalculator:
    """
    Калькулятор спектральных индексов для сцены.
    
    Параметры
    ---------
    scene : Scene
        Объект сцены
    offset : float, default=-1000
        Сдвиг для преобразования DN -> Reflectance (для Sentinel-2)
    scale : float, default=10000
        Масштаб для преобразования DN -> Reflectance (для Sentinel-2)
    """
    
    def __init__(
        self,
        scene: Scene,
        offset: float = -1000,
        scale: float = 10000
    ):
        self.scene = scene
        self.offset = offset
        self.scale = scale
    
    def _save_params_json(
        self,
        output_path: Path,
        index: SpectralIndex,
        mask_used: bool,
        bbox: Optional[List[float]],
        resample_to: Optional[str],
        resample_method: str
    ) -> None:
        """Сохраняет _params.json с параметрами запроса и операции"""
        params_file = output_path / "_params.json"
        
        params_data = {
            "query": self.scene._params.copy(),
            "operation": {
                "name": "compute_index",
                "timestamp": datetime.now().isoformat(),
                "package_version": "1.0.0",
                "index_name": index.name,
                "index_expression": index.expression,
                "mask_used": mask_used,
                "resample_to": resample_to,
                "resample_method": resample_method,
                "bbox_used": bbox or self.scene._params.get("bbox")
            }
        }
        
        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump(params_data, f, indent=2, ensure_ascii=False)
        print(f"   Сохранён _params.json в {output_path}")

    def _save_metadata(self, output_path: Path, filename: str) -> None:
        """Сохраняет _metadata.txt в финальной директории"""
        metadata_file = output_path / "_metadata.txt"
        
        with open(metadata_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter='|')
            writer.writerow(["dt", "satellite", "device", "station", "index", "file"])
            writer.writerow([
                self.scene.dt,
                self.scene.satellite,
                self.scene.device,
                self.scene.station,
                "index_result",
                filename
            ])
        print(f"   Сохранён _metadata.txt в {output_path}")

    def compute(
        self,
        index: SpectralIndex,
        result_subdir: str,
        mask: Optional[np.ndarray] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[str] = "highest",
        resample_method: str = "bilinear",
        save_png: bool = False
    ) -> Dict[str, Any]:
        """
        Вычислить индекс и сохранить как GeoTIFF.
        
        Параметры
        ---------
        index : SpectralIndex
            Индекс для вычисления
        result_subdir : str
            Поддиректория внутри data/processed/
        mask : np.ndarray, optional
            Маска (1 = хороший пиксель, 0 = исключить)
        bbox : List[float], optional
            BBOX в WGS84 [minx, miny, maxx, maxy]
        resample_to : str, optional
            "highest", "lowest" или None
        resample_method : str
            "nearest", "bilinear", "cubic"
        save_png : bool, default=False
            Если True, создать PNG-превью результата
        
        Возвращает
        ----------
        dict
            С ключами: index, file, expression, statistics, (png_file)
        """
        output_path = config.PROCESSED_DIR / result_subdir
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Загружаем каналы
        band_data, transform, proj = self._load_bands(
            index.bands, bbox, resample_to, resample_method
        )
        
        # 2. Вычисляем индекс
        result_array = index.evaluate(band_data)
        
        # 3. Применяем маску
        if mask is not None:
            if mask.shape != result_array.shape:
                from scipy.ndimage import zoom
                scale_y = result_array.shape[0] / mask.shape[0]
                scale_x = result_array.shape[1] / mask.shape[1]
                mask = zoom(mask, (scale_y, scale_x), order=0)
            
            result_array = result_array * mask
            result_array[mask == 0] = -9999
        
        # 4. Заменяем NaN на NoData
        result_array = np.nan_to_num(result_array, nan=-9999)
        
        # 5. Сохраняем GeoTIFF
        dt_str = self.scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        filename = f"{dt_str}_{index.name.lower()}.tif"
        out_file = output_path / filename
        
        options = [
            'COMPRESS=DEFLATE',
            'PREDICTOR=3',
            'TILED=YES',
            'BLOCKXSIZE=512',
            'BLOCKYSIZE=512'
        ]
        
        write_geotiff(
            str(out_file),
            result_array,
            transform,
            proj,
            no_data=-9999,
            options=options
        )
        
        # 6. Сохраняем PNG (опционально)
        png_file = None
        if save_png:
            png_path = out_file.with_suffix('.png')
            array_to_png(result_array, str(png_path), normalize=True, no_data=-9999)
            png_file = str(png_path)
        
        # 7. Сохраняем логи
        self._save_params_json(output_path, index, mask is not None, bbox, resample_to, resample_method)
        self._save_metadata(output_path, filename)
        
        # 8. Статистика
        stats = get_raster_statistics(result_array, no_data=-9999)
        
        result = {
            "index": index.name,
            "file": str(out_file),
            "expression": index.expression,
            "statistics": stats
        }
        if png_file:
            result["png_file"] = png_file
        
        return result
    
    def _load_bands(
        self,
        bands: Dict[str, str],
        bbox: Optional[List[float]],
        resample_to: Optional[str],
        resample_method: str
    ) -> tuple:
        """
        Загружает каналы и преобразует DN -> Reflectance.
        
        Возвращает
        ----------
        tuple
            (band_data, transform, proj)
        """
        gdal_scene = GDALScene(self.scene)
        band_data = {}
        transform = None
        proj = None
        
        for alias, product in bands.items():
            temp_dir = f"_temp_{alias}"
            result = gdal_scene.save_products(
                result_subdir=temp_dir,
                products=[product],
                bbox=bbox,
                resample_to=resample_to,
                resample_method=resample_method
            )
            
            file_path = result["files"][product]
            info = read_raster(file_path)
            arr = info['array']
            
            if transform is None:
                transform = info['transform']
                proj = info['proj']
            
            arr = (arr + self.offset) / self.scale
            band_data[alias] = arr
        
        return band_data, transform, proj


# ============================================
# УДОБНАЯ ФУНКЦИЯ ДЛЯ БЫСТРОГО ВЫЗОВА
# ============================================

def compute_index(
    scene: Scene,
    index: SpectralIndex,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    resample_to: Optional[str] = "highest",
    resample_method: str = "bilinear",
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление индекса (однострочник).
    
    Параметры
    ---------
    scene : Scene
        Объект сцены
    index : SpectralIndex
        Индекс для вычисления
    result_subdir : str
        Поддиректория внутри data/processed/
    mask : np.ndarray, optional
        Маска облачности
    bbox : List[float], optional
        BBOX в WGS84 [minx, miny, maxx, maxy]
    offset : float
        Сдвиг для DN→Reflectance (по умолчанию -1000)
    scale : float
        Масштаб для DN→Reflectance (по умолчанию 10000)
    resample_to : str, optional
        "highest", "lowest" или None
    resample_method : str
        "nearest", "bilinear", "cubic"
    save_png : bool, default=False
        Если True, создать PNG-превью результата
    """
    calc = IndexCalculator(scene, offset=offset, scale=scale)
    return calc.compute(
        index,
        result_subdir,
        mask=mask,
        bbox=bbox,
        resample_to=resample_to,
        resample_method=resample_method,
        save_png=save_png
    )