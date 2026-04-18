"""
Предустановленные спектральные индексы для Sentinel-2.

Содержит готовые индексы с правильным маппингом каналов
и удобные функции для быстрого вычисления.

Использование:
    from processing.indices.sentinel2 import Sentinel2Indices, compute_ndvi
    
    # Быстрый NDVI
    result = compute_ndvi(scene, "my_ndvi")
    
    # Или явно через индекс
    result = compute_index(scene, Sentinel2Indices.EVI, "my_evi")
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
    # Формула: (NIR - RED) / (NIR + RED)
    NDVI = SpectralIndex(
        name="NDVI",
        expression="(nir - red) / (nir + red)",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NDWI - Normalized Difference Water Index (McFeeters)
    # Формула: (GREEN - NIR) / (GREEN + NIR)
    # Для воды: положительные значения
    NDWI = SpectralIndex(
        name="NDWI",
        expression="(green - nir) / (green + nir)",
        bands={"green": "channel3_l2a", "nir": "channel8_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # EVI - Enhanced Vegetation Index
    # Формула: 2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)
    # Уменьшает влияние атмосферы и фона почвы
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
    # Формула: ((NIR - RED) / (NIR + RED + L)) * (1 + L)
    # L = 0.5 (для умеренной растительности)
    SAVI = SpectralIndex(
        name="SAVI",
        expression="((nir - red) / (nir + red + 0.5)) * 1.5",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NDMI - Normalized Difference Moisture Index
    # Формула: (NIR - SWIR1) / (NIR + SWIR1)
    # Чувствителен к влажности растительности
    NDMI = SpectralIndex(
        name="NDMI",
        expression="(nir - swir1) / (nir + swir1)",
        bands={"nir": "channel8_l2a", "swir1": "channel11_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )
    
    # NBR - Normalized Burn Ratio
    # Формула: (NIR - SWIR2) / (NIR + SWIR2)
    # Для выявления гарей: низкие значения после пожара
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
    scale: float = 10000
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
    
    Возвращает
    ----------
    dict
        С ключами: index, file, expression, statistics
    
    Пример
    -------
    >>> from processing.indices.sentinel2 import compute_ndvi
    >>> result = compute_ndvi(scene, "ndvi_results")
    >>> print(result['file'])
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )


def compute_evi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000
) -> Dict[str, Any]:
    """
    Быстрое вычисление EVI для Sentinel-2.
    
    Пример
    -------
    >>> result = compute_evi(scene, "evi_results")
    """
    return compute_index(
        scene,
        Sentinel2Indices.EVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )


def compute_ndwi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000
) -> Dict[str, Any]:
    """
    Быстрое вычисление NDWI для Sentinel-2.
    
    Пример
    -------
    >>> result = compute_ndwi(scene, "ndwi_results")
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDWI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )


def compute_savi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000
) -> Dict[str, Any]:
    """
    Быстрое вычисление SAVI для Sentinel-2.
    
    Пример
    -------
    >>> result = compute_savi(scene, "savi_results")
    """
    return compute_index(
        scene,
        Sentinel2Indices.SAVI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )


def compute_ndmi(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000
) -> Dict[str, Any]:
    """
    Быстрое вычисление NDMI для Sentinel-2.
    
    Пример
    -------
    >>> result = compute_ndmi(scene, "ndmi_results")
    """
    return compute_index(
        scene,
        Sentinel2Indices.NDMI,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )


def compute_nbr(
    scene: Scene,
    result_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000
) -> Dict[str, Any]:
    """
    Быстрое вычисление NBR для Sentinel-2.
    
    Пример
    -------
    >>> result = compute_nbr(scene, "nbr_results")
    """
    return compute_index(
        scene,
        Sentinel2Indices.NBR,
        result_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale
    )