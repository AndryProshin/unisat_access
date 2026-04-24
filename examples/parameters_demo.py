import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from pprint import pprint


print("> Print available parameters presets (collections)")
print(Parameters.list_presets())

# ------------------------------------------------------------
# 1. Пример С коллекцией (простой путь для новичков)
# ------------------------------------------------------------
print("\n> Example WITH collection (simplified)")
params = Parameters(collection="sentinel2_boa", params={ 
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 100,
    "products": ["channel8_l2a", "channel4_l2a"],
    "max_cloudiness": 80
})
print("Parameters with collection:")
pprint(params.to_dict())

# ------------------------------------------------------------
# 2. Пример БЕЗ коллекции (полный контроль, продвинутый)
# ------------------------------------------------------------
print("\n> Example WITHOUT collection (full control, advanced)")
params_no_collection = Parameters(params={
    "dt_from": "2024-08-01 00:00:00",
    "dt": "2024-08-30 00:00:00",
    "bbox": [39, 54, 40, 55],
    "satellites": ["SENTINEL-2A", "SENTINEL-2B"],
    "devices": ["MSI_BOA"],
    "stations": ["ESA"],
    "products": ["channel8_l2a", "channel4_l2a"],
    "limit": 5,
    "max_cloudiness": 30
})
print("Parameters (no collection):")
pprint(params_no_collection.to_dict())

# ------------------------------------------------------------
# 3. Дальнейшая работа с параметрами
# ------------------------------------------------------------
print("\n> Set parameter and print it")
params.set("limit", 10)
pprint(params.get("limit"))

print("\n> Print required parameters")
print(params.get_required_params())

print("\n> Show all parameters description")
print(params.get_parameters_description())

print("\n> Save parameters as new preset")
params.save("my_query")

print("\n> Load user preset 'my_query' and show parameters")
params2 = Parameters(user_preset="my_query")
print("Parameters from user preset:")
pprint(params2.to_dict())

print("\n> Override max_cloudiness and limit")
params3 = Parameters(user_preset="my_query", params={
    "max_cloudiness": 60,
    "limit": 20
})
print("Parameters after override:")
pprint(params3.to_dict())