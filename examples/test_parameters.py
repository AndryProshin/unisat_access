import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unisat_api.parameters import Parameters
from unisat_api.metadata import Metadata

from pprint import pprint


print("> Print available parmeters presets (collections)")
print(Parameters.list_presets())

# Create parameters with preset
print("\n> Compose custom query parmeters and show them as dict")
params = Parameters("sentinel2_boa", { 
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

#print("\n> Show specified parameter description")
# print(params.get_param_description("max_cloudiness"))  # "Maximum cloud cover (%)"

print("\n> Show all parameters description")
print(params.get_parameters_description())

# Save as new preset
print("\n> Save parameters as new preset")
params.save("my_query")

#params = Parameters("sentinel2_boa")

#print("=================")
#print(repr(params))

#metadata = Metadata(params)
#pprint(metadata.raw_json)
#exit()


