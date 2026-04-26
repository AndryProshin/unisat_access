"""
Предустановленные спектральные индексы для Sentinel-2.

Содержит готовые индексы с правильным маппингом каналов
и удобные функции для быстрого вычисления.

Использование:
    from processing.indices.sentinel2 import Sentinel2Indices, compute_ndvi
    
    # Быстрый NDVI
    result = compute_ndvi(scene, "my_ndvi")
    
    # NDVI с PNG-превью
    result = compute_ndvi(scene, "my_ndvi", save_png=True)
"""

from typing import Dict, Any, Optional, List
import numpy as np

from .base import SpectralIndex, compute_index
from unisat_api.scene import Scene


# ============================================
# ПРЕДУСТАНОВЛЕННЫЕ ИНДЕКСЫ
# ============================================

class Sentinel2Indices:
    """
    Предустановленные индексы для Sentinel-2.
    
    Доступные индексы:
    - NDVI : Normalized Difference Vegetation Index
    - NDWI : Normalized Difference Water Index (McFeeters)
    - EVI  : Enhanced Vegetation Index
    - SAVI : Soil Adjusted Vegetation Index
    - NDMI : Normalized Difference Moisture Index
    - NBR  : Normalized Burn Ratio
    """
    
    # NDVI - Normalized Difference Vegetation Index
    NDVI = SpectralIndex(
        name="NDVI",
        expression="(nir - red) / (nir + red)",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NDWI - Normalized Difference Water Index
    NDWI = SpectralIndex(
        name="NDWI",
        expression="(green - nir) / (green + nir)",
        bands={"green": "channel3_l2a", "nir": "channel8_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # EVI - Enhanced Vegetation Index
    EVI = SpectralIndex(
        name="EVI",
        expression="2.5 * (nir - red) / (nir + 6*red - 7.5*blue + 1)",
        bands={
            "nir": "channel8_l2a",
            "red": "channel4_l2a",
            "blue": "channel2_l2a"
        },
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # SAVI - Soil Adjusted Vegetation Index
    SAVI = SpectralIndex(
        name="SAVI",
        expression="((nir - red) / (nir + red + 0.5)) * 1.5",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NDMI - Normalized Difference Moisture Index
    NDMI = SpectralIndex(
        name="NDMI",
        expression="(nir - swir1) / (nir + swir1)",
        bands={"nir": "channel8_l2a", "swir1": "channel11_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NBR - Normalized Burn Ratio
    NBR = SpectralIndex(
        name="NBR",
        expression="(nir - swir2) / (nir + swir2)",
        bands={"nir": "channel8_l2a", "swir2": "channel12_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )


# ============================================
# УДОБНЫЕ ФУНКЦИИ ДЛЯ БЫСТРОГО ВЫЗОВА
# ============================================

def compute_ndvi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление NDVI для Sentinel-2.
    
    Параметры
    ---------
    scene : Scene
        Объект сцены
    result_subdir : str
        Поддиректория внутри data/processed/
    mask : np.ndarray, optional
        Маска облачности (1 = хороший пиксель)
    bbox : List[float], optional
        BBOX в WGS84 [minx, miny, maxx, maxy]
    offset : float
        Сдвиг для DN→Reflectance (по умолчанию -1000)
    scale : float
        Масштаб для DN→Reflectance (по умолчанию 10000)
    save_png : bool, default=False
        Если True, создать PNG-превью результата
    
    Возвращает
    ----------
    dict
        С ключами: index, file, expression, statistics, (png_file)
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )


def compute_evi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление EVI для Sentinel-2.
    """
    return compute_index(
        scene,
        Sentinel2Indices.EVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )


def compute_ndwi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление NDWI для Sentinel-2.
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDWI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )


def compute_savi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление SAVI для Sentinel-2.
    """
    return compute_index(
        scene,
        Sentinel2Indices.SAVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )


def compute_ndmi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление NDMI для Sentinel-2.
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDMI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )


def compute_nbr(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False
) -> Dict[str, Any]:
    """
    Быстрое вычисление NBR для Sentinel-2.
    """
    return compute_index(
        scene,
        Sentinel2Indices.NBR,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png
    )