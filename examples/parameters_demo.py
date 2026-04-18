import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

from pprint import pprint


print("> Print available parameters presets (collections)")
print(Parameters.list_presets())

# Create parameters with preset
print("\n> Compose custom query parameters and show them as dict")
params = Parameters(collection="sentinel2_boa", params={ 
    "dt_from": "2024-01-01 00:00:00",
    "dt": "2024-01-02 00:00:00",
    "bbox": [41, 41, 45, 45],
    "limit": 100,
    "products": ["channel8_l2a", "channel4_l2a"],
    "max_cloudiness": 80
})
# Get dictionary for archive request
pprint(params.to_dict())


print("\n> Set parameter and print it")
params.set("limit", 10)
pprint(params.get("limit"))

# Get schema info
print("\n> Print required parameters")
print(params.get_required_params())  # ['dt', 'dt_from', 'limit', 'bbox']

print("\n> Show all parameters description")
print(params.get_parameters_description())

# Save as new preset
print("\n> Save parameters as new preset")
params.save("my_query")

# Load and use user preset
print("\n> Load user preset 'my_query' and show parameters")
params2 = Parameters(user_preset="my_query")
print("Parameters from user preset:")
pprint(params2.to_dict())

# Override some parameters from user preset
print("\n> Override max_cloudiness and limit")
params3 = Parameters(user_preset="my_query", params={
    "max_cloudiness": 60,
    "limit": 20
})
print("Parameters after override:")
pprint(params3.to_dict())