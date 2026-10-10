# scene.py (processing/gdal/scene.py)
"""
GDAL extension for Scene.
Requires: pip install gdal
"""

import json
import csv
import os
import shutil
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from osgeo import gdal, osr, ogr

from unisat_api.scene import Scene
from unisat_api import config

from .utils import read_raster, write_geotiff, get_raster_statistics, array_to_png


class GDALScene:
    """GDAL wrapper around Scene."""

    def __init__(self, scene: Scene):
        self._scene = scene
        gdal.UseExceptions()

    @property
    def original(self) -> Scene:
        """Access to the original scene."""
        return self._scene

    def save_products(
        self,
        data_subdir: str,
        products: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[Union[str, float]] = None,
        resample_method: str = "nearest",
        qlook: bool = False
    ) -> Dict[str, Any]:
        """
        Merge fragments per product, clip by bbox and save as GeoTIFF.

        Args:
            data_subdir: subdirectory inside data/_scene/
            products: list of products (None -> all scene products)
            bbox: [minx, miny, maxx, maxy] in WGS84 (None -> from scene params)
            resample_to: resampling (None, "highest", "lowest", or meters)
            resample_method: resampling method ("nearest", "bilinear", "cubic")
            qlook: if True, create a quicklook PNG next to GeoTIFF

        Returns:
            dict with output_dir, files and qlook_files
        """
        output_path = config.DATA_DIR / data_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        self._save_params_json(output_path, resample_to, resample_method, bbox, products)

        if products is None:
            products = list(self._scene.products.keys())

        if bbox is None:
            bbox = self._scene._params.get("bbox")
            if bbox is None:
                raise ValueError("bbox is not set in scene params nor in arguments")

        print(f"\n=== Diagnostics ===")
        print(f"Scene: {self._scene.dt}")
        print(f"Source bbox (WGS84): {bbox}")

        fragments = self._scene.get_fragments()
        if not fragments:
            raise ValueError("No fragments to process")

        print(f"Fragments: {len(fragments)}")

        saved_files = {}
        dt_str = self._scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]

        for product in products:
            filename = self._process_product(
                product, fragments, bbox, output_path,
                resample_to, resample_method
            )
            if filename:
                tif_path = output_path / filename
                saved_files[product] = str(tif_path)

                if qlook:
                    ds = gdal.Open(str(tif_path))
                    arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                    ds = None
                    qlook_path = tif_path.parent / (tif_path.stem + "_qlook.png")
                    array_to_png(arr, str(qlook_path), normalize=True, no_data=0)

        self._save_final_metadata(output_path, saved_files)

        print(f"\nSaved to: {output_path}")

        return {
            "output_dir": str(output_path),
            "files": saved_files,
            "qlook_files": {prod: str(output_path / f"{dt_str}_{prod}_qlook.png") for prod in saved_files} if qlook else {}
        }

    def _save_params_json(
        self,
        output_path: Path,
        resample_to: Optional[Union[str, float]],
        resample_method: str,
        bbox: Optional[List[float]],
        products: Optional[List[str]]
    ) -> None:
        """Save _params.json (only if not exists)."""
        params_file = output_path / "_params.json"
        if params_file.exists():
            return

        params_data = {
            "query": self._scene._params.copy(),
            "operation": {
                "name": "save_products",
                "timestamp": datetime.now().isoformat(),
                "package_version": "1.0.0",
                "resample_to": resample_to,
                "resample_method": resample_method,
                "bbox_used": bbox or self._scene._params.get("bbox"),
                "products_used": products
            }
        }

        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump(params_data, f, indent=2, ensure_ascii=False)
        print(f"   Saved _params.json to {output_path}")

    def _save_final_metadata(self, output_path: Path, saved_files: Dict[str, str]) -> None:
        """Append _metadata.txt in the final directory."""
        metadata_file = output_path / "_metadata.txt"
        file_exists = metadata_file.exists()

        with open(metadata_file, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter='|')
            if not file_exists:
                writer.writerow(["dt", "satellite", "device", "station", "product", "file"])

            for product, filepath in saved_files.items():
                filename = Path(filepath).name
                writer.writerow([
                    self._scene.dt, self._scene.satellite,
                    self._scene.device, self._scene.station,
                    product, filename
                ])

        print(f"   Appended _metadata.txt in {output_path}")

    def _bbox_to_cutline(self, bbox_wgs84: List[float]) -> str:
        """Convert bbox to a GeoJSON file for gdal.Warp cutline."""
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[1])
        ring.AddPoint(bbox_wgs84[2], bbox_wgs84[1])
        ring.AddPoint(bbox_wgs84[2], bbox_wgs84[3])
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[3])
        ring.AddPoint(bbox_wgs84[0], bbox_wgs84[1])

        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": json.loads(poly.ExportToJson()),
                    "properties": {}
                }]
            }
            json.dump(geojson, f)
            return f.name

    def _process_product(
        self,
        product: str,
        fragments: List[Dict],
        bbox_wgs84: List[float],
        output_path: Path,
        resample_to: Optional[Union[str, float]],
        resample_method: str
    ) -> Optional[str]:
        """Process a single product: merge fragments and clip by bbox."""

        print(f"\n--- Processing product: {product} ---")

        http_paths = []
        for i, frag in enumerate(fragments):
            if product in frag:
                path = frag[product]
                http_paths.append(f"{config.NGINX_BASE_URL}/{path}")
                print(f"  Fragment {i}: {path}")

        if not http_paths:
            print(f"Warning: product {product} not found in fragments")
            return None

        print(f"Fragments for product: {len(http_paths)}")

        print(f"\nBuilding VRT for {product}...")
        vrt_path = f"/vsimem/{product}_merge.vrt"
        gdal.BuildVRT(vrt_path, http_paths)

        dt_str = self._scene.dt.replace('-', '').replace(':', '').replace(' ', '_')[:15]
        output_file = output_path / f"{dt_str}_{product}.tif"

        cutline_path = self._bbox_to_cutline(bbox_wgs84)

        warp_options = {
            'format': 'GTiff',
            'cutlineDSName': cutline_path,
            'cropToCutline': True,
            'dstNodata': 0,
            'creationOptions': ["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"]
        }

        if resample_to is not None:
            src_ds = gdal.Open(vrt_path)
            geo = src_ds.GetGeoTransform()
            src_res = abs(geo[1])
            src_ds = None

            if resample_to == "highest":
                target_res = src_res
            elif resample_to == "lowest":
                target_res = src_res
            elif isinstance(resample_to, (int, float)):
                target_res = resample_to
            else:
                target_res = src_res

            if target_res != src_res:
                warp_options['xRes'] = target_res
                warp_options['yRes'] = target_res
                warp_options['resampleAlg'] = self._get_resample_alg(resample_method)

        print(f"Clipping by bbox and saving to {output_file.name}...")
        gdal.Warp(str(output_file), vrt_path, **warp_options)

        file_size = output_file.stat().st_size
        print(f"File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        if file_size < 10000:
            print(f"*** WARNING: file is very small ({file_size} bytes) - possibly empty ***")

        gdal.Unlink(vrt_path)
        os.unlink(cutline_path)

        return output_file.name

    def _get_resample_alg(self, method: str) -> int:
        """Get GDAL constant for resampling method."""
        method_map = {
            "nearest": gdal.GRA_NearestNeighbour,
            "bilinear": gdal.GRA_Bilinear,
            "cubic": gdal.GRA_Cubic,
            "cubicspline": gdal.GRA_CubicSpline,
            "lanczos": gdal.GRA_Lanczos,
            "average": gdal.GRA_Average,
            "mode": gdal.GRA_Mode,
            "max": gdal.GRA_Max,
            "min": gdal.GRA_Min,
            "med": gdal.GRA_Med,
            "q1": gdal.GRA_Q1,
            "q3": gdal.GRA_Q3,
        }
        return method_map.get(method, gdal.GRA_NearestNeighbour)