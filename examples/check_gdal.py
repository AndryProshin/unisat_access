"""
Простой скрипт для проверки GDAL и получения информации о растре
"""

from osgeo import gdal, ogr, osr
import sys

print("=" * 50)
print("Проверка GDAL")
print("=" * 50)

# 1. Версия GDAL
print(f"\n1. GDAL версия: {gdal.__version__}")

# 2. Доступные драйверы (первые 10)
print("\n2. Доступные растровые драйверы:")
drivers_count = gdal.GetDriverCount()
for i in range(min(10, drivers_count)):
    driver = gdal.GetDriver(i)
    print(f"   - {driver.ShortName}: {driver.LongName}")

# 3. Проверка OGR (векторные данные)
print(f"\n3. OGR доступен: {ogr is not None}")
print(f"   Доступно векторных драйверов: {ogr.GetDriverCount()}")

# 4. Проверка OSR (системы координат)
print(f"\n4. OSR (пространственные привязки): доступен")

# 5. Если есть файл растра — показать информацию
raster_file = "test.tif"  # замени на свой файл
if len(sys.argv) > 1:
    raster_file = sys.argv[1]

import os
if os.path.exists(raster_file):
    print(f"\n5. Анализ файла: {raster_file}")
    ds = gdal.Open(raster_file)
    if ds:
        print(f"   - Размер: {ds.RasterXSize} x {ds.RasterYSize} пикселей")
        print(f"   - Количество каналов: {ds.RasterCount}")
        proj = ds.GetProjection()
        if proj:
            print(f"   - Проекция: {proj[:80]}...")
        else:
            print("   - Проекция: не задана")
        ds = None
    else:
        print(f"\n5. Не удалось открыть {raster_file}")
else:
    print(f"\n5. Файл {raster_file} не найден — пропускаем")

print("\n" + "=" * 50)
print("✅ GDAL готов к работе!")