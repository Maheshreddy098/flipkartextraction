# %%
## BELOW CODES ARE TO CREATE THE ZONE MAPPING JSON FILE
import pandas as pd
import json

states = pd.read_excel(
    "/Users/vanglian/My Drive/2023_2024/Shipping Cost/Shipping cost table.xlsx",
    sheet_name="State Zones",
)

zones = pd.read_excel(
    "/Users/vanglian/My Drive/2023_2024/Shipping Cost/Shipping cost table.xlsx",
    sheet_name="Zonewise Codes",
)


zonesMapping = {}
states_dict = states["State"].to_dict()
states_list = states["State"].to_list()
for index, row in states.iterrows():
    # print(index, row["State"], row["Zone Name"])
    source_state = row["State"]
    zonesMapping[source_state] = {}
    source_state_zone = row["Zone Name"]
    # print ('Source state: ',row["State"], row["Zone Name"])
    for dest_state in states_list:
        dest_state_zone = states[states['State']==dest_state]['Zone Name'].values[0]
        # print (dest_state, dest_state_zone)
        zone_code = zones[zones['EX/TO']==source_state_zone][dest_state_zone].values[0]
        zonesMapping[source_state][dest_state] = zone_code

        # zonesMapping[row["State"]][state] = zones[zones['EX/TO']==row["Zone Name"]]
        # print(zones[zones['EX/TO']==row["Zone Name"]][states[]])
        # get the zone code for the state


print(zonesMapping)
zonesMapping_json = json.dumps(zonesMapping, indent=4)

zonesx = json.loads(zonesMapping_json)
#%%
with open("SafeExpress_zonesMapping.json", "w") as json_file:
    json.dump(zonesMapping, json_file, indent=4)