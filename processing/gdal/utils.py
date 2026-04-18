"""
Внутренние утилиты для работы с GDAL.
Не экспортируются наружу, используются внутри модулей extras.

Содержит только универсальные функции, не привязанные к конкретким сенсорам.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from osgeo import gdal

gdal.UseExceptions()


# ============================================
# ЧТЕНИЕ РАСТРОВ
# ============================================

def read_raster(
    path: str,
    band: int = 1,
    bbox: Optional[List[float]] = None,
    out_size: Optional[Tuple[int, int]] = None
) -> Dict[str, Any]:
    """
    Чтение GeoTIFF файла.
    
    Параметры
    ---------
    path : str
        Путь к файлу
    band : int
        Номер канала (по умолчанию 1)
    bbox : List[float], optional
        BBOX в проекции файла [minx, miny, maxx, maxy]
    out_size : Tuple[int, int], optional
        Целевой размер (ширина, высота) для ресемплинга
    
    Возвращает
    ----------
    dict
        С ключами: array, transform, proj, width, height, bands
    """
    ds = gdal.Open(path)
    
    if bbox or out_size:
        options = {}
        if bbox:
            options['projWin'] = [bbox[0], bbox[3], bbox[2], bbox[1]]
        if out_size:
            options['width'] = out_size[0]
            options['height'] = out_size[1]
        
        temp_ds = gdal.Warp('', ds, format='MEM', **options)
        ds = temp_ds
    
    array = ds.GetRasterBand(band).ReadAsArray().astype(np.float32)
    transform = ds.GetGeoTransform()
    proj = ds.GetProjection()
    width = ds.RasterXSize
    height = ds.RasterYSize
    bands = ds.RasterCount
    
    ds = None
    
    return {
        'array': array,
        'transform': transform,
        'proj': proj,
        'width': width,
        'height': height,
        'bands': bands
    }


def read_raster_info(path: str) -> Dict[str, Any]:
    """
    Получить метаинформацию о растре без чтения данных.
    
    Возвращает
    ----------
    dict
        С ключами: width, height, bands, transform, proj, dtype
    """
    ds = gdal.Open(path)
    info = {
        'width': ds.RasterXSize,
        'height': ds.RasterYSize,
        'bands': ds.RasterCount,
        'transform': ds.GetGeoTransform(),
        'proj': ds.GetProjection(),
        'dtype': ds.GetRasterBand(1).DataType
    }
    ds = None
    return info


# ============================================
# ЗАПИСЬ РАСТРОВ
# ============================================

def write_geotiff(
    path: str,
    array: np.ndarray,
    transform: Tuple[float, ...],
    proj: str,
    no_data: Optional[float] = None,
    options: Optional[List[str]] = None,
    band: int = 1
) -> None:
    """
    Сохранение массива в GeoTIFF.
    
    Параметры
    ---------
    path : str
        Путь для сохранения
    array : np.ndarray
        2D массив
    transform : tuple
        GeoTransform (6 элементов)
    proj : str
        Проекция в формате WKT
    no_data : float, optional
        Значение NoData
    options : List[str], optional
        Опции GDAL (по умолчанию COMPRESS=LZW, TILED=YES)
    band : int
        Номер канала (по умолчанию 1)
    """
    if options is None:
        options = ['COMPRESS=LZW', 'TILED=YES', 'BLOCKXSIZE=512', 'BLOCKYSIZE=512']
    
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(
        str(path),
        array.shape[1],
        array.shape[0],
        1,
        gdal.GDT_Float32,
        options=options
    )
    
    ds.SetGeoTransform(transform)
    ds.SetProjection(proj)
    
    out_band = ds.GetRasterBand(band)
    out_band.WriteArray(array)
    
    if no_data is not None:
        out_band.SetNoDataValue(no_data)
    
    # Сохраняем статистику (если массив не содержит NaN)
    if not np.any(np.isnan(array)):
        out_band.SetStatistics(
            float(np.min(array)),
            float(np.max(array)),
            float(np.mean(array)),
            float(np.std(array))
        )
    
    ds = None


def write_multiband_geotiff(
    path: str,
    arrays: List[np.ndarray],
    transform: Tuple[float, ...],
    proj: str,
    no_data: Optional[float] = None,
    options: Optional[List[str]] = None
) -> None:
    """
    Сохранение многоканального GeoTIFF.
    
    Параметры
    ---------
    path : str
        Путь для сохранения
    arrays : List[np.ndarray]
        Список 2D массивов (каждый = один канал)
    transform : tuple
        GeoTransform (6 элементов)
    proj : str
        Проекция в формате WKT
    no_data : float, optional
        Значение NoData
    options : List[str], optional
        Опции GDAL (по умолчанию COMPRESS=LZW, INTERLEAVE=PIXEL)
    """
    if options is None:
        options = ['COMPRESS=LZW', 'TILED=YES', 'INTERLEAVE=PIXEL']
    
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(
        str(path),
        arrays[0].shape[1],
        arrays[0].shape[0],
        len(arrays),
        gdal.GDT_Float32,
        options=options
    )
    
    ds.SetGeoTransform(transform)
    ds.SetProjection(proj)
    
    for i, array in enumerate(arrays, start=1):
        band = ds.GetRasterBand(i)
        band.WriteArray(array)
        if no_data is not None:
            band.SetNoDataValue(no_data)
    
    ds = None


# ============================================
# УНИВЕРСАЛЬНЫЕ ПРЕОБРАЗОВАНИЯ
# ============================================

def normalize_percentile(
    array: np.ndarray,
    min_percentile: float = 2,
    max_percentile: float = 98,
    output_range: Tuple[float, float] = (0, 255),
    no_data_value: Optional[float] = 0
) -> np.ndarray:
    """
    Нормализация массива с обрезкой по процентилям.
    
    Параметры
    ---------
    array : np.ndarray
        Исходный массив
    min_percentile : float
        Нижний процентиль для обрезки
    max_percentile : float
        Верхний процентиль для обрезки
    output_range : tuple
        Выходной диапазон (min, max)
    no_data_value : float, optional
        Значение NoData для исключения из статистики
    
    Возвращает
    ----------
    np.ndarray
        Нормализованный массив (uint8)
    """
    # Исключаем NoData из статистики
    if no_data_value is not None:
        valid = array[array != no_data_value]
    else:
        valid = array[~np.isnan(array)]
    
    if len(valid) == 0:
        return np.zeros_like(array, dtype=np.uint8)
    
    vmin = np.percentile(valid, min_percentile)
    vmax = np.percentile(valid, max_percentile)
    
    if vmax - vmin < 1e-6:
        return np.zeros_like(array, dtype=np.uint8)
    
    result = np.clip(array, vmin, vmax)
    result = (result - vmin) / (vmax - vmin)
    result = result * (output_range[1] - output_range[0]) + output_range[0]
    
    # NoData зануляем
    if no_data_value is not None:
        result[array == no_data_value] = 0
    else:
        result[np.isnan(array)] = 0
    
    return result.astype(np.uint8)


def get_utm_zone_from_bbox(bbox_wgs84: List[float]) -> Tuple[int, str]:
    """
    Определить UTM зону по BBOX в WGS84.
    
    Формула: zone = floor((longitude + 180) / 6) + 1
    
    Параметры
    ---------
    bbox_wgs84 : List[float]
        [minx, miny, maxx, maxy] в WGS84
    
    Возвращает
    ----------
    tuple
        (zone, hemisphere) где hemisphere = 'N' или 'S'
    """
    center_lon = (bbox_wgs84[0] + bbox_wgs84[2]) / 2
    zone = int(np.floor((center_lon + 180) / 6)) + 1
    
    center_lat = (bbox_wgs84[1] + bbox_wgs84[3]) / 2
    hemisphere = 'N' if center_lat >= 0 else 'S'
    
    return zone, hemisphere


def create_vrt_from_paths(
    paths: List[str],
    vrt_path: str = '/vsimem/temp.vrt'
) -> str:
    """
    Создать VRT из списка путей к файлам.
    
    Параметры
    ---------
    paths : List[str]
        Список путей (HTTP или локальных)
    vrt_path : str
        Путь для VRT (в памяти по умолчанию)
    
    Возвращает
    ----------
    str
        Путь к созданному VRT
    """
    gdal.BuildVRT(vrt_path, paths)
    return vrt_path


def get_raster_statistics(array: np.ndarray, no_data: Optional[float] = None) -> Dict[str, float]:
    """
    Вычислить статистику для массива.
    
    Параметры
    ---------
    array : np.ndarray
        Входной массив
    no_data : float, optional
        Значение NoData для исключения
    
    Возвращает
    ----------
    dict
        С ключами: min, max, mean, std
    """
    # Исключаем NoData или NaN из статистики
    if no_data is not None:
        valid = array[array != no_data]
    else:
        valid = array[~np.isnan(array)]
    
    if len(valid) == 0:
        return {'min': np.nan, 'max': np.nan, 'mean': np.nan, 'std': np.nan}
    
    return {
        'min': float(np.min(valid)),
        'max': float(np.max(valid)),
        'mean': float(np.mean(valid)),
        'std': float(np.std(valid))
    }