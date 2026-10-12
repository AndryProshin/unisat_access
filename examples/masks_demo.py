# masks_demo.py
"""
Demo: working with masks (Mask class).
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from processing.masks import Mask, get_scl_mask_for_scene, SCL_GOOD_CLASSES


def save_mask_with_metadata(mask: Mask, data_path: str, params_info: dict) -> str:
    """Save mask as GeoTIFF and PNG, plus _params.json."""
    png_path = mask.save(data_path=data_path, save_png=True)

    # _params.json is written next to the .tif under data/
    params_file = Path(png_path).parent / "_params.json"
    if not params_file.exists():
        params_data = {
            "mask_creation": params_info,
            "timestamp": datetime.now().isoformat(),
            "package_version": "1.0.0"
        }
        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump(params_data, f, indent=2, ensure_ascii=False)

    return png_path


def main():
    print("=" * 60)
    print("MASKS DEMO")
    print("=" * 60)

    # 1. Load scene
    print("\n1. Loading scene...")
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-20 00:00:00",
        "dt": "2024-08-30 00:00:00",
        "bbox": [39, 54.5, 40, 55.5],
        "products": ["channel8_l2a", "s2_scl"],
        "limit": 5,
        "max_cloudiness": 80
    })

    metadata = Metadata(params)

    if len(metadata) == 0:
        print("   No scenes to process")
        return

    scene = metadata[0]
    print(f"   Scene: {scene.dt}")

    # 2. Build mask from SCL
    print("\n2. Building mask from SCL...")
    good_classes = SCL_GOOD_CLASSES['vegetation_water']
    dilate_clouds = 2
    dilate_shadows = 3

    try:
        mask_scl = get_scl_mask_for_scene(
            scene,
            data_subdir="mask_demo",
            good_classes=good_classes,
            dilate_clouds=dilate_clouds,
            dilate_shadows=dilate_shadows
        )
        print(f"   Mask shape: {mask_scl.shape}")
        good_pixels = (mask_scl > 0).sum()
        print(f"   Good pixels: {good_pixels} / {mask_scl.size} ({100 * good_pixels / mask_scl.size:.1f}%)")

        from PIL import Image
        output_dir = Path("data/mask_demo")
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_vis = (mask_scl * 255).astype(np.uint8)
        vis_path = output_dir / "mask_scl_visual.png"
        Image.fromarray(mask_vis, mode='L').save(vis_path)
        print(f"   Mask visualization: {vis_path}")

    except Exception as e:
        print(f"   Error: {e}")
        return

    mask = Mask.from_array(mask_scl)

    # 3. Save SCL mask (locally)
    print("\n3. Saving SCL mask locally...")
    scl_params = {
        "operation": "create_scl_mask",
        "good_classes": good_classes,
        "dilate_clouds": dilate_clouds,
        "dilate_shadows": dilate_shadows,
        "scene_dt": scene.dt,
        "scene_satellite": scene.satellite
    }
    scl_data_path = "mask_demo/mask_scl"
    png_path = save_mask_with_metadata(mask, scl_data_path, scl_params)
    print(f"   GeoTIFF: data/{scl_data_path}.tif")
    print(f"   PNG: {png_path}")
    print(f"   JSON: data/{scl_data_path.rsplit('/', 1)[0]}/_params.json")

    # 3b. Save SCL mask to S3
    print("\n3b. Saving SCL mask to S3...")
    try:
        s3_tif_key = "mask_demo/mask_scl"
        s3_png_key = mask.save(
            s3_path=s3_tif_key,
            save_png=True,
        )
        print(f"   S3 GeoTIFF key: {s3_tif_key}.tif")
        print(f"   S3 PNG key: {s3_png_key}")
    except Exception as e:
        print(f"   S3 save failed: {e}")

    # 4. Combine masks
    print("\n4. Combining masks...")
    mask_all_good = Mask.all_good(mask_scl.shape)
    combined = mask_all_good & mask
    combined_data_path = "mask_demo/mask_combined"
    combined_params = {"operation": "combine_masks", "type": "all_good & scl_mask"}
    save_mask_with_metadata(combined, combined_data_path, combined_params)
    print(f"   GeoTIFF: data/{combined_data_path}.tif")
    print(f"   PNG: data/{combined_data_path}.png")

    # 5. Invert mask
    print("\n5. Inverting mask...")
    mask_inv = ~mask
    inv_data_path = "mask_demo/mask_inv"
    inv_params = {"operation": "invert_mask"}
    save_mask_with_metadata(mask_inv, inv_data_path, inv_params)
    print(f"   GeoTIFF: data/{inv_data_path}.tif")
    print(f"   PNG: data/{inv_data_path}.png")

    # 6. Load mask from file and apply
    print("\n6. Loading mask from file and applying...")
    mask_file = Path("data") / (scl_data_path + ".tif")
    mask_loaded = Mask.from_file(str(mask_file))
    print(f"   Loaded mask from {mask_file}, shape {mask_loaded.data.shape}")

    test_data = np.ones(mask_scl.shape, dtype=np.float32) * 100
    masked_data = mask_loaded.apply_to_array(test_data)
    nan_count = np.isnan(masked_data).sum()
    print(f"   apply_to_array example:")
    print(f"     Before: min={test_data.min()}, max={test_data.max()}")
    print(f"     After mask: min={np.nanmin(masked_data):.0f}, max={np.nanmax(masked_data):.0f}, NaN={nan_count}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print("Results:")
    print("  data/mask_demo/mask_scl.tif / .png")
    print("  data/mask_demo/mask_scl_visual.png")
    print("  data/mask_demo/mask_combined.tif / .png")
    print("  data/mask_demo/mask_inv.tif / .png")
    print("  data/mask_demo/_params.json")


if __name__ == "__main__":
    main()