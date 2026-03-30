# quick_start.py
from unisat_api import Parameters, Metadata

params = Parameters("sentinel2_boa", {
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 10
})

metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}")

for scene in metadata:
    print(scene.dt, scene.satellite)