#%%
# Service layer
#13128
#21182
import requests
import json
import pandas as pd
import numpy as np
from rectpack import newPacker
import rectpack.packer as packer
import rectpack.maxrects as maxrects
import rectpack.skyline as skyline
import rectpack.guillotine as guillotine
from rectpack import newPacker
from rectpack.packer import newPacker, PackingMode, PackingBin
import random

maxPalletHeight = 160
maxPermissibleWeight = 660.0


b1_url = "https://103.69.202.3:50000/b1s/v1/"
reqUrl = b1_url + "Login"
b1_session = requests.Session()
sales_order = b1_url + "Orders(23413)"


headersList = {
                "Accept": "*/*",
                "Content-Type": "application/json" 
            }

manager_data_TestDB = {"CompanyDB": "KFL_TEST","Password": "F@3ac8#b","UserName": "manager"}
# manager_data_TestDB = {"CompanyDB": "KFL_LIVE","Password": "F@3ac8#b","UserName": "manager"}
payload = json.dumps(manager_data_TestDB)

response = b1_session.request("POST", reqUrl, data=payload,  headers=headersList,verify=False)


res = response.json()
#res
# res['SessionId']
# headersList['Cookie'] = 'B1SESSION=' + str(res['SessionId']) + ';'
b1_session.cookies.set("B1SESSION", str(res['SessionId']))

#Retrieve all or some selected properties from an instance of 'Orders' with the given id.
# GET https://localhost:50000/b1s/v1/Orders(123) # id is the DocID

# so_url = b1_url + "Orders?$select=DocEntry,DocNum,DocType&$filter=DocEntry ge 123 &$orderby=DocEntry&$top=10&$skip=1"
#https://localhost:50000/b1s/v1/Orders?$select=DocEntry,DocNum,DocType&$filter=DocEntry ge 1 &$orderby=DocEntry&$top=10&$skip=1

# single_sales_order = b1_session.get (url=so_url)


# single_sales_order.json()
# %%
#sales_order = b1_url + "Orders(21182)"
single_sales_order = b1_session.get(url=sales_order)
sales_order_json = single_sales_order.json()
if (sales_order_json["U_MOS"] == "Sea"):
    maxPalletHeight = 160
elif (sales_order_json["U_MOS"]=="Air"):
    maxPalletHeight = 150

#%%
# FOR UPDATING THE BOX LAYOUT

sales_order_update = {}
sales_order_update["DocumentLines"] = [{"LineNum": line["LineNum"], "U_BoxNo": line["U_BoxNo"]} for line in sales_order_json["DocumentLines"]]
box_start = 1
for i, line in enumerate(sales_order_json["DocumentLines"]):
    box_end = box_start + int(line["U_NOB"]) - 1
    sales_order_update["DocumentLines"][i]["U_BoxNo"] = "{} TO {}".format(box_start, box_end)
    box_start = box_end + 1

# b1_session.patch(url=sales_order, data=json.dumps(sales_order_update))
# %%
# Box_list format ['LineNo','Box Dimension (LXBXH cm)','No of Box']
Box_list = []
#From Document Lines Get the FG Code, Use /Items API and get SalesUnitWeight
for line in sales_order_json["DocumentLines"]:
    itemDetails = b1_session.get(url=b1_url+"Items('"+line['ItemCode']+"')")
    itemDetails_json = itemDetails.json()
    Box_list.append([line["LineNum"], line["U_BD"], line["U_NOB"], itemDetails_json['SalesUnitWeight']])

#Box_list.extend([[line["LineNum"], line["U_BD"], line["U_NOB"]] for line in sales_order_json["DocumentLines"]])
Box_list



# %%
result = []

for sublist in Box_list:
    dimensions_str = sublist[1].split(' x ')
    dimensions = [float(dimension) for dimension in dimensions_str]  # Change int to float
    dimensions.append(sublist[3])
    count = int(sublist[2])
    result.append(dimensions + [count])

# Group the data by the first three dimensions
grouped_data = {}
for item in result:
    key = tuple(item[:4])
    if key in grouped_data:
        grouped_data[key] += item[4]
    else:
        grouped_data[key] = item[4]

# Convert the grouped data back to the list format
small_boxes = [[int(dim) if dim.is_integer() else dim for dim in key] + [value] for key, value in grouped_data.items()]

print(small_boxes)


