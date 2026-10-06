import frappe
# %%
import json


def get_shipping_cost(**kwargs):
    from_state = kwargs.get("from_state")
    to_state = kwargs.get("to_state")
    city = kwargs.get("city")
    weight = kwargs.get("weight", 0)
    invoice_value = kwargs.get("invoice_value", 0)
    shipping_partner = kwargs.get("shipping_partner", None)
    distance = kwargs.get("distance", None)

    # Assuming zonesMapping is already loaded from the JSON file
    with open("SafeExpress_zonesMapping.json", "r") as json_file:
        zonesMapping = json.load(json_file)

    # Freight Charge per KG
    surface_freight_charge = {"A": 7, "B": 8.75, "C": 11, "D": 13.5, "E": 22}
    code = zonesMapping[from_state][to_state]

    charge = surface_freight_charge[code]
    if weight:
        basic_charge = charge * weight

    # Metro Congestion Charge
    if city in [
        "Ahmedabad",
        "Bengaluru",
        "Chennai",
        "Hyderabad",
        "Kolkata",
        "Mumbai",
        "Pune",
    ]:
        charge = basic_charge + 100

    # Green Tax
    if city in ["Delhi", "Ghaziabad", "Noida"]:
        charge = charge + 100

    # Waybill Charge
    charge = charge + 100

    # Value Surcharge
    charge = charge + (invoice_value * 0.005) + 100

    # Fuel Surcharge
    charge = charge + (basic_charge * 0.25)

    return charge


# %%

x = get_shipping_cost(from_state='Karnataka', to_state="Maharashtra",city='Mumbai', shipping_partner=None, weight=34, distance=None)
print (x)
# %%
