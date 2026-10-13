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
from unisat_api.exceptions import StorageError

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
        data_subdir: Optional[str] = None,
        s3_subdir: Optional[str] = None,
        products: Optional[List[str]] = None,
        bbox: Optional[List[float]] = None,
        resample_to: Optional[Union[str, float]] = None,
        resample_method: str = "nearest",
        qlook: bool = False
    ) -> Dict[str, Any]:
        """
        Merge fragments per product, clip by bbox and save as GeoTIFF.

        Exactly one of data_subdir / s3_subdir must be provided.

        Args:
            data_subdir: subdirectory inside data/ (local destination)
            s3_subdir:   prefix in S3 (upload destination). Results are
                         written locally to data/s3/<s3_subdir>/ first,
                         then uploaded and removed.
            products: list of products (None -> all scene products)
            bbox: [minx, miny, maxx, maxy] in WGS84 (None -> from scene params)
            resample_to: one of:
                None        -- keep native resolution
                "highest"   -- best (min) resolution among the requested products
                "lowest"    -- worst (max) resolution among the requested products
                <number>    -- target resolution in meters
            resample_method: resampling method ("nearest", "bilinear", "cubic")
            qlook: if True, create a quicklook PNG next to GeoTIFF

        Returns:
            dict with output_dir, files and qlook_files. When s3_subdir is
            used, paths in the result are S3 keys and the flag "s3" is True.
        """
        if (data_subdir is None) == (s3_subdir is None):
            raise ValueError(
                "save_products: exactly one of data_subdir or s3_subdir must be provided"
            )

        if data_subdir is not None:
            output_path = config.DATA_DIR / data_subdir
        else:
            output_path = config.DATA_DIR / "s3" / s3_subdir
        output_path.mkdir(parents=True, exist_ok=True)

        if products is None:
            products = list(self._scene.products.keys())

        if bbox is None:
            bbox = self._scene._params.get("bbox")
            if bbox is None:
                raise ValueError("bbox is not set in scene params nor in arguments")

        resolved_resample = self._resolve_resample_to(resample_to, products)

        self._save_params_json(output_path, resolved_resample, resample_method, bbox, products)

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
                resolved_resample, resample_method
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

        qlook_files = {}
        if qlook:
            for prod in saved_files:
                qlook_path = output_path / f"{dt_str}_{prod}_qlook.png"
                if qlook_path.exists():
                    qlook_files[prod] = str(qlook_path)

        if data_subdir is not None:
            print(f"\nSaved to: {output_path}")
            return {
                "output_dir": str(output_path),
                "files": saved_files,
                "qlook_files": qlook_files,
            }

        # S3 branch: upload everything we produced, then remove local copies.
        local_files = list(saved_files.values())
        local_files.append(str(output_path / "_params.json"))
        local_files.append(str(output_path / "_metadata.txt"))
        local_files.extend(qlook_files.values())

        s3_keys = self._upload_to_s3(local_files, s3_subdir)
        self._remove_local_files(local_files)

        print(f"\nSaved to S3: {s3_subdir}/")

        return {
            "output_dir": s3_subdir,
            "files": {prod: s3_keys[str(path)] for prod, path in saved_files.items()},
            "qlook_files": {prod: s3_keys[path] for prod, path in qlook_files.items()},
            "s3": True,
        }

    def _upload_to_s3(
        self,
        local_files: List[str],
        s3_subdir: str,
    ) -> Dict[str, str]:
        """
        Upload the given files to S3, return {local_path: s3_key}.
        Raises StorageError on failure.
        """
        from s3tool import S3Tool, S3ToolError

        try:
            tool = S3Tool(raise_on_fatal=True)
        except S3ToolError as e:
            raise StorageError(f"save_products: cannot connect to S3: {e}") from None

        if not tool.upload_files(local_files, s3_subdir):
            raise StorageError(
                f"save_products: failed to upload to S3 "
                f"[{tool.get_error_code()}] {tool.get_error_message()}"
            )

        prefix = s3_subdir.rstrip("/")
        keys = {}
        for path in local_files:
            name = os.path.basename(path)
            keys[path] = f"{prefix}/{name}" if prefix else name
        return keys

    @staticmethod
    def _remove_local_files(local_files: List[str]) -> None:
        """Remove only the files we produced, ignore missing."""
        for path in local_files:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass

    def _resolve_resample_to(
        self,
        resample_to: Optional[Union[str, float]],
        products: List[str]
    ) -> Optional[float]:
        """
        Turn the user-facing resample_to into a concrete number of meters.

        - None        -> None (no resampling)
        - number      -> as is
        - "highest"   -> min resolution among requested products
        - "lowest"    -> max resolution among requested products

        If the requested mode is highest/lowest but no product resolution
        is available, falls back to None with a warning.
        """
        if resample_to is None:
            return None
        if isinstance(resample_to, (int, float)):
            return float(resample_to)
        if resample_to not in ("highest", "lowest"):
            print(f"Warning: unknown resample_to={resample_to!r}, ignoring")
            return None

        resolutions = []
        for product in products:
            res = self._scene.get_resolution(product)
            if res is not None:
                resolutions.append(res)

        if not resolutions:
            print(f"Warning: resample_to={resample_to!r} requested, "
                  f"but no product resolutions are available; "
                  f"resampling is skipped")
            return None

        target = min(resolutions) if resample_to == "highest" else max(resolutions)
        print(f"resample_to={resample_to!r} -> {target} m "
              f"(from {len(resolutions)} product resolution(s))")
        return float(target)

    def _save_params_json(
        self,
        output_path: Path,
        resample_to: Optional[float],
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
        resample_to: Optional[float],
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
            warp_options['xRes'] = resample_to
            warp_options['yRes'] = resample_to
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