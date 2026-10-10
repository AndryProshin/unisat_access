# products_demo.py
# Demo: fetching raster products (PNG)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata

# 1. Query parameters
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-07-18 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "bbox": [39, 54, 40, 55],
    "products": ["channel8_l2a", "channel4_l2a", "s2_scl", "v_color"],
    "max_cloudiness": 20
})

# 2. Load metadata
metadata = Metadata(params)
print(f"Scenes found: {len(metadata)}\n")

if len(metadata) == 0:
    print("No scenes to process")
    sys.exit(0)

# 3. First scene
scene = metadata[0]
print(f"Scene: {scene.dt}")
print(f"All products: {list(scene.products.keys())}\n")

# 4. Fetch two products
print("=== 1. Two products (channel8_l2a, v_color) ===")
scene.get_products(
    products=["channel8_l2a", "v_color"],
    products_subdir="demo",
    max_size=1024
)

# 5. Fetch all products
print("\n=== 2. All products ===")
scene.get_all_products(
    products_subdir="demo_all",
    max_size=1024
)

print("\nDone.")
print("  data/_product/demo/")
print("  data/_product/demo_all/")