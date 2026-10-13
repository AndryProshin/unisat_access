# gdal_resample_demo.py
"""
Demonstrate resample_to modes in GDALScene.save_products.

Uses a scene that has products with different native resolutions
(channel8_l2a -- 10 m, channel11_l2a -- 20 m).

Calls save_products:
  * resample_to=None       -- keep native (each product at its own resolution)
  * resample_to="highest"  -- both products at 10 m
  * resample_to="lowest"   -- both products at 20 m
  * s3_subdir="resample_demo" -- results go to S3 instead of local data/

After each local call, reads back the resulting GeoTIFFs and prints
their pixel size. For the S3 branch, just prints returned keys.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from osgeo import gdal

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata
from processing.gdal.scene import GDALScene


def show_resolution(directory: Path) -> None:
    """Print pixel size and raster size for every .tif in the directory."""
    tifs = sorted(directory.glob("*.tif"))
    if not tifs:
        print(f"  (no .tif files in {directory})")
        return
    for tif in tifs:
        ds = gdal.Open(str(tif))
        gt = ds.GetGeoTransform()
        print(f"  {tif.name}: pixel = {abs(gt[1]):.2f} m, "
              f"size = {ds.RasterXSize} x {ds.RasterYSize}")
        ds = None


# 1. Build query parameters
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-08-01 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "products": ["channel8_l2a", "channel11_l2a"],
    "bbox": [39, 54, 40, 55],
    "limit": 1,
    "max_cloudiness": 20
})

# 2. Load metadata, take the first scene
metadata = Metadata(params)
if len(metadata) == 0:
    print("No scenes found")
    sys.exit(1)
scene = metadata[0]
print(f"Scene: {scene.dt} | {scene.satellite} | {scene.device}")
print(f"Products: {list(scene.products.keys())}")
for product in scene.products:
    print(f"  {product}: native resolution = {scene.get_resolution(product)} m")
print()

gdal_scene = GDALScene(scene)

# 3. resample_to=None -- keep native
print("=== resample_to=None (keep native) ===")
gdal_scene.save_products(
    data_subdir="resample_demo/native",
    products=["channel8_l2a", "channel11_l2a"],
    resample_to=None,
)
show_resolution(Path("data/resample_demo/native"))
print()

# 4. resample_to="highest" -- both at 10 m
print("=== resample_to='highest' (both should be 10 m) ===")
gdal_scene.save_products(
    data_subdir="resample_demo/highest",
    products=["channel8_l2a", "channel11_l2a"],
    resample_to="highest",
    resample_method="bilinear",
)
show_resolution(Path("data/resample_demo/highest"))
print()

# 5. resample_to="lowest" -- both at 20 m
print("=== resample_to='lowest' (both should be 20 m) ===")
gdal_scene.save_products(
    data_subdir="resample_demo/lowest",
    products=["channel8_l2a", "channel11_l2a"],
    resample_to="lowest",
    resample_method="average",
)
show_resolution(Path("data/resample_demo/lowest"))
print()

# 6. s3_subdir -- results go to S3
print("=== s3_subdir='resample_demo' (results in S3) ===")
result = gdal_scene.save_products(
    s3_subdir="resample_demo",
    products=["channel8_l2a", "channel11_l2a"],
    resample_to="highest",
    resample_method="bilinear",
    qlook=True,
)
print("Returned result:")
print(f"  s3:         {result.get('s3')}")
print(f"  output_dir: {result['output_dir']}")
for product, key in result["files"].items():
    print(f"  {product}: {key}")
for product, key in result.get("qlook_files", {}).items():
    print(f"  {product} (qlook): {key}")

# Check that local data/s3/resample_demo/ is empty
local_dir = Path("data/s3/resample_demo")
if local_dir.exists():
    leftovers = list(local_dir.iterdir())
    if leftovers:
        print(f"\nWARNING: local {local_dir} still has: {[p.name for p in leftovers]}")
    else:
        print(f"\nLocal {local_dir} is empty (files uploaded and removed).")
else:
    print(f"\nLocal {local_dir} does not exist.")