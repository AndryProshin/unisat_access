# processing/indices/base.py
"""
Spectral indices for satellite data.

Generic tool for computing spectral indices.
Contains no sensor-specific presets.

Features:
- User-defined indices via expression
- Preset indices (sensor-specific - in other modules)
- Cloud mask support
- Save results to GeoTIFF
- Optional PNG preview
"""

import json
import csv
import shutil
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from unisat_api.scene import Scene
from unisat_api import config
from processing.gdal.utils import read_raster, write_geotiff, get_raster_statistics, array_to_png
from processing.gdal.scene import GDALScene


# ============================================
# SPECTRAL INDEX
# ============================================

class SpectralIndex:
    """
    Spectral index definition.

    Parameters
    ----------
    name : str
        Index name (e.g. "NDVI")
    expression : str
        Formula using names from bands.
        Available: np, sqrt, log, log10, exp, abs, where, min, max
    bands : Dict[str, str]
        Mapping of names in expression -> product names in scene
    scale : float, default=1
        Result multiplier (e.g. 10000 for int16)
    output_range : tuple, optional
        Result clipping (min, max)
    no_data : float, default=np.nan
        NoData value
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
        Evaluate the index expression.

        Parameters
        ----------
        band_data : Dict[str, np.ndarray]
            Arrays for each name in bands

        Returns
        -------
        np.ndarray
            Result array
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
# INDEX CALCULATOR
# ============================================

class IndexCalculator:
    """
    Spectral index calculator for a scene.

    Parameters
    ----------
    scene : Scene
        Scene object
    offset : float, default=-1000
        Offset for DN -> Reflectance (Sentinel-2)
    scale : float, default=10000
        Scale for DN -> Reflectance (Sentinel-2)
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
        resample_to: Optional[float],
        resample_method: str
    ) -> None:
        """Save _params.json with query and operation parameters."""
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
        print(f"   Saved _params.json to {output_path}")

    def _save_metadata(self, output_path: Path, filename: str) -> None:
        """Save _metadata.txt in the final directory."""
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
        print(f"   Saved _metadata.txt to {output_path}")

    def compute(
        self,
        index: SpectralIndex,
        data_subdir: str,
        mask: Optional[np.ndarray] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[float] = None,
        resample_method: str = "bilinear",
        save_png: bool = False,
        keep_tmp: bool = False
    ) -> Dict[str, Any]:
        """
        Compute index and save as GeoTIFF.

        Parameters
        ----------
        index : SpectralIndex
            Index to compute
        data_subdir : str
            Subdirectory inside data/
        mask : np.ndarray, optional
            Mask (1 = good pixel, 0 = exclude)
        bbox : List[float], optional
            BBOX in WGS84 [minx, miny, maxx, maxy]
        resample_to : float, optional
            Target resolution in meters, or None to keep native
        resample_method : str
            "nearest", "bilinear", "cubic"
        save_png : bool, default=False
            If True, create PNG preview of the result
        keep_tmp : bool, default=False
            If True, keep temporary files after success

        Returns
        -------
        dict
            With keys: index, file, expression, statistics, (png_file)
        """
        output_path = config.DATA_DIR / data_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. Load bands
        band_data, transform, proj = self._load_bands(
            index.bands, bbox, resample_to, resample_method, data_subdir, keep_tmp
        )

        # 2. Compute index
        result_array = index.evaluate(band_data)

        # 3. Apply mask
        if mask is not None:
            if mask.shape != result_array.shape:
                from scipy.ndimage import zoom
                scale_y = result_array.shape[0] / mask.shape[0]
                scale_x = result_array.shape[1] / mask.shape[1]
                mask = zoom(mask, (scale_y, scale_x), order=0)

            result_array = result_array * mask
            result_array[mask == 0] = -9999

        # 4. Replace NaN with NoData
        result_array = np.nan_to_num(result_array, nan=-9999)

        # 5. Save GeoTIFF
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

        # 6. Save PNG (optional)
        png_file = None
        if save_png:
            png_path = out_file.with_suffix('.png')
            array_to_png(result_array, str(png_path), normalize=True, no_data=-9999)
            png_file = str(png_path)

        # 7. Save logs
        self._save_params_json(output_path, index, mask is not None, bbox, resample_to, resample_method)
        self._save_metadata(output_path, filename)

        # 8. Statistics
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
        resample_to: Optional[float],
        resample_method: str,
        data_subdir: str,
        keep_tmp: bool = False
    ) -> tuple:
        """
        Load bands and convert DN -> Reflectance.

        Temporary GeoTIFFs are written to <data_subdir>/_tmp/<alias>/.
        On success and keep_tmp=False, the whole _tmp directory is removed.
        On error it is left intact for inspection.

        Returns
        -------
        tuple
            (band_data, transform, proj)
        """
        gdal_scene = GDALScene(self.scene)
        band_data = {}
        transform = None
        proj = None

        for alias, product in bands.items():
            tmp_dir = f"{data_subdir}/_tmp/{alias}"
            result = gdal_scene.save_products(
                data_subdir=tmp_dir,
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

        if not keep_tmp:
            tmp_root = config.DATA_DIR / data_subdir / "_tmp"
            shutil.rmtree(tmp_root, ignore_errors=True)

        return band_data, transform, proj


# ============================================
# CONVENIENCE FUNCTION
# ============================================

def compute_index(
    scene: Scene,
    index: SpectralIndex,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    resample_to: Optional[float] = None,
    resample_method: str = "bilinear",
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """
    Quick index computation.

    Parameters
    ----------
    scene : Scene
        Scene object
    index : SpectralIndex
        Index to compute
    data_subdir : str
        Subdirectory inside data/
    mask : np.ndarray, optional
        Cloud mask
    bbox : List[float], optional
        BBOX in WGS84 [minx, miny, maxx, maxy]
    offset : float
        Offset for DN->Reflectance (default -1000)
    scale : float
        Scale for DN->Reflectance (default 10000)
    resample_to : float, optional
        Target resolution in meters, or None to keep native
    resample_method : str
        "nearest", "bilinear", "cubic"
    save_png : bool, default=False
        If True, create PNG preview
    keep_tmp : bool, default=False
        If True, keep temporary files after success
    """
    calc = IndexCalculator(scene, offset=offset, scale=scale)
    return calc.compute(
        index,
        data_subdir,
        mask=mask,
        bbox=bbox,
        resample_to=resample_to,
        resample_method=resample_method,
        save_png=save_png,
        keep_tmp=keep_tmp
    )