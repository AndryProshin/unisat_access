"""
Демонстрация работы со спектральными индексами с реальными данными.

Требует:
- Настроенный .env с METADATA_URL и NGINX_URL
- Доступ к серверу с данными
- GDAL (Python из QGIS или установленный)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

from processing import GDALScene
from processing.indices import (
    compute_ndvi,
    compute_evi,
    compute_ndwi,
    Sentinel2Indices,
    SpectralIndex,
    IndexCalculator,
    compute_index
)

from processing.masks import get_scl_mask_for_scene, SCL_GOOD_CLASSES


def main():
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ СПЕКТРАЛЬНЫХ ИНДЕКСОВ")
    print("=" * 60)

    # 1. Параметры запроса (Рязань, август 2024)
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-01 00:00:00",
        "dt": "2024-08-15 00:00:00",
        "bbox": [39.5, 54.5, 40.0, 54.8],  # небольшой участок под Рязанью
        "products": ["channel8_l2a", "channel4_l2a", "channel3_l2a", "channel2_l2a", "s2_scl"],
        "limit": 2,
        "max_cloudiness": 50
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
    print(f"   device: {scene.device}")
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
        print(f"   Хороших пикселей: {(mask > 0).sum()} / {mask.size} ({100 * (mask > 0).sum() / mask.size:.1f}%)")
    except Exception as e:
        print(f"   SCL не найден, работаем без маски: {e}")
        mask = None

    # 5. Вычисляем NDVI
    print("\n4. Вычисление NDVI...")
    try:
        result_ndvi = compute_ndvi(scene, "demo_ndvi", mask=mask)
        print(f"   Файл: {result_ndvi['file']}")
        print(f"   Статистика:")
        print(f"     min: {result_ndvi['statistics']['min']:.3f}")
        print(f"     max: {result_ndvi['statistics']['max']:.3f}")
        print(f"     mean: {result_ndvi['statistics']['mean']:.3f}")
        print(f"     std: {result_ndvi['statistics']['std']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 6. Вычисляем EVI
    print("\n5. Вычисление EVI...")
    try:
        result_evi = compute_evi(scene, "demo_evi", mask=mask)
        print(f"   Файл: {result_evi['file']}")
        print(f"   Статистика: min={result_evi['statistics']['min']:.3f}, max={result_evi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 7. Вычисляем NDWI
    print("\n6. Вычисление NDWI...")
    try:
        result_ndwi = compute_ndwi(scene, "demo_ndwi", mask=mask)
        print(f"   Файл: {result_ndwi['file']}")
        print(f"   Статистика: min={result_ndwi['statistics']['min']:.3f}, max={result_ndwi['statistics']['max']:.3f}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 8. Пользовательский индекс (своя формула)
    print("\n7. Пользовательский индекс...")
    from processing.indices import SpectralIndex, compute_index

    my_index = SpectralIndex(
        name="MY_INDEX",
        expression="(nir - red) / (nir + red + 0.1)",  # сглаженный NDVI
        bands={"nir": "channel8_l2a", "red": "channel4_l2a"},
        scale=10000,
        output_range=(-10000, 10000)
    )

    try:
        result_my = compute_index(scene, my_index, "demo_custom", mask=mask)
        print(f"   Индекс: {result_my['index']}")
        print(f"   Формула: {result_my['expression']}")
        print(f"   Файл: {result_my['file']}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 9. Через IndexCalculator (явный контроль)
    print("\n8. Через IndexCalculator (явный контроль)...")

    from processing.indices.base import IndexCalculator
    calc = IndexCalculator(scene, offset=-1000, scale=10000)
    try:
        result = calc.compute(
            Sentinel2Indices.SAVI,
            "demo_savi",
            mask=mask,
            resample_to="highest"
        )
        print(f"   SAVI сохранён: {result['file']}")
    except Exception as e:
        print(f"   Ошибка: {e}")

    # 10. Итог
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ")
    print("=" * 60)
    print(f"Все результаты сохранены в: data/processed/")
    print(f"  - demo_ndvi/")
    print(f"  - demo_evi/")
    print(f"  - demo_ndwi/")
    print(f"  - demo_custom/")
    print(f"  - demo_savi/")
    print("\n=== Завершено ===")


if __name__ == "__main__":
    main()