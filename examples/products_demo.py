# products_demo.py
# Демонстрация получения растровых продуктов (PNG)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api import Parameters, Metadata

# 1. Параметры поиска
params = Parameters(collection="sentinel2_boa", params={
    "dt_from": "2024-07-18 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "bbox": [39, 54, 40, 55],
    "products": ["channel8_l2a", "channel4_l2a", "s2_scl"],
    "max_cloudiness": 20
})

# 2. Загрузка метаданных
metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}\n")

if len(metadata) == 0:
    print("Нет сцен для обработки")
    sys.exit(0)

# 3. Первая сцена
scene = metadata[0]
print(f"Сцена: {scene.dt}")
print(f"Все продукты: {list(scene.products.keys())}\n")

# 4. Получить два продукта
print("=== 1. Два продукта (channel8_l2a, channel4_l2a) ===")
scene.get_products(
    products=["channel8_l2a", "channel4_l2a"],
    products_subdir="products_two",
    max_size=1024
)

# 5. Получить все продукты
print("\n=== 2. Все продукты ===")
scene.get_all_products(
    products_subdir="products_all",
    max_size=1024
)

print("\nГотово.")
print("  data/products/products_two/")
print("  data/products/products_all/")