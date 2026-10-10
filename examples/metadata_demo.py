# metadata_demo.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

# 1. Build query parameters
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-08-01 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "products": ["channel8_l2a", "channel4_l2a", "s2_scl"],
    "bbox": [39, 54, 40, 55],
    "limit": 2,
    "max_cloudiness": 20
})

# 2. Load metadata
metadata = Metadata(params)
print(f"Scenes found: {len(metadata)}\n")

# 3. Work with the first scene
scene = metadata[0]

print("=== Scene attributes ===")
print(f"dt: {scene.dt}")
print(f"satellite: {scene.satellite}")
print(f"device: {scene.device}")
print(f"station: {scene.station}")
print(f"products: {list(scene.products.keys())}\n")

# 4. Get fragments with paths
fragments = scene.get_fragments()

print(f"=== Fragments ({len(fragments)}) ===")
for i, frag in enumerate(fragments):
    print(f"Fragment {i}: {frag}")
print()

# 5. Example: first fragment as vsicurl
print("=== First fragment as vsicurl ===")
print(scene.to_vsicurl(fragments[0]))
print()

# 6. Iterate fragments with http links
print("=== Fragments with http links ===")
for i, frag in enumerate(fragments):
    print(f"\nFragment {i}:")
    http_frag_info = scene.to_http(frag)
    for product, path in http_frag_info.items():
        print(f"  {product}: {path}")

# 7. Download files
result = scene.download(download_subdir="demo", flat=True)
print(f"\nDownload result:")
print(f"  Directory: {result['download_dir']}")
print(f"  Files: {len(result['files'])}")
print(f"  Params: {result['params_file']}")
print(f"  Log: {result['metadata_file']}")