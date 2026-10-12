# processing/masks/base.py
"""
Base class for masks.
"""

import os
import tempfile
import numpy as np
from typing import Optional
from osgeo import gdal
from pathlib import Path

from unisat_api import config
from unisat_api.exceptions import StorageError


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
        return cls(array.astype(np.float32))

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

    def save(
        self,
        data_path: Optional[str] = None,
        s3_path: Optional[str] = None,
        save_png: bool = False,
        transform: Optional[tuple] = None,
        proj: Optional[str] = None
    ) -> Optional[str]:
        """
        Save mask as GeoTIFF, optionally to S3, optionally with a PNG preview.

        Exactly one of data_path / s3_path must be provided.

        Parameters
        ----------
        data_path : str, optional
            Path relative to data/, including file name. If the path has
            no extension, ".tif" is appended. Example:
            "masks/clean/scl_clean" -> data/masks/clean/scl_clean.tif
        s3_path : str, optional
            Path relative to the S3 base. If the path has no extension,
            ".tif" is appended. S3 connection is configured inside
            s3tool (via .env next to s3tool.py).
        save_png : bool
            If True, also save a PNG preview next to the GeoTIFF
            (0=black, 1=white). For S3, the PNG is uploaded alongside.
        transform : tuple, optional
            GeoTransform (6 numbers). If provided, written to the GeoTIFF.
        proj : str, optional
            Projection in WKT. If provided, written to the GeoTIFF.

        Returns
        -------
        Optional[str]
            Path to PNG if save_png=True, else None. For S3, the S3 key
            (relative to base) of the PNG.
        """
        if (data_path is None) == (s3_path is None):
            raise ValueError(
                "Mask.save: exactly one of data_path or s3_path must be provided"
            )

        if data_path is not None:
            return self._save_local(data_path, save_png, transform, proj)
        return self._save_s3(s3_path, save_png, transform, proj)

    # ------------------------------------------------------------------
    # Internal save helpers
    # ------------------------------------------------------------------

    def _save_local(
        self,
        data_path: str,
        save_png: bool,
        transform: Optional[tuple],
        proj: Optional[str]
    ) -> Optional[str]:
        """Write GeoTIFF (and optional PNG) under config.DATA_DIR."""
        rel = data_path
        if not Path(rel).suffix:
            rel = rel + ".tif"

        out_path = config.DATA_DIR / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self._write_geotiff(str(out_path), transform, proj)

        png_path = None
        if save_png:
            png_path = str(out_path.with_suffix(".png"))
            self._write_png(png_path)

        return png_path

    def _save_s3(
        self,
        s3_path: str,
        save_png: bool,
        transform: Optional[tuple],
        proj: Optional[str]
    ) -> Optional[str]:
        """Write GeoTIFF (and optional PNG) to S3 via S3Tool."""
        from s3tool import S3Tool, S3ToolError

        try:
            tool = S3Tool(raise_on_fatal=True)
        except S3ToolError as e:
            raise StorageError(f"Mask.save: cannot connect to S3: {e}") from None

        # Target key and its parent directory in S3.
        tif_key = s3_path if Path(s3_path).suffix else s3_path + ".tif"
        tif_parent = str(Path(tif_key).parent)
        if tif_parent == ".":
            tif_parent = ""

        png_key = str(Path(tif_key).with_suffix(".png")) if save_png else None
        png_parent = ""
        if png_key:
            png_parent = str(Path(png_key).parent)
            if png_parent == ".":
                png_parent = ""

        with tempfile.TemporaryDirectory() as tmp:
            # Save under the target base name, so upload_file places
            # the object in S3 under the correct key.
            tif_local = os.path.join(tmp, Path(tif_key).name)
            self._write_geotiff(tif_local, transform, proj)

            if not tool.upload_file(tif_local, tif_parent):
                raise StorageError(
                    f"Mask.save: failed to upload GeoTIFF to S3 "
                    f"[{tool.get_error_code()}] {tool.get_error_message()}"
                )

            if save_png:
                png_local = os.path.join(tmp, Path(png_key).name)
                self._write_png(png_local)
                if not tool.upload_file(png_local, png_parent):
                    raise StorageError(
                        f"Mask.save: failed to upload PNG to S3 "
                        f"[{tool.get_error_code()}] {tool.get_error_message()}"
                    )

        return png_key

    # ------------------------------------------------------------------
    # Low-level writers
    # ------------------------------------------------------------------

    def _write_geotiff(
        self,
        path: str,
        transform: Optional[tuple],
        proj: Optional[str]
    ) -> None:
        """Write the mask array to a GeoTIFF file."""
        driver = gdal.GetDriverByName('GTiff')
        ds = driver.Create(
            path, self.data.shape[1], self.data.shape[0],
            1, gdal.GDT_Float32,
            options=['COMPRESS=LZW']
        )
        if transform is not None:
            ds.SetGeoTransform(transform)
        if proj is not None:
            ds.SetProjection(proj)
        ds.GetRasterBand(1).WriteArray(self.data)
        ds = None

    def _write_png(self, path: str) -> None:
        """Write the mask array as an 8-bit PNG."""
        from PIL import Image
        png_array = (self.data * 255).astype(np.uint8)
        img = Image.fromarray(png_array, mode='L')
        img.save(path)