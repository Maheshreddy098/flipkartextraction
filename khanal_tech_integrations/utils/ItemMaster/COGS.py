#%%
import pandas as pd 
# %%
po_df = pd.read_excel("/Users/shahilkhan/Desktop/WorkSpace/Production Orders/2024/10July.xlsx")
issue_df = pd.read_excel("Complete March and April.xlsx", sheet_name="Issue")
recipt_df = pd.read_excel("Complete March and April.xlsx", sheet_name="Receipt")
batchPrice_df = pd.read_excel("Complete March and April.xlsx", sheet_name="Sheet2")

# %%
po_df = po_df[(po_df['ProductionOrderStatus'] == 'boposClosed') &
              (po_df['ProductionOrderType'] != 'bopotDisassembly')]
# %%
issue_df = issue_df[issue_df['ProductionBaseEntry'].isin(po_df['AbsoluteEntry'])]
recipt_df = recipt_df[recipt_df['ProductionBaseEntry'].isin(po_df['AbsoluteEntry'])]

# %%
# Get unique ProductionBaseEntry values sorted by DocDate
unique_entries_sorted = issue_df.drop_duplicates(subset='ProductionBaseEntry').sort_values(by=['DocEntry'])['ProductionBaseEntry']

# Convert the result to a list (optional, if needed)
unique_entries_list = unique_entries_sorted.tolist()
# %%
new_df = pd.DataFrame(columns=['BatchNumber', 'ItemCode', 'LineQuantity', 'UnitPrice','Difference Present'])


for entry in unique_entries_list:
    entry_input_rows = issue_df[issue_df['ProductionBaseEntry'] == entry]
    entry_output_rows = recipt_df[recipt_df['ProductionBaseEntry'] == entry]
    total_output_quantity = entry_output_rows[~entry_output_rows['ItemCode'].str.startswith('WAST')]['LineQuantity'].sum()
    
    
    total_output_quantity_with_waste = entry_output_rows['LineQuantity'].sum()
    total_input_quantity = entry_input_rows['LineQuantity'].sum()
    input_output_diff = total_input_quantity - total_output_quantity_with_waste
    diff_present = False
    if input_output_diff >-1 and input_output_diff<1:
        diff_present = False
    else:
        diff_present = True

    inputPrice = 0
    for _, row in entry_input_rows.iterrows():
        item_code = row['ItemCode']
        batch_number = row['BatchNumber']
        line_quantity = row['LineQuantity']

        # Get UnitPrice from batchPrice_df for the combination of ItemCode and BatchNumber
        unit_price = batchPrice_df.loc[(batchPrice_df['ItemCode'] == item_code) &
                                        (batchPrice_df['BatchNumber'] == batch_number), 'UnitPrice']
        
        unit_price_from_recipts = new_df.loc[(new_df['ItemCode'] == item_code) &
                                        (new_df['BatchNumber'] == batch_number), 'UnitPrice']
        
        # If there's a matching unit price, extract the first value
        if not unit_price_from_recipts.empty:
            unit_price_value = unit_price_from_recipts.values[0]
            new_df.loc[(new_df['ItemCode'] == item_code) & (new_df['BatchNumber'] == batch_number)[0], 'LineQuantity'] -= line_quantity
        elif not unit_price.empty:
            unit_price_value = unit_price.values[0]
        else:
            unit_price_value = 0
        inputPrice = inputPrice + (unit_price_value*row["LineQuantity"])
    outputUnitPrice = inputPrice/total_output_quantity
    

    for _, row in entry_output_rows[~entry_output_rows['ItemCode'].str.startswith('WAST')].iterrows():
        item_code = row['ItemCode']
        batch_number = row['BatchNumber']
        line_quantity = row['LineQuantity']
        match_index = (new_df['ItemCode'] == item_code) & (new_df['BatchNumber'] == batch_number)

        # If there's a match, add LineQuantity and update unit price
        if match_index.any():
            match_row_index = new_df.index[match_index][0]  # Get the index of the first matching row
            
            existing_line_quantity = new_df.loc[match_row_index, 'LineQuantity']
            existing_unit_price = new_df.loc[match_row_index, 'UnitPrice']
            
            weighted_average_unit_price = ((existing_line_quantity * existing_unit_price) + (outputUnitPrice * line_quantity)) / (existing_line_quantity + line_quantity)
            new_df.at[match_row_index, 'UnitPrice'] = weighted_average_unit_price
            new_df.at[match_row_index, 'Difference Present'] = diff_present
            new_df.loc[match_row_index, 'LineQuantity'] += line_quantity
        else:
            # Define the values for the new row
            new_row_values = {
                'BatchNumber': row['BatchNumber'],
                'ItemCode': row['ItemCode'],
                'LineQuantity': row["LineQuantity"],
                'UnitPrice': outputUnitPrice,
                'Difference Present':diff_present
            }
            new_df.loc[len(new_df)] = [batch_number, item_code, line_quantity, outputUnitPrice]



      
        
# %%
new_df = new_df[new_df['ItemCode'].str.startswith('RM')]

# Export new_df to Excel
output_file = 'new_df_filtered.xlsx'
new_df.to_excel(output_file, index=False)
# %%
