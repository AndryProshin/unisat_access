"""
Минимальный пример работы с архивом через GDAL без использования processing.

Показывает, как вручную:
- Найти сцену через Parameters + Metadata
- Получить фрагменты
- Открыть файлы напрямую через GDAL по HTTP
- Прочитать данные

Этот пример не требует установки processing и показывает низкоуровневую работу.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata
from osgeo import gdal

gdal.UseExceptions()


def main():
    print("=" * 60)
    print("GDAL BARE DEMO — работа без processing")
    print("=" * 60)

    # 1. Параметры запроса
    params = Parameters(collection="sentinel2_boa", params={
        "dt_from": "2024-08-10 08:35:14",      # начало
        "dt": "2024-08-10 08:35:14",           # конец (та же дата)
        "bbox": [39.5, 54.5, 40.0, 54.8],
        "products": ["channel8_l2a", "channel4_l2a"],
        "max_cloudiness": 50
    })

    # 2. Загрузка метаданных
    print("\n1. Поиск сцены...")
    metadata = Metadata(params)
    print(f"   Найдено сцен: {len(metadata)}")

    if len(metadata) == 0:
        print("   Нет сцен для обработки")
        return

    scene = metadata[0]
    print(f"   Сцена: {scene.dt} | {scene.satellite} | {scene.device}")

    # 3. Получение фрагментов
    print("\n2. Получение фрагментов...")
    fragments = scene.get_fragments()
    print(f"   Фрагментов: {len(fragments)}")

    if not fragments:
        print("   Нет фрагментов")
        return

    # 4. Прямая работа с GDAL
    print("\n3. Открытие файлов через GDAL по HTTP...")

    for i, frag in enumerate(fragments):
        print(f"\n   Фрагмент {i}:")
        http_frag = scene.to_http(frag)

        for product_name, url in http_frag.items():
            print(f"     {product_name}: {url[:80]}...")

            # Открываем через GDAL
            ds = gdal.Open(url)
            if ds is None:
                print(f"       Ошибка: не удалось открыть")
                continue

            # Читаем метаданные
            band = ds.GetRasterBand(1)
            cols = ds.RasterXSize
            rows = ds.RasterYSize
            dtype = gdal.GetDataTypeName(band.DataType)

            # Читаем статистику (без загрузки всего массива)
            stats = band.GetStatistics(True, True)

            print(f"       Размер: {cols} x {rows}, тип: {dtype}")
            print(f"       Статистика: min={stats[0]:.0f}, max={stats[1]:.0f}, mean={stats[2]:.0f}")

            # Опционально: читаем небольшой кусочек
            if cols > 100 and rows > 100:
                small = band.ReadAsArray(0, 0, 100, 100)
                print(f"       Прочитано 100x100 пикселей, форма: {small.shape}")

            ds = None

    print("\n" + "=" * 60)
    print("Готово! Данные доступны для кастомной обработки.")
    print("=" * 60)


if __name__ == "__main__":
    main()