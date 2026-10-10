"""
Internal GDAL utilities.
Not exported. Used inside extras modules.

Contains only generic functions, not tied to specific sensors.
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from osgeo import gdal

gdal.UseExceptions()


# ============================================
# READING RASTERS
# ============================================

def read_raster(
    path: str,
    band: int = 1,
    bbox: Optional[List[float]] = None,
    out_size: Optional[Tuple[int, int]] = None
) -> Dict[str, Any]:
    """
    Read a GeoTIFF file.

    Parameters
    ----------
    path : str
        File path
    band : int
        Band number (default 1)
    bbox : List[float], optional
        BBOX in file projection [minx, miny, maxx, maxy]
    out_size : Tuple[int, int], optional
        Target size (width, height) for resampling

    Returns
    -------
    dict
        With keys: array, transform, proj, width, height, bands
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
    Get raster metadata without reading data.

    Returns
    -------
    dict
        With keys: width, height, bands, transform, proj, dtype
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
# WRITING RASTERS
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
    Save array to GeoTIFF.

    Parameters
    ----------
    path : str
        Output path
    array : np.ndarray
        2D array
    transform : tuple
        GeoTransform (6 elements)
    proj : str
        Projection in WKT
    no_data : float, optional
        NoData value
    options : List[str], optional
        GDAL options (default COMPRESS=LZW, TILED=YES)
    band : int
        Band number (default 1)
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
    Save multi-band GeoTIFF.

    Parameters
    ----------
    path : str
        Output path
    arrays : List[np.ndarray]
        List of 2D arrays (one per band)
    transform : tuple
        GeoTransform (6 elements)
    proj : str
        Projection in WKT
    no_data : float, optional
        NoData value
    options : List[str], optional
        GDAL options (default COMPRESS=LZW, INTERLEAVE=PIXEL)
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
# GENERIC TRANSFORMS
# ============================================

def normalize_percentile(
    array: np.ndarray,
    min_percentile: float = 2,
    max_percentile: float = 98,
    output_range: Tuple[float, float] = (0, 255),
    no_data_value: Optional[float] = 0
) -> np.ndarray:
    """
    Normalize array with percentile clipping.

    Parameters
    ----------
    array : np.ndarray
        Input array
    min_percentile : float
        Lower percentile for clipping
    max_percentile : float
        Upper percentile for clipping
    output_range : tuple
        Output range (min, max)
    no_data_value : float, optional
        NoData value to exclude from statistics

    Returns
    -------
    np.ndarray
        Normalized array (uint8)
    """
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

    if no_data_value is not None:
        result[array == no_data_value] = 0
    else:
        result[np.isnan(array)] = 0

    return result.astype(np.uint8)


def get_utm_zone_from_bbox(bbox_wgs84: List[float]) -> Tuple[int, str]:
    """
    Determine UTM zone from BBOX in WGS84.

    Formula: zone = floor((longitude + 180) / 6) + 1

    Parameters
    ----------
    bbox_wgs84 : List[float]
        [minx, miny, maxx, maxy] in WGS84

    Returns
    -------
    tuple
        (zone, hemisphere) where hemisphere = 'N' or 'S'
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
    Create VRT from a list of file paths.

    Parameters
    ----------
    paths : List[str]
        List of paths (HTTP or local)
    vrt_path : str
        VRT path (in-memory by default)

    Returns
    -------
    str
        Path to created VRT
    """
    gdal.BuildVRT(vrt_path, paths)
    return vrt_path


def get_raster_statistics(array: np.ndarray, no_data: Optional[float] = None) -> Dict[str, float]:
    """
    Compute statistics for an array.

    Parameters
    ----------
    array : np.ndarray
        Input array
    no_data : float, optional
        NoData value to exclude

    Returns
    -------
    dict
        With keys: min, max, mean, std
    """
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


def array_to_png(
    array: np.ndarray,
    output_path: str,
    normalize: bool = True,
    min_percentile: float = 2,
    max_percentile: float = 98,
    no_data: Optional[float] = None
) -> str:
    """
    Convert a 2D array to a PNG image.

    Parameters
    ----------
    array : np.ndarray
        Input array
    output_path : str
        Output PNG path
    normalize : bool
        If True, apply percentile normalization
    min_percentile : float
        Lower percentile for clipping
    max_percentile : float
        Upper percentile for clipping
    no_data : float, optional
        NoData value to exclude from statistics (and replace with 0)

    Returns
    -------
    str
        Path to saved PNG
    """
    from PIL import Image

    if normalize:
        if no_data is not None:
            valid = array[array != no_data]
        else:
            valid = array[~np.isnan(array)]

        if len(valid) > 0:
            vmin = np.percentile(valid, min_percentile)
            vmax = np.percentile(valid, max_percentile)

            if vmax - vmin < 1e-6:
                png_array = np.zeros_like(array, dtype=np.uint8)
            else:
                png_array = np.clip(array, vmin, vmax)
                png_array = (png_array - vmin) / (vmax - vmin)
                png_array = (png_array * 255).astype(np.uint8)
        else:
            png_array = np.zeros_like(array, dtype=np.uint8)
    else:
        png_array = np.clip(array, 0, 255).astype(np.uint8)

    if no_data is not None:
        png_array[array == no_data] = 0
    else:
        png_array[np.isnan(array)] = 0

    img = Image.fromarray(png_array, mode='L')
    img.save(output_path)

    return output_path