# %%
def Layer(rectangles):
    bins = [(84, 124)]

    packer = newPacker(mode=PackingMode.Offline, bin_algo=PackingBin.Global,pack_algo=maxrects.MaxRectsBl, rotation=True)

    # Add the rectangles to packing queue
    for r in rectangles:
        packer.add_rect(*r)

    # Add the bins where the rectangles will be placed
    for b in bins:
        packer.add_bin(*b)

    # Start packing
    packer.pack()


    output1 = []
    for index, abin in enumerate(packer):
      bw, bh  = abin.width, abin.height
      #print('Area', bw, bh, "no. of rectangles in layer", len(abin))
      for rect in abin:
        x, y, l, b = rect.x, rect.y, rect.width, rect.height
        output1.append([x,y,l,b])
        print('rectangle', l,b)

    bins = [(124, 84)]

    packer = newPacker(mode=PackingMode.Offline, bin_algo=PackingBin.Global,pack_algo=maxrects.MaxRectsBl, rotation=True)

    # Add the rectangles to packing queue
    for r in rectangles:
        packer.add_rect(*r)

    # Add the bins where the rectangles will be placed
    for b in bins:
        packer.add_bin(*b)

    # Start packing
    packer.pack()


    output2 = []
    for index, abin in enumerate(packer):
      bw, bh  = abin.width, abin.height
      #print('Area', bw, bh, "no. of rectangles in layer", len(abin))
      for rect in abin:
        x, y, l, b = rect.x, rect.y, rect.width, rect.height
        output2.append([x,y,l,b])
        print('rectangle', l,b)
    
    print(len(output1))
    print(len(output2))
    if(len(output1)>len(output2)):
        return output1
    else:
        return output2 


Result = []


for box in small_boxes:
    length, width, height, weight, quantity = box
    box_dict = {
        'Length': length,
        'Width': width,
        'Height': height,
        'Weight':weight,
        'Total_Qty': quantity,
        'Layer_Capacity': None,  # Initialize with None, to be updated later
        'Layer_Weight':None,
        'Height_Capacity':None,
        'Layer':None,
        'Qty_Layer':None,
        'Residue_Qty':None,
        'Solo_Pallet':None,
        'Layer_Left':None,
        'Pallet_Capacity':None,

    }

    #! layer Capacity
    boxSurface = (box_dict['Length'], box_dict['Width'])
    layer = Layer([boxSurface]*500)
    # Update 'Layer_Capacity' in the current box dictionary
    box_dict['Layer_Capacity'] = len(layer)

    box_dict['Layer_Weight'] = box_dict['Layer_Capacity']*box_dict['Weight']


    #! Height Capacity 
    box_dict['Height_Capacity']=int(maxPalletHeight/box_dict['Height'])

    if (box_dict['Height_Capacity'] > int(maxPermissibleWeight/box_dict['Layer_Weight'])):
        box_dict['Height_Capacity'] = int(maxPermissibleWeight/box_dict['Layer_Weight'])

    #!Layers = Qty/layer Capacity
    box_dict['Layer']=int(box_dict['Total_Qty']/box_dict['Layer_Capacity'])

    #!Qty consumed in Layers = Layers * layer Capacity
    box_dict['Qty_Layer']=int(box_dict['Layer']*box_dict['Layer_Capacity'])
        #     box.append(box[6]*box[4])

    #!Residue Qty = SAP Qty - Qty Consumned in Layers 
    box_dict['Residue_Qty']=int(box_dict['Total_Qty']-box_dict['Qty_Layer'])


    #!Solo Pallets Count 
    box_dict['Solo_Pallet']=int(box_dict['Layer']/box_dict['Height_Capacity'])

    #!Layer Left
    box_dict['Layer_Left']=int(box_dict['Layer']-(box_dict['Solo_Pallet']*box_dict['Height_Capacity']))

    #!Layer Left
    box_dict['Pallet_Capacity']=int(box_dict['Height_Capacity']*box_dict['Layer_Capacity'])



    # Append the updated box dictionary to Result
    Result.append(box_dict)

print(Result)

# %%
def sort_boxes_by_area(box_list):
    # Calculate the area for each box and add it as a new key 'Area'
    for box in box_list:
        box['Area'] = box['Length'] * box['Width']

    # Sort the list based on the 'Area' key in descending order
    sorted_boxes = sorted(box_list, key=lambda x: x['Area'], reverse=True)

    # Remove the temporary 'Area' key before returning the result
    for box in sorted_boxes:
        del box['Area']

    return sorted_boxes
Sorted_Result=sort_boxes_by_area(Result)


print(Sorted_Result)

# %%
pallets = {}

# Distribute the solo pallets into the pallets
pallet_counter = 1  # Initialize the counter for pallet items

for item in Sorted_Result:
    total_solo_pallets = item['Solo_Pallet']
    total_capacity = item['Layer_Capacity'] * item['Height_Capacity']
    
    for _ in range(total_solo_pallets):
        pallets[pallet_counter] = {
            'total': total_capacity,
            'contains': {
                f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})": {
                    'total': total_capacity
                }
            }
        }
        pallet_counter += 1  # Increment the counter for the next pallet item


        
