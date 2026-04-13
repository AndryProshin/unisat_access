"""
Пример использования GDALScene для обработки сцен Sentinel-2
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata
from unisat_api.extras.gdal_scene import GDALScene

def main():
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-20 00:00:00",
        "dt": "2024-09-01 00:00:00",
        "bbox": [39, 54, 40, 55],  # Рязань
        "products": ["channel8_l2a", "channel4_l2a"],
        "limit": 2,
        "max_cloudiness": 50
    })

    print("Загрузка метаданных...")
    metadata = Metadata(params)
    print(f"Найдено сцен: {len(metadata)}\n")

    # Имя поддиректории (будет создана внутри data/processed/)
    result_subdir = "ryazan_test"

    for idx, scene in enumerate(metadata):
        print(f"--- Обработка сцены {idx + 1} ---")
        print(f"dt: {scene.dt}")
        
        gdal_scene = GDALScene(scene)
        result = gdal_scene.save_products(
            result_subdir=result_subdir,
            resample_to="highest",
            resample_method="bilinear"
        )
        
        print(f"Сохранено файлов: {len(result['files'])}")
        for product, filepath in result['files'].items():
            print(f"  {product}: {filepath}")
        print()

    print(f"Готово! Все файлы в: data/processed/{result_subdir}")


if __name__ == "__main__":
    main()