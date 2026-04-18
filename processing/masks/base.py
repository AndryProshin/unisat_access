"""
Базовый класс для работы с масками.
"""

import numpy as np
from typing import Optional, List
from osgeo import gdal


class Mask:
    """
    Маска для исключения пикселей (облака, тени, вода и т.д.).
    
    Способы создания:
    - Mask.from_file(path)              # из файла
    - Mask.from_array(array)            # из numpy массива
    - Mask.all_good(shape)              # все пиксели разрешены
    - Mask.all_bad(shape)               # все пиксели запрещены
    """
    
    def __init__(self, data: np.ndarray):
        """
        data: 2D массив, где 1 = хороший пиксель, 0 = исключить
        """
        self.data = data.astype(np.float32)
    
    @classmethod
    def from_file(cls, path: str, band: int = 1, invert: bool = False) -> "Mask":
        """Загрузить маску из GeoTIFF файла"""
        ds = gdal.Open(path)
        arr = ds.GetRasterBand(band).ReadAsArray()
        ds = None
        
        if invert:
            arr = 1 - arr
        
        arr = (arr > 0).astype(np.float32)
        return cls(arr)
    
    @classmethod
    def from_array(cls, array: np.ndarray) -> "Mask":
        """Создать маску из numpy массива (0/1 или boolean)"""
        arr = array.astype(np.float32)
        if arr.dtype == bool:
            arr = arr.astype(np.float32)
        return cls(arr)
    
    @classmethod
    def all_good(cls, shape: tuple) -> "Mask":
        """Создать маску, где все пиксели разрешены"""
        return cls(np.ones(shape, dtype=np.float32))
    
    @classmethod
    def all_bad(cls, shape: tuple) -> "Mask":
        """Создать маску, где все пиксели запрещены"""
        return cls(np.zeros(shape, dtype=np.float32))
    
    def apply_to_array(self, array: np.ndarray) -> np.ndarray:
        """Применить маску к numpy массиву"""
        result = array.copy()
        result[self.data == 0] = np.nan
        return result
    
    def apply_to_file(
        self,
        input_path: str,
        output_path: str,
        no_data_value: float = np.nan
    ) -> str:
        """Применить маску к GeoTIFF файлу"""
        ds = gdal.Open(input_path)
        arr = ds.ReadAsArray()
        transform = ds.GetGeoTransform()
        proj = ds.GetProjection()
        ds = None
        
        masked = self.apply_to_array(arr)
        
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(
            output_path, masked.shape[1], masked.shape[0],
            1, gdal.GDT_Float32,
            options=['COMPRESS=LZW']
        )
        out_ds.SetGeoTransform(transform)
        out_ds.SetProjection(proj)
        out_ds.GetRasterBand(1).WriteArray(masked)
        out_ds.GetRasterBand(1).SetNoDataValue(no_data_value)
        out_ds = None
        
        return output_path
    
    def save(self, path: str) -> None:
        """Сохранить маску как GeoTIFF"""
        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(
            path, self.data.shape[1], self.data.shape[0],
            1, gdal.GDT_Float32
        )
        ds.GetRasterBand(1).WriteArray(self.data)
        ds = None
    
    def __and__(self, other: "Mask") -> "Mask":
        """Логическое И двух масок"""
        return Mask(np.minimum(self.data, other.data))
    
    def __or__(self, other: "Mask") -> "Mask":
        """Логическое ИЛИ двух масок"""
        return Mask(np.maximum(self.data, other.data))
    
    def __invert__(self) -> "Mask":
        """Отрицание маски"""
        return Mask(1 - self.data)