# quick_start.py
from unisat_api import Parameters, Metadata

params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "products": ["channel8_l2a", "channel4_l2a"],
    "bbox": [41, 41, 45, 45],
    "limit": 10
})

metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}\n")

scene = metadata[0]
print(f"Сцена: {scene.dt} | {scene.satellite} | {scene.device}")

fragments = scene.get_fragments()
http_frag = scene.to_http(fragments[0])

print("\nHTTP ссылки на файлы первого фрагмента:")
for product, url in http_frag.items():
    print(f"  {product}: {url}")