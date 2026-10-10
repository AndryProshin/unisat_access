# indices_demo.py
"""
Demo: spectral indices with real data.

Requires:
- .env with METADATA_URL and NGINX_URL
- Access to data server
- GDAL

Demonstrates:
- NDVI and EVI (two preset indices)
- User-defined index
- Optional PNG preview
- Cloud mask from SCL
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from processing.indices import compute_ndvi, compute_evi, SpectralIndex, compute_index
from processing.masks import get_scl_mask_for_scene, SCL_GOOD_CLASSES


def main():
    print("=" * 60)
    print("SPECTRAL INDICES DEMO")
    print("=" * 60)

    # 1. Query parameters (Ryazan, August 2024)
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-01 00:00:00",
        "dt": "2024-08-30 00:00:00",
        "bbox": [39.5, 54.5, 40.0, 54.8],
        "products": ["channel8_l2a", "channel4_l2a", "channel3_l2a", "channel2_l2a", "s2_scl"],
        "limit": 2,
        "max_cloudiness": 20
    })

    # 2. Load metadata
    print("\n1. Loading metadata...")
    metadata = Metadata(params)
    print(f"   Scenes found: {len(metadata)}")

    if len(metadata) == 0:
        print("   No scenes to process")
        return

    # 3. First scene
    scene = metadata[0]
    print(f"\n2. Scene:")
    print(f"   dt: {scene.dt}")
    print(f"   satellite: {scene.satellite}")
    print(f"   products: {list(scene.products.keys())}")

    # 4. Build cloud mask from SCL
    print("\n3. Building cloud mask...")
    try:
        mask = get_scl_mask_for_scene(
            scene,
            data_subdir="indices_demo",
            good_classes=SCL_GOOD_CLASSES['vegetation_water'],
            dilate_clouds=2,
            dilate_shadows=3
        )
        print(f"   Mask shape: {mask.shape}")
        good_pixels = (mask > 0).sum()
        print(f"   Good pixels: {good_pixels} / {mask.size} ({100 * good_pixels / mask.size:.1f}%)")
    except Exception as e:
        print(f"   SCL not found, proceeding without mask: {e}")
        mask = None

    # 5. NDVI (with PNG preview)
    print("\n4. Computing NDVI...")
    try:
        result_ndvi = compute_ndvi(
            scene, "indices_demo",
            mask=mask,
            save_png=True,
            keep_tmp=True
        )
        print(f"   GeoTIFF: {result_ndvi['file']}")
        print(f"   PNG: {result_ndvi.get('png_file', 'not created')}")
        print(f"   Stats: min={result_ndvi['statistics']['min']:.3f}, max={result_ndvi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Error: {e}")

    # 6. EVI
    print("\n5. Computing EVI...")
    try:
        result_evi = compute_evi(
            scene, "indices_demo",
            mask=mask,
            keep_tmp=True
        )
        print(f"   GeoTIFF: {result_evi['file']}")
        print(f"   Stats: min={result_evi['statistics']['min']:.3f}, max={result_evi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Error: {e}")

    # 7. User-defined index
    print("\n6. User-defined index...")
    my_index = SpectralIndex(
        name="SMOOTH_NDVI",
        expression="(nir - red) / (nir + red + 0.1)",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    try:
        result_custom = compute_index(
            scene, my_index, "indices_demo",
            mask=mask,
            save_png=True,
            keep_tmp=True
        )
        print(f"   GeoTIFF: {result_custom['file']}")
        print(f"   PNG: {result_custom.get('png_file', 'not created')}")
    except Exception as e:
        print(f"   Error: {e}")

    # 8. Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print("  data/indices_demo/    # NDVI, EVI, SMOOTH_NDVI (GeoTIFF + PNG)")
    print("  data/indices_demo/_tmp/   # temporary files (kept for illustration)")
    print("\n=== Done ===")


if __name__ == "__main__":
    main()