"""
Демонстрация работы с масками (класс Mask).
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from processing.masks import Mask, get_scl_mask_for_scene, SCL_GOOD_CLASSES


def save_mask_with_metadata(mask: Mask, output_path: Path, params_info: dict) -> str:
    """Сохраняет маску как GeoTIFF и PNG, а также _params.json"""
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем GeoTIFF и PNG
    png_path = mask.save(str(output_path), save_png=True)
    
    # Сохраняем _params.json
    params_file = output_dir / "_params.json"
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
    print("ДЕМОНСТРАЦИЯ РАБОТЫ С МАСКАМИ")
    print("=" * 60)

    # 1. Загрузка сцены (весна, возможна облачность)
    print("\n1. Загрузка сцены...")
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
        print("   Нет сцен для обработки")
        return
    
    scene = metadata[0]
    print(f"   Сцена: {scene.dt}")

    # 2. Создание маски из SCL
    print("\n2. Создание маски из SCL...")
    good_classes = SCL_GOOD_CLASSES['vegetation_water']
    dilate_clouds = 2
    dilate_shadows = 3
    
    try:
        mask_scl = get_scl_mask_for_scene(
            scene,
            good_classes=good_classes,
            dilate_clouds=dilate_clouds,
            dilate_shadows=dilate_shadows
        )
        print(f"   Форма маски: {mask_scl.shape}")
        good_pixels = (mask_scl > 0).sum()
        print(f"   Хороших пикселей: {good_pixels} / {mask_scl.size} ({100 * good_pixels / mask_scl.size:.1f}%)")
        
        # Сохраняем визуализацию маски как PNG (склеенная версия)
        from PIL import Image
        output_dir = Path("data/processed/mask_demo")
        output_dir.mkdir(parents=True, exist_ok=True)
        mask_vis = (mask_scl * 255).astype(np.uint8)
        vis_path = output_dir / "mask_scl_visual.png"
        Image.fromarray(mask_vis, mode='L').save(vis_path)
        print(f"   Визуализация маски (склеенная): {vis_path}")
        
    except Exception as e:
        print(f"   Ошибка: {e}")
        return

    output_dir = Path("data/processed/mask_demo")
    mask = Mask.from_array(mask_scl)
    
    # 3. Сохранение SCL маски (с PNG и JSON)
    print("\n3. Сохранение SCL маски...")
    scl_params = {
        "operation": "create_scl_mask",
        "good_classes": good_classes,
        "dilate_clouds": dilate_clouds,
        "dilate_shadows": dilate_shadows,
        "scene_dt": scene.dt,
        "scene_satellite": scene.satellite
    }
    mask_path = output_dir / "mask_scl.tif"
    png_path = save_mask_with_metadata(mask, mask_path, scl_params)
    print(f"   GeoTIFF: {mask_path}")
    print(f"   PNG: {png_path}")
    print(f"   JSON: {mask_path.parent / '_params.json'}")

    # 4. Комбинирование масок
    print("\n4. Комбинирование масок...")
    mask_all_good = Mask.all_good(mask_scl.shape)
    combined = mask_all_good & mask
    combined_path = output_dir / "mask_combined.tif"
    combined_params = {"operation": "combine_masks", "type": "all_good & scl_mask"}
    save_mask_with_metadata(combined, combined_path, combined_params)
    print(f"   GeoTIFF: {combined_path}")
    print(f"   PNG: {combined_path.with_suffix('.png')}")

    # 5. Инверсия маски
    print("\n5. Инверсия маски...")
    mask_inv = ~mask
    inv_path = output_dir / "mask_inv.tif"
    inv_params = {"operation": "invert_mask"}
    save_mask_with_metadata(mask_inv, inv_path, inv_params)
    print(f"   GeoTIFF: {inv_path}")
    print(f"   PNG: {inv_path.with_suffix('.png')}")

    # 6. Загрузка маски из файла и применение
    print("\n6. Загрузка маски из файла и применение к данным...")
    mask_loaded = Mask.from_file(str(mask_path))
    print(f"   Загружена маска из {mask_path}, форма {mask_loaded.data.shape}")
    
    # Создаём тестовые данные для демонстрации apply_to_array
    test_data = np.ones(mask_scl.shape, dtype=np.float32) * 100
    masked_data = mask_loaded.apply_to_array(test_data)
    nan_count = np.isnan(masked_data).sum()
    print(f"   Пример apply_to_array: исходные данные → после маски")
    print(f"     До: min={test_data.min()}, max={test_data.max()}")
    print(f"     После маски: min={np.nanmin(masked_data):.0f}, max={np.nanmax(masked_data):.0f}, NaN={nan_count}")

    print("\n" + "=" * 60)
    print("ГОТОВО")
    print("=" * 60)
    print(f"Результаты в: {output_dir.absolute()}")
    print("  - mask_scl.tif / .png            # маска из SCL")
    print("  - mask_scl_visual.png            # склеенная визуализация маски")
    print("  - mask_combined.tif / .png       # комбинированная маска")
    print("  - mask_inv.tif / .png            # инвертированная маска")
    print("  - _params.json                   # параметры создания масок")


if __name__ == "__main__":
    main()