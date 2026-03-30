from unisat_api import Parameters, Metadata, Scene

params = Parameters("sentinel2_boa", { 
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 100,
    "max_cloudiness": 80
})

metadata = Metadata(params)
print(f"Найдено сцен: {len(metadata)}\n")


