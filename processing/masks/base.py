# processing/masks/base.py
"""
Base class for masks.
"""

import numpy as np
from typing import Optional, List
from osgeo import gdal
from pathlib import Path


class Mask:
    """
    Mask for excluding pixels (clouds, shadows, water, etc.).

    Creation:
    - Mask.from_file(path)
    - Mask.from_array(array)
    - Mask.all_good(shape)
    - Mask.all_bad(shape)
    """

    def __init__(self, data: np.ndarray):
        """
        data: 2D array where 1 = good pixel, 0 = exclude
        """
        self.data = data.astype(np.float32)

    @classmethod
    def from_file(cls, path: str, band: int = 1, invert: bool = False) -> "Mask":
        """Load mask from a GeoTIFF file."""
        ds = gdal.Open(path)
        arr = ds.GetRasterBand(band).ReadAsArray()
        ds = None

        if invert:
            arr = 1 - arr

        arr = (arr > 0).astype(np.float32)
        return cls(arr)

    @classmethod
    def from_array(cls, array: np.ndarray) -> "Mask":
        """Create mask from a numpy array (0/1 or boolean)."""
        arr = array.astype(np.float32)
        if arr.dtype == bool:
            arr = arr.astype(np.float32)
        return cls(arr)

    @classmethod
    def all_good(cls, shape: tuple) -> "Mask":
        """Create mask where all pixels are allowed."""
        return cls(np.ones(shape, dtype=np.float32))

    @classmethod
    def all_bad(cls, shape: tuple) -> "Mask":
        """Create mask where all pixels are excluded."""
        return cls(np.zeros(shape, dtype=np.float32))

    def apply_to_array(self, array: np.ndarray) -> np.ndarray:
        """Apply mask to a numpy array."""
        result = array.copy()
        result[self.data == 0] = np.nan
        return result

    def apply_to_file(
        self,
        input_path: str,
        output_path: str,
        no_data_value: float = np.nan
    ) -> str:
        """Apply mask to a GeoTIFF file."""
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

    def __and__(self, other: "Mask") -> "Mask":
        """Logical AND of two masks."""
        return Mask(np.minimum(self.data, other.data))

    def __or__(self, other: "Mask") -> "Mask":
        """Logical OR of two masks."""
        return Mask(np.maximum(self.data, other.data))

    def __invert__(self) -> "Mask":
        """Negate mask."""
        return Mask(1 - self.data)

    def save(self, path: str, save_png: bool = False) -> Optional[str]:
        """
        Save mask as GeoTIFF (and optionally PNG).

        Parameters
        ----------
        path : str
            Output GeoTIFF path
        save_png : bool
            If True, also save PNG (0=black, 1=white)

        Returns
        -------
        Optional[str]
            Path to PNG if save_png=True, else None
        """
        from ..gdal.utils import array_to_png

        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(
            path, self.data.shape[1], self.data.shape[0],
            1, gdal.GDT_Float32
        )
        ds.GetRasterBand(1).WriteArray(self.data)
        ds = None

        png_path = None
        if save_png:
            png_path = str(Path(path).with_suffix('.png'))
            png_array = (self.data * 255).astype(np.uint8)
            from PIL import Image
            img = Image.fromarray(png_array, mode='L')
            img.save(png_path)

        return png_path