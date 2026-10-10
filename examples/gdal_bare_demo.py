"""
Minimal example of working with the archive via GDAL without processing.

Shows how to manually:
- Find a scene via Parameters + Metadata
- Get fragments
- Open files directly via GDAL over HTTP
- Read data

Does not require processing. Demonstrates low-level access.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from osgeo import gdal

gdal.UseExceptions()


def main():
    print("=" * 60)
    print("GDAL BARE DEMO — no processing")
    print("=" * 60)

    # 1. Query parameters
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-10 08:35:14",
        "dt": "2024-08-10 08:35:14",
        "bbox": [39.5, 54.5, 40.0, 54.8],
        "products": ["channel8_l2a", "channel4_l2a"],
        "max_cloudiness": 50
    })

    # 2. Load metadata
    print("\n1. Searching for scene...")
    metadata = Metadata(params)
    print(f"   Scenes found: {len(metadata)}")

    if len(metadata) == 0:
        print("   No scenes to process")
        return

    scene = metadata[0]
    print(f"   Scene: {scene.dt} | {scene.satellite} | {scene.device}")

    # 3. Get fragments
    print("\n2. Getting fragments...")
    fragments = scene.get_fragments()
    print(f"   Fragments: {len(fragments)}")

    if not fragments:
        print("   No fragments")
        return

    # 4. Direct GDAL work
    print("\n3. Opening files via GDAL over HTTP...")

    for i, frag in enumerate(fragments):
        print(f"\n   Fragment {i}:")
        http_frag = scene.to_http(frag)

        for product_name, url in http_frag.items():
            print(f"     {product_name}: {url[:80]}...")

            ds = gdal.Open(url)
            if ds is None:
                print(f"       Error: cannot open")
                continue

            band = ds.GetRasterBand(1)
            cols = ds.RasterXSize
            rows = ds.RasterYSize
            dtype = gdal.GetDataTypeName(band.DataType)

            stats = band.GetStatistics(True, True)

            print(f"       Size: {cols} x {rows}, type: {dtype}")
            print(f"       Stats: min={stats[0]:.0f}, max={stats[1]:.0f}, mean={stats[2]:.0f}")

            if cols > 100 and rows > 100:
                small = band.ReadAsArray(0, 0, 100, 100)
                print(f"       Read 100x100 pixels, shape: {small.shape}")

            ds = None

    print("\n" + "=" * 60)
    print("Done! Data available for custom processing.")
    print("=" * 60)


if __name__ == "__main__":
    main()