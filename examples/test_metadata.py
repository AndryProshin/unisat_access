# test.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

from pprint import pprint

# 1. Создаём параметры запроса
params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-10 00:00:00",
    "bbox": [43, 43, 45, 45],
    "limit": 2,
    "max_cloudiness": 50
})

# 2. Загружаем метаданные
metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}\n")

# 3. Работа с первой сценой
scene = metadata[1]


print("=== Атрибуты сцены ===")
print(f"dt: {scene.dt}")
print(f"satellite: {scene.satellite}")
print(f"device: {scene.device}")
print(f"station: {scene.station}")
print(f"products: {list(scene.products.keys())}\n")

# 4. Получаем фрагменты с путями
fragments = scene.get_products_info()
print(f"=== Фрагменты ({len(fragments)}) ===")
for i, frag in enumerate(fragments):
    print(f"Фрагмент {i}: {frag}")
print()

# 5. Пример преобразования в http для первого фрагмента
print("=== Первый фрагмент в формате vsicurl ===")
print(scene.to_vsicurl(fragments[0]))
print()

# 6. Цикл по фрагментам с http ссылками
print("=== Обработка фрагментов с использованием http ссылок ===")
for i, frag in enumerate(fragments):
    print(f"\nФрагмент {i}:")
    http_frag_info = scene.to_http(frag)
    for product, path in http_frag_info.items():
        print(f"  {product}: {path}")

# 7. Загрузка файлов
#scene.download("download")
scene.download("download_flat", flat=True)