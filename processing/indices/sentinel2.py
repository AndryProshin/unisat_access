# processing/indices/sentinel2.py
"""
Preset spectral indices for Sentinel-2.

Provides ready-to-use indices with proper band mapping
and convenience functions for quick computation.

Usage:
    from processing.indices.sentinel2 import Sentinel2Indices, compute_ndvi

    result = compute_ndvi(scene, "my_ndvi")
    result = compute_ndvi(scene, "my_ndvi", save_png=True)
"""

from typing import Dict, Any, Optional, List
import numpy as np

from .base import SpectralIndex, compute_index
from unisat_api.scene import Scene


# ============================================
# PRESET INDICES
# ============================================

class Sentinel2Indices:
    """
    Preset indices for Sentinel-2.

    Available:
    - NDVI : Normalized Difference Vegetation Index
    - NDWI : Normalized Difference Water Index (McFeeters)
    - EVI  : Enhanced Vegetation Index
    - SAVI : Soil Adjusted Vegetation Index
    - NDMI : Normalized Difference Moisture Index
    - NBR  : Normalized Burn Ratio
    """

    NDVI = SpectralIndex(
        name="NDVI",
        expression="(nir - red) / (nir + red)",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    NDWI = SpectralIndex(
        name="NDWI",
        expression="(green - nir) / (green + nir)",
        bands={"green": "channel3_l2a", "nir": "channel8_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

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

    SAVI = SpectralIndex(
        name="SAVI",
        expression="((nir - red) / (nir + red + 0.5)) * 1.5",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    NDMI = SpectralIndex(
        name="NDMI",
        expression="(nir - swir1) / (nir + swir1)",
        bands={"nir": "channel8_l2a", "swir1": "channel11_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    NBR = SpectralIndex(
        name="NBR",
        expression="(nir - swir2) / (nir + swir2)",
        bands={"nir": "channel8_l2a", "swir2": "channel12_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def compute_ndvi(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick NDVI computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.NDVI,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )


def compute_evi(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick EVI computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.EVI,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )


def compute_ndwi(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick NDWI computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.NDWI,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )


def compute_savi(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick SAVI computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.SAVI,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )


def compute_ndmi(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick NDMI computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.NDMI,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )


def compute_nbr(
    scene: Scene,
    data_subdir: str,
    mask: Optional[np.ndarray] = None,
    bbox: Optional[List[float]] = None,
    offset: float = -1000,
    scale: float = 10000,
    save_png: bool = False,
    keep_tmp: bool = False
) -> Dict[str, Any]:
    """Quick NBR computation for Sentinel-2."""
    return compute_index(
        scene,
        Sentinel2Indices.NBR,
        data_subdir,
        mask=mask,
        bbox=bbox,
        offset=offset,
        scale=scale,
        save_png=save_png,
        keep_tmp=keep_tmp
    )