remainingHeight = maxPalletHeight
remainingWeight = maxPermissibleWeight

for item in Sorted_Result:
    for i in range(item['Layer_Left']):
        if item['Height'] <= remainingHeight and item['Layer_Weight'] <= remainingWeight:
            
            #add number of boxes in a layer(Layer_capacity) to current pallet
            if pallet_counter not in pallets:
                pallets[pallet_counter] = {
                    'total': item['Layer_Capacity'], 
                    'contains':{
                        f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})": 
                        {
                            'total': item['Layer_Capacity']
                        }
                    }
                }
            elif f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})" not in pallets[pallet_counter]['contains']:
                pallets[pallet_counter]['total'] = pallets[pallet_counter]['total'] + item['Layer_Capacity']
                pallets[pallet_counter]['contains'][f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})"] = {
                    'total': item['Layer_Capacity']
                }
            else: 
                pallets[pallet_counter]['total'] = pallets[pallet_counter]['total'] + item['Layer_Capacity']
                pallets[pallet_counter]['contains'][f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})"]['total'] = pallets[pallet_counter]['contains'][f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})"]['total'] + item['Layer_Capacity']
            
            remainingHeight = remainingHeight - item['Height']
            remainingWeight = remainingWeight - item['Layer_Weight']
        else:
            #create new pallet and add boxes in a layer to the new pallet
            pallet_counter+=1
            remainingHeight = maxPalletHeight - item['Height']
            remainingWeight = remainingWeight - item['Layer_Weight']
            pallets[pallet_counter] = {
                    'total': item['Layer_Capacity'], 
                    'contains':{
                        f"({item['Length']} x {item['Width']} x {item['Height']} x {item['Weight']})": 
                        {
                            'total': item['Layer_Capacity']
                        }
                    }
                }

print(pallets)

# %%
residueBoxes = [
    (item['Length'], item['Width'], item['Height'], item['Weight']) 
    for item in Sorted_Result 
    for _ in range(item['Residue_Qty'])
]

# %%
while len(residueBoxes)>0:
    extracted_surfaceDimensions = [(box[0], box[1]) for box in residueBoxes]
    output = Layer(extracted_surfaceDimensions)
    layerHeight = 0 
    layerWeight = 0 
    
    # Loop through each item in output
    for i, item in enumerate(output):  # Using slicing to allow removal of items during iteration
        print(item)
        for box in residueBoxes[:]:  # Using slicing to allow removal of items during iteration
            if box[0] == item[2] and box[1] == item[3]:
                layerWeight = layerWeight + box[3]
                output[i].append(box[2])
                output[i].append(box[3])
                residueBoxes.remove(box)
                if layerHeight < box[2]:
                    layerHeight = box[2]
                
                break  # Break out of the inner loop once a match is found
            elif box[0] == item[3] and box[1] == item[2]:
                layerWeight = layerWeight + box[3]
                output[i].append(box[2])
                output[i].append(box[3])
                temp = item[2]
                item[2] = item[3]
                item[3] = temp
                residueBoxes.remove(box)
                if layerHeight < box[2]:
                    layerHeight = box[2]
                
                break  # Break out of the inner loop once a match is found


    if layerHeight > remainingHeight or layerWeight > remainingWeight:
        remainingHeight = maxPalletHeight
        remainingWeight = maxPermissibleWeight
        pallet_counter += 1
        
        #create new bin
        for item in output:
            print(item)
            if pallet_counter not in pallets:
                pallets[pallet_counter] = {
                    'total': 1, 
                    'contains':{
                        f"({item[2]} x {item[3]} x {item[4]} x {item[5]})": 
                        {
                            'total': 1
                        }
                    }
                }
            elif f"({item[2]} x {item[3]} x {item[4]} x {item[5]})" not in pallets[pallet_counter]['contains']:
                pallets[pallet_counter]['total'] += 1
                pallets[pallet_counter]['contains'][f"({item[2]} x {item[3]} x {item[4]} x {item[5]})"] = {
                    'total': 1
                }
            else: 
                pallets[pallet_counter]['total']+= 1
                pallets[pallet_counter]['contains'][f"({item[2]} x {item[3]} x {item[4]} x {item[5]})"]['total'] += 1
            
        
    else:
        #add to current bin
        remainingHeight = remainingHeight - layerHeight
        remainingWeight = remainingWeight - layerWeight
        for item in output:
            print(item)
            if pallet_counter not in pallets:
                pallets[pallet_counter] = {
                    'total': 1, 
                    'contains':{
                        f"({item[2]} x {item[3]} x {item[4]} x {item[5]})": 
                        {
                            'total': 1
                        }
                    }
                }
            elif f"({item[2]} x {item[3]} x {item[4]} x {item[5]})" not in pallets[pallet_counter]['contains']:
                pallets[pallet_counter]['total'] += 1
                pallets[pallet_counter]['contains'][f"({item[2]} x {item[3]} x {item[4]} x {item[5]})"] = {
                    'total': 1
                }
            else: 
                pallets[pallet_counter]['total']+= 1
                pallets[pallet_counter]['contains'][f"({item[2]} x {item[3]} x {item[4]} x {item[5]})"]['total'] += 1
                    


print(pallets)

# %%
qty = []

for item in sales_order_json["DocumentLines"]:
    dimensions = item['U_BD']
    quantity = item['U_NOB']
    description = item['ItemDescription']
    code = item['ItemCode']
    itemDetails = b1_session.get(url=b1_url+"Items('"+item['ItemCode']+"')")
    itemDetails_json = itemDetails.json()
    # weight=itemDetails_json['SalesUnitWeight']
    
    extracted_obj = {
        'Dimensions': dimensions,
        'Quantity': quantity,
        'ItemDescription': description,
        'ItemCode': code,
        'ItemWeight':itemDetails_json['SalesUnitWeight']
    }
    
    qty.append(extracted_obj)

print(qty)




# %%


# pallets = {}

for pallet in pallets:
    
    for item in pallets[pallet]['contains']:
        pallets[pallet]['contains'][item]['contains'] = {}

for pallet in pallets:
    
    for item in pallets[pallet]['contains']:
        totalDimensionQty = pallets[pallet]['contains'][item]['total']
        for FG in qty:
            # print(item.replace("(", '').replace(")", ''))
            # print(f"{FG['Dimensions']} x {FG['ItemWeight']}")
            if item.replace("(", '').replace(")", '') == f"{FG['Dimensions']} x {FG['ItemWeight']}":
                # print('if')
                if totalDimensionQty >= int(FG['Quantity']) and totalDimensionQty != 0 :
                    totalDimensionQty = totalDimensionQty - int(FG['Quantity'])
                    if FG['ItemCode'] in pallets[pallet]['contains'][item]['contains']:
                        pallets[pallet]['contains'][item]['contains'][FG['ItemCode']]["Quantity"] += int(FG['Quantity']) 
                    else:
                        pallets[pallet]['contains'][item]['contains'][FG['ItemCode']] = {
                            'Quantity': int(FG['Quantity']) ,
                            'Description': FG['ItemDescription']
                        }
                    FG['Quantity'] = 0
                elif int(FG['Quantity'])!=0:
                    FG['Quantity'] = int(FG['Quantity']) - totalDimensionQty
                    if FG['ItemCode'] in pallets[pallet]['contains'][item]['contains']:
                        pallets[pallet]['contains'][item]['contains'][FG['ItemCode']]["Quantity"] += totalDimensionQty 
                    else:
                        pallets[pallet]['contains'][item]['contains'][FG['ItemCode']] = {
                            'Quantity': totalDimensionQty ,
                            'Description': FG['ItemDescription']
                        }
                    totalDimensionQty = 0 
                    break

print(pallets)

# %%
report = ""
for pallet_number, pallet_details in pallets.items():
    report += f"Pallet {pallet_number} : {pallet_details['total']} boxes ("
    # Initialize a dictionary to store quantities for different product descriptions
    product_quantities = {}

    for box_size, box_details in pallet_details['contains'].items():
        for product_code, product_info in box_details['contains'].items():
            description = product_info['Description']
            if description not in product_quantities:
                product_quantities[description] = 0
            product_quantities[description] += product_info['Quantity']

    # Filter out products with quantity zero
    product_quantities = {desc: qty for desc, qty in product_quantities.items() if qty > 0}

    # Format the product quantities for the report
    product_quantities_text = ", ".join([f"{description} - {quantity} boxes" for description, quantity in product_quantities.items()])
    report += f"{product_quantities_text})"

# Print the formatted report
# print(report)


# Remove unnecessary characters from the report

report_as_string = json.dumps(report).replace('\\n', '\n')
report_as_string = report_as_string.replace('"', "").replace('{', "").replace('}', '')

# Create the data payload
data_payload = {"U_Pallet_des": report_as_string}

# Print the formatted JSON report
json_report = json.dumps(data_payload, indent=2)
json_report = json_report.replace('\n', "").replace('Pallet ', '\nPallet ')
print(json_report)


# %%

# response = b1_session.request("PATCH", sales_order, data=json_report,  headers=headersList,verify=False)
# response
# print(response.text)
# %%
