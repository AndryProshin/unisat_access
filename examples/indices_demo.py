"""
Демонстрация работы со спектральными индексами с реальными данными.

Требует:
- Настроенный .env с METADATA_URL и NGINX_URL
- Доступ к серверу с данными
- GDAL (Python из QGIS или установленный)

Демонстрирует:
- NDVI и EVI (два разных предустановленных индекса)
- Пользовательский индекс
- Опциональное создание PNG-превью (рядом с GeoTIFF)
- Маску облачности из SCL
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from processing.indices import compute_ndvi, compute_evi, SpectralIndex, compute_index
from processing.masks import get_scl_mask_for_scene, SCL_GOOD_CLASSES


def main():
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ СПЕКТРАЛЬНЫХ ИНДЕКСОВ")
    print("=" * 60)

    # 1. Параметры запроса (Рязань, август 2024)
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-01 00:00:00",
        "dt": "2024-08-30 00:00:00",
        "bbox": [39.5, 54.5, 40.0, 54.8],
        "products": ["channel8_l2a", "channel4_l2a", "channel3_l2a", "channel2_l2a", "s2_scl"],
        "limit": 2,
        "max_cloudiness": 20
    })

    # 2. Загрузка метаданных
    print("\n1. Загрузка метаданных...")
    metadata = Metadata(params)
    print(f"   Найдено сцен: {len(metadata)}")

    if len(metadata) == 0:
        print("   Нет сцен для обработки")
        return

    # 3. Берём первую сцену
    scene = metadata[0]
    print(f"\n2. Сцена для обработки:")
    print(f"   dt: {scene.dt}")
    print(f"   satellite: {scene.satellite}")
    print(f"   Доступные продукты: {list(scene.products.keys())}")

    # 4. Создаём маску облачности из SCL
    print("\n3. Создание маски облачности...")
    try:
        mask = get_scl_mask_for_scene(
            scene,
            good_classes=SCL_GOOD_CLASSES['vegetation_water'],
            dilate_clouds=2,
            dilate_shadows=3
        )
        print(f"   Маска создана, форма: {mask.shape}")
        good_pixels = (mask > 0).sum()
        print(f"   Хороших пикселей: {good_pixels} / {mask.size} ({100 * good_pixels / mask.size:.1f}%)")
    except Exception as e:
        print(f"   SCL не найден, работаем без маски: {e}")
        mask = None

    # 5. NDVI (с PNG-превью)
    print("\n4. Вычисление NDVI...")
    try:
        result_ndvi = compute_ndvi(scene, "demo_ndvi", mask=mask, save_png=True)
        print(f"   GeoTIFF: {result_ndvi['file']}")
        print(f"   PNG (превью): {result_ndvi.get('png_file', 'не создан')}")
        print(f"   Статистика: min={result_ndvi['statistics']['min']:.3f}, max={result_ndvi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 6. EVI (без PNG)
    print("\n5. Вычисление EVI...")
    try:
        result_evi = compute_evi(scene, "demo_evi", mask=mask)
        print(f"   GeoTIFF: {result_evi['file']}")
        print(f"   Статистика: min={result_evi['statistics']['min']:.3f}, max={result_evi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 7. Пользовательский индекс (с PNG-превью)
    print("\n6. Пользовательский индекс...")
    my_index = SpectralIndex(
        name="SMOOTH_NDVI",
        expression="(nir - red) / (nir + red + 0.1)",
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    try:
        result_custom = compute_index(scene, my_index, "demo_custom", mask=mask, save_png=True)
        print(f"   GeoTIFF: {result_custom['file']}")
        print(f"   PNG (превью): {result_custom.get('png_file', 'не создан')}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 8. Итог
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print("  data/processed/demo_ndvi/     # NDVI (GeoTIFF + PNG превью)")
    print("  data/processed/demo_evi/      # EVI (GeoTIFF)")
    print("  data/processed/demo_custom/   # Пользовательский индекс (GeoTIFF + PNG)")
    print("\n=== Завершено ===")


if __name__ == "__main__":
    main()