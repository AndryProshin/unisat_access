"""
Утилиты для работы с масками Sentinel-2 (SCL).
"""

import numpy as np
from typing import List, Optional, Dict
from scipy.ndimage import binary_dilation

from unisat_api.scene import Scene
from processing.gdal.utils import read_raster
from processing.gdal.scene import GDALScene


# ============================================
# КОНСТАНТЫ
# ============================================

# Классы SCL (Scene Classification Layer)
SCL_CLASSES = {
    'NO_DATA': 0,
    'SATURATED_DEFECTIVE': 1,
    'DARK_AREA': 2,
    'CLOUD_SHADOWS': 3,
    'VEGETATION': 4,
    'NOT_VEGETATED': 5,
    'WATER': 6,
    'UNCLASSIFIED': 7,
    'CLOUD_MEDIUM': 8,
    'CLOUD_HIGH': 9,
    'THIN_CIRRUS': 10,
    'SNOW': 11
}

# Предустановленные наборы "хороших" классов
SCL_GOOD_CLASSES = {
    'vegetation': [4, 5],           # растительность + почва
    'vegetation_water': [4, 5, 6],  # + вода
    'all_land': [4, 5, 6, 7],       # всё кроме облаков и теней
    'clean': [4, 5, 6, 7],          # синоним all_land
    'strict': [4, 5],               # только растительность и почва
    'loose': [4, 5, 6, 7, 2]        # + тёмные области
}

# Классы, считающиеся облачными
SCL_CLOUD_CLASSES = [8, 9, 10]

# Класс теней
SCL_SHADOW_CLASS = 3


# ============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С SCL
# ============================================

def create_scl_mask(
    scl_array: np.ndarray,
    good_classes: Optional[List[int]] = None,
    dilate_clouds: int = 0,
    dilate_shadows: int = 0
) -> np.ndarray:
    """
    Создать бинарную маску из SCL.
    
    Параметры
    ---------
    scl_array : np.ndarray
        Массив SCL (значения 0-11)
    good_classes : List[int], optional
        Классы, считающиеся "хорошими"
        (по умолчанию [4, 5, 6] = растительность, почва, вода)
    dilate_clouds : int
        Радиус раздувания облачных классов (8,9,10)
    dilate_shadows : int
        Радиус раздувания теней (класс 3)
    
    Возвращает
    ----------
    np.ndarray
        Маска (1 = хороший пиксель, 0 = исключить)
    """
    if good_classes is None:
        good_classes = SCL_GOOD_CLASSES['vegetation_water']
    
    # Начальная маска: хорошие классы
    mask = np.isin(scl_array, good_classes)
    
    # Раздувание облаков
    if dilate_clouds > 0:
        cloud_mask = np.isin(scl_array, SCL_CLOUD_CLASSES)
        dilated = binary_dilation(cloud_mask, iterations=dilate_clouds)
        mask = mask & ~dilated
    
    # Раздувание теней
    if dilate_shadows > 0:
        shadow_mask = (scl_array == SCL_SHADOW_CLASS)
        dilated = binary_dilation(shadow_mask, iterations=dilate_shadows)
        mask = mask & ~dilated
    
    return mask.astype(np.float32)


def load_scl_for_scene(scene: Scene) -> np.ndarray:
    """
    Загрузить SCL продукт для сцены.
    
    Параметры
    ---------
    scene : Scene
        Объект сцены
    
    Возвращает
    ----------
    np.ndarray
        Массив SCL (значения 0-11)
    """
    gdal_scene = GDALScene(scene)
    
    # Временно сохраняем SCL
    result = gdal_scene.save_products(
        result_subdir="_temp_scl",
        products=["s2_scl"],
        resample_to="highest",
        resample_method="nearest"
    )
    
    scl_path = result["files"].get("s2_scl")
    if not scl_path:
        raise ValueError("SCL продукт не найден для этой сцены")
    
    # Читаем массив
    info = read_raster(scl_path)
    scl_array = info['array']
    
    return scl_array.astype(np.int16)


def get_scl_mask_for_scene(
    scene: Scene,
    good_classes: Optional[List[int]] = None,
    dilate_clouds: int = 2,
    dilate_shadows: int = 3
) -> np.ndarray:
    """
    Удобная функция: загрузить SCL и создать маску за один вызов.
    
    Параметры
    ---------
    scene : Scene
        Объект сцены
    good_classes : List[int], optional
        Хорошие классы (по умолчанию [4,5,6])
    dilate_clouds : int
        Раздувание облаков (по умолчанию 2)
    dilate_shadows : int
        Раздувание теней (по умолчанию 3)
    
    Возвращает
    ----------
    np.ndarray
        Маска (1 = хороший пиксель, 0 = исключить)
    """
    scl_array = load_scl_for_scene(scene)
    return create_scl_mask(scl_array, good_classes, dilate_clouds, dilate_shadows)


def get_scl_class_name(class_code: int) -> str:
    """Получить название класса SCL по коду."""
    for name, code in SCL_CLASSES.items():
        if code == class_code:
            return name
    return f"UNKNOWN_{class_code}"


def print_scl_statistics(scl_array: np.ndarray) -> None:
    """Вывести статистику распределения классов SCL."""
    print("\nSCL Statistics:")
    print("-" * 40)
    
    unique, counts = np.unique(scl_array, return_counts=True)
    total = scl_array.size
    
    for code, count in zip(unique, counts):
        name = get_scl_class_name(code)
        percent = 100 * count / total
        print(f"  {code:2d} {name:<20}: {percent:5.1f}% ({count} pixels)")
    
    print("-" * 40)