# processing/masks/sentinel2.py
"""
Utilities for Sentinel-2 (SCL) masks.
"""

import numpy as np
from typing import List, Optional, Dict
from scipy.ndimage import binary_dilation

from unisat_api.scene import Scene
from processing.gdal.utils import read_raster
from processing.gdal.scene import GDALScene


# ============================================
# CONSTANTS
# ============================================

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

SCL_GOOD_CLASSES = {
    'vegetation': [4, 5],
    'vegetation_water': [4, 5, 6],
    'all_land': [4, 5, 6, 7],
    'clean': [4, 5, 6, 7],
    'strict': [4, 5],
    'loose': [4, 5, 6, 7, 2]
}

SCL_CLOUD_CLASSES = [8, 9, 10]

SCL_SHADOW_CLASS = 3


# ============================================
# SCL UTILITIES
# ============================================

def create_scl_mask(
    scl_array: np.ndarray,
    good_classes: Optional[List[int]] = None,
    dilate_clouds: int = 0,
    dilate_shadows: int = 0
) -> np.ndarray:
    """
    Create a binary mask from SCL.

    Parameters
    ----------
    scl_array : np.ndarray
        SCL array (values 0-11)
    good_classes : List[int], optional
        Classes considered good (default [4, 5, 6])
    dilate_clouds : int
        Dilation radius for cloud classes (8, 9, 10)
    dilate_shadows : int
        Dilation radius for shadows (class 3)

    Returns
    -------
    np.ndarray
        Mask (1 = good pixel, 0 = exclude)
    """
    if good_classes is None:
        good_classes = SCL_GOOD_CLASSES['vegetation_water']

    mask = np.isin(scl_array, good_classes)

    if dilate_clouds > 0:
        cloud_mask = np.isin(scl_array, SCL_CLOUD_CLASSES)
        dilated = binary_dilation(cloud_mask, iterations=dilate_clouds)
        mask = mask & ~dilated

    if dilate_shadows > 0:
        shadow_mask = (scl_array == SCL_SHADOW_CLASS)
        dilated = binary_dilation(shadow_mask, iterations=dilate_shadows)
        mask = mask & ~dilated

    return mask.astype(np.float32)


def load_scl_for_scene(scene: Scene, data_subdir: str) -> np.ndarray:
    """
    Load SCL product for a scene.

    Parameters
    ----------
    scene : Scene
        Scene object
    data_subdir : str
        Subdirectory inside data/ for temporary files

    Returns
    -------
    np.ndarray
        SCL array (values 0-11)
    """
    gdal_scene = GDALScene(scene)

    result = gdal_scene.save_products(
        data_subdir=f"{data_subdir}/_tmp/scl",
        products=["s2_scl"],
        resample_to="highest",
        resample_method="nearest"
    )

    scl_path = result["files"].get("s2_scl")
    if not scl_path:
        raise ValueError("SCL product not found for this scene")

    info = read_raster(scl_path)
    scl_array = info['array']

    return scl_array.astype(np.int16)


def get_scl_mask_for_scene(
    scene: Scene,
    data_subdir: str,
    good_classes: Optional[List[int]] = None,
    dilate_clouds: int = 2,
    dilate_shadows: int = 3
) -> np.ndarray:
    """
    Convenience: load SCL and build mask in one call.

    Parameters
    ----------
    scene : Scene
        Scene object
    data_subdir : str
        Subdirectory inside data/ for temporary files
    good_classes : List[int], optional
        Good classes (default [4, 5, 6])
    dilate_clouds : int
        Cloud dilation (default 2)
    dilate_shadows : int
        Shadow dilation (default 3)

    Returns
    -------
    np.ndarray
        Mask (1 = good pixel, 0 = exclude)
    """
    scl_array = load_scl_for_scene(scene, data_subdir)
    return create_scl_mask(scl_array, good_classes, dilate_clouds, dilate_shadows)


def get_scl_class_name(class_code: int) -> str:
    """Return SCL class name by code."""
    for name, code in SCL_CLASSES.items():
        if code == class_code:
            return name
    return f"UNKNOWN_{class_code}"


def print_scl_statistics(scl_array: np.ndarray) -> None:
    """Print SCL class distribution."""
    print("\nSCL Statistics:")
    print("-" * 40)

    unique, counts = np.unique(scl_array, return_counts=True)
    total = scl_array.size

    for code, count in zip(unique, counts):
        name = get_scl_class_name(code)
        percent = 100 * count / total
        print(f"  {code:2d} {name:<20}: {percent:5.1f}% ({count} pixels)")

    print("-" * 40)