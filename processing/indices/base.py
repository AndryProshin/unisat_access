"""
Спектральные индексы для спутниковых данных.

Универсальный инструмент для вычисления любых спектральных индексов.
Не содержит сенсор-специфичных предустановок.

Позволяет:
- Создавать пользовательские индексы через формулу
- Вычислять предустановленные индексы (сенсор-специфичные - в других модулях)
- Работать с масками облачности
- Сохранять результаты в GeoTIFF
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


from unisat_api.scene import Scene
from unisat_api import config
from processing.gdal.utils import read_raster, write_geotiff, get_raster_statistics
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
        # Безопасное пространство имён
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
        
        # Вычисляем
        result = eval(self.expression, {"__builtins__": {}}, namespace)
        
        # Применяем масштаб
        result = result * self.scale
        
        # Клиппинг
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
    
    Для других сенсоров укажите offset=0, scale=10000 или другие значения.
    
    Пример
    -------
    >>> calc = IndexCalculator(scene)
    >>> result = calc.compute(ndvi_index, "my_ndvi")
    >>> print(result["file"])
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
    
    def compute(
        self,
        index: SpectralIndex,
        result_subdir: str,
        mask: Optional[np.ndarray] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[str] = "highest",
        resample_method: str = "bilinear"
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
        
        Возвращает
        ----------
        dict
            С ключами: index, file, expression, statistics
        """
        output_path = config.PROCESSED_DIR / result_subdir
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Загружаем каналы
        band_data, transform, proj = self._load_bands(
            index.bands, bbox, resample_to, resample_method
        )
        
        # 2. Вычисляем индекс
        result_array = index.evaluate(band_data)
        
        # 3. Применяем маску (ПОСЛЕ вычисления индекса)
        if mask is not None:
            # Ресемплим маску до размера результата, если нужно
            if mask.shape != result_array.shape:
                from scipy.ndimage import zoom
                scale_y = result_array.shape[0] / mask.shape[0]
                scale_x = result_array.shape[1] / mask.shape[1]
                mask = zoom(mask, (scale_y, scale_x), order=0)
            
            # Применяем маску
            result_array = result_array * mask
            result_array[mask == 0] = -9999
        
        # 4. Заменяем NaN на NoData
        result_array = np.nan_to_num(result_array, nan=-9999)
        
        # 5. Сохраняем
        dt_str = self.scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        out_file = output_path / f"{dt_str}_{index.name.lower()}.tif"
        
        # Опции сжатия
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
        
        # Статистика
        stats = get_raster_statistics(result_array, no_data=-9999)
        
        return {
            "index": index.name,
            "file": str(out_file),
            "expression": index.expression,
            "statistics": stats
        }
    
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
            # Временная поддиректория
            temp_dir = f"_temp_{alias}"
            result = gdal_scene.save_products(
                result_subdir=temp_dir,
                products=[product],
                bbox=bbox,
                resample_to=resample_to,
                resample_method=resample_method
            )
            
            file_path = result["files"][product]
            
            # Читаем растр
            info = read_raster(file_path)
            arr = info['array']
            
            if transform is None:
                transform = info['transform']
                proj = info['proj']
            
            # DN -> Reflectance
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
    resample_method: str = "bilinear"
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
    
    Возвращает
    ----------
    dict
        С ключами: index, file, expression, statistics
    
    Пример
    -------
    >>> from unisat_api.extras import compute_index, Sentinel2Indices
    >>> result = compute_index(scene, Sentinel2Indices.NDVI, "my_ndvi")
    """
    calc = IndexCalculator(scene, offset=offset, scale=scale)
    return calc.compute(
        index,
        result_subdir,
        mask=mask,
        bbox=bbox,
        resample_to=resample_to,
        resample_method=resample_method
    )