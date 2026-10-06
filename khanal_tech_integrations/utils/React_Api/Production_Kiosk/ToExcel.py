import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Production Orders/CheckDataOg11.csv'

BpData = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Production Orders/GST REVENUE REPORT 22-23.xlsx','Sheet1')
headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=300",
                }
payload = ''


@frappe.whitelist()
def ProductionOrders_ToExcel(StartDate, EndDate):
    import pandas as pd
    import frappe

    def update_ProductionOrders(ProductionOrders_data):
        temp_list = []
        if ProductionOrders_data.get('value'):
            for Single_Order in ProductionOrders_data['value']:
                AbsoluteEntry = Single_Order.get('AbsoluteEntry')
                DocumentNumber = Single_Order.get('DocumentNumber')
                ProductionOrderStatus = Single_Order.get('ProductionOrderStatus')
                ProductionOrderType = Single_Order.get('ProductionOrderType')
                Series = Single_Order.get('Series')
                ItemNo = Single_Order.get('ItemNo')
                PlannedQuantity = Single_Order.get('PlannedQuantity')
                CompletedQuantity = Single_Order.get('CompletedQuantity')
                RejectedQuantity = Single_Order.get('RejectedQuantity')
                PostingDate = Single_Order.get('PostingDate')
                DueDate = Single_Order.get('DueDate')
                Warehouse = Single_Order.get('Warehouse')
                RejectedQuantity = Single_Order.get('RejectedQuantity')
                ProductionOrderOrigin = Single_Order.get('ProductionOrderOrigin')
                UserSignature = Single_Order.get('UserSignature')
                Remarks = Single_Order.get('Remarks')
                ClosingDate = Single_Order.get('ClosingDate')
                ReleaseDate = Single_Order.get('ReleaseDate')
                CustomerCode = Single_Order.get('CustomerCode')
                InventoryUOM = Single_Order.get('InventoryUOM')
                JournalRemarks = Single_Order.get('JournalRemarks')
                TransactionNumber = Single_Order.get('TransactionNumber')
                CreationDate = Single_Order.get('CreationDate')
                UoMEntry = Single_Order.get('UoMEntry')
                StartDate = Single_Order.get('StartDate')
                ProductDescription = Single_Order.get('ProductDescription')
                
                for line in Single_Order.get('ProductionOrderLines', []):
                    LineNumber = line.get('LineNumber')
                    LineItemNo = line.get('ItemNo')
                    BaseQuantity = line.get('BaseQuantity')
                    LinePlannedQuantity = line.get('PlannedQuantity')
                    IssuedQuantity = line.get('IssuedQuantity')
                    LineWarehouse = line.get('Warehouse')
                    
                    data = {
                        'AbsoluteEntry': AbsoluteEntry,
                        'DocumentNumber': DocumentNumber,
                        'ItemNo': ItemNo,
                        'Series': Series,
                        'ProductionOrderStatus': ProductionOrderStatus,
                        'ProductionOrderType': ProductionOrderType,
                        'ProductionOrderOrigin': ProductionOrderOrigin,
                        'UserSignature': UserSignature,
                        'Remarks': Remarks,
                        'ClosingDate': ClosingDate,
                        'ReleaseDate': ReleaseDate,
                        'CustomerCode': CustomerCode,
                        'InventoryUOM': InventoryUOM,
                        'JournalRemarks': JournalRemarks,
                        'TransactionNumber': TransactionNumber,
                        'CreationDate': CreationDate,
                        'UoMEntry': UoMEntry,
                        'StartDate': StartDate,
                        'ProductDescription': ProductDescription,
                        'PlannedQuantity': PlannedQuantity,
                        'DueDate': DueDate,
                        'CompletedQuantity': CompletedQuantity,
                        'RejectedQuantity': RejectedQuantity,
                        'PostingDate': PostingDate,
                        'LineNumber': LineNumber,
                        'LineItemNo': LineItemNo,
                        'BaseQuantity': BaseQuantity,
                        'LinePlannedQuantity': LinePlannedQuantity,
                        'IssuedQuantity': IssuedQuantity, 
                        'Warehouse': Warehouse,      
                        'LineWarehouse': LineWarehouse,          
                    }

                    temp_list.append(data)
        return temp_list

    print(StartDate, EndDate, 'StartDate,EndDate')
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "ProductionOrders?$filter=PostingDate ge '{StartDate}' and PostingDate le '{EndDate}' and ProductionOrderStatus eq 'boposClosed' and ProductionOrderType ne 'bopotDisassembly'"
    modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate)
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    ProductionOrders_list = dict(response.json())
    
    all_data = []
    
    while ProductionOrders_list.get('odata.nextLink', None):
        all_data.extend(update_ProductionOrders(ProductionOrders_list))
        print(ProductionOrders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + ProductionOrders_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        ProductionOrders_list = dict(response.json())

    all_data.extend(update_ProductionOrders(ProductionOrders_list))
    
    df_all = pd.DataFrame(all_data)
    # # csv_filename = 'ProductionOrders.csv'
    df_all.to_csv(csv_filename, index=False)  # Save the DataFrame to a CSV file

    
    
    return 'File Saved'



# bench --site dev.localhost execute  --args "( '2024-03-01','2024-03-03' )"  khanal_tech_integrations.utils.React_Api.Production_Kiosk.ToExcel.ProductionOrders_ToExcel


# /Users/shahilkhan/Desktop/khanalFoods/frappe-bench/apps/khanal_tech_integrations/khanal_tech_integrations/utils/React_Api/Production_Kiosk/ToExcel.py





@frappe.whitelist()
def ProductionOrders_ToFrappe(StartDate, EndDate):


    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    reqUrl = doc_settings.sap_b1_url + "ProductionOrders?$filter=PostingDate ge '{StartDate}' and PostingDate le '{EndDate}' and ProductionOrderStatus eq 'boposClosed' and ProductionOrderType ne 'bopotDisassembly'"
    modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate)
    response = session.request("GET", modified_Url, headers=headersList, verify=False)
    ProductionOrders_list = dict(response.json())
    
    all_data = []
    
    while ProductionOrders_list.get('odata.nextLink', None):
        all_data.extend(update_ProductionOrders(ProductionOrders_list))
        print(ProductionOrders_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url + ProductionOrders_list['odata.nextLink']
        response = session.request("GET", next_url, headers=headersList, verify=False)
        ProductionOrders_list = dict(response.json())

    all_data.extend(update_ProductionOrders(ProductionOrders_list))
    
    df = pd.DataFrame(all_data)



    MofifyingData_Tofrappe=MofifyingData(df)

    Data_ToFrappe=UpdationDoc(MofifyingData_Tofrappe)
    MofifyingData_Tofrappe.to_csv(csv_filename, index=False)
    return 'File Saved'



def update_ProductionOrders(ProductionOrders_data):
    temp_list = []
    if ProductionOrders_data.get('value'):
        for Single_Order in ProductionOrders_data['value']:
            AbsoluteEntry = Single_Order.get('AbsoluteEntry')
            DocumentNumber = Single_Order.get('DocumentNumber')
            ProductionOrderStatus = Single_Order.get('ProductionOrderStatus')
            ProductionOrderType = Single_Order.get('ProductionOrderType')
            Series = Single_Order.get('Series')
            ItemNo = Single_Order.get('ItemNo')
            PlannedQuantity = Single_Order.get('PlannedQuantity')
            CompletedQuantity = Single_Order.get('CompletedQuantity')
            RejectedQuantity = Single_Order.get('RejectedQuantity')
            PostingDate = Single_Order.get('PostingDate')
            DueDate = Single_Order.get('DueDate')
            Warehouse = Single_Order.get('Warehouse')
            RejectedQuantity = Single_Order.get('RejectedQuantity')
            ProductionOrderOrigin = Single_Order.get('ProductionOrderOrigin')
            UserSignature = Single_Order.get('UserSignature')
            Remarks = Single_Order.get('Remarks')
            ClosingDate = Single_Order.get('ClosingDate')
            ReleaseDate = Single_Order.get('ReleaseDate')
            CustomerCode = Single_Order.get('CustomerCode')
            InventoryUOM = Single_Order.get('InventoryUOM')
            JournalRemarks = Single_Order.get('JournalRemarks')
            TransactionNumber = Single_Order.get('TransactionNumber')
            CreationDate = Single_Order.get('CreationDate')
            UoMEntry = Single_Order.get('UoMEntry')
            StartDate = Single_Order.get('StartDate')
            ProductDescription = Single_Order.get('ProductDescription')
            
            for line in Single_Order.get('ProductionOrderLines', []):
                LineNumber = line.get('LineNumber')
                LineItemNo = line.get('ItemNo')
                BaseQuantity = line.get('BaseQuantity')
                LinePlannedQuantity = line.get('PlannedQuantity')
                IssuedQuantity = line.get('IssuedQuantity')
                LineWarehouse = line.get('Warehouse')
                
                data = {
                    'AbsoluteEntry': AbsoluteEntry,
                    'DocumentNumber': DocumentNumber,
                    'ItemNo': ItemNo,
                    'Series': Series,
                    'ProductionOrderStatus': ProductionOrderStatus,
                    'ProductionOrderType': ProductionOrderType,
                    'ProductionOrderOrigin': ProductionOrderOrigin,
                    'UserSignature': UserSignature,
                    'Remarks': Remarks,
                    'ClosingDate': ClosingDate,
                    'ReleaseDate': ReleaseDate,
                    'CustomerCode': CustomerCode,
                    'InventoryUOM': InventoryUOM,
                    'JournalRemarks': JournalRemarks,
                    'TransactionNumber': TransactionNumber,
                    'CreationDate': CreationDate,
                    'UoMEntry': UoMEntry,
                    'StartDate': StartDate,
                    'ProductDescription': ProductDescription,
                    'PlannedQuantity': PlannedQuantity,
                    'DueDate': DueDate,
                    'CompletedQuantity': CompletedQuantity,
                    'RejectedQuantity': RejectedQuantity,
                    'PostingDate': PostingDate,
                    'LineNumber': LineNumber,
                    'LineItemNo': LineItemNo,
                    'BaseQuantity': BaseQuantity,
                    'LinePlannedQuantity': LinePlannedQuantity,
                    'IssuedQuantity': IssuedQuantity, 
                    'Warehouse': Warehouse,      
                    'LineWarehouse': LineWarehouse,          
                }

                temp_list.append(data)
    return temp_list

def MofifyingData(df):
    result = df.groupby(['AbsoluteEntry']).agg({
        'ItemNo': 'first',  # Take the first value of 'ItemNo' within each group
        'CompletedQuantity': 'first',
        'Warehouse': 'first',
        'DocumentNumber': 'first',
        'Series': 'first',
        'ProductionOrderStatus': 'first',
        'ProductionOrderType': 'first',
        'ProductionOrderOrigin': 'first',
        'UserSignature': 'first',
        'Remarks': 'first',
        'ClosingDate': 'first',
        'ReleaseDate': 'first',
        'CustomerCode': 'first',
        'InventoryUOM': 'first',
        'JournalRemarks': 'first',
        'TransactionNumber': 'first',
        'CreationDate': 'first',
        'UoMEntry': 'first',
        'StartDate': 'first',
        'DueDate': 'first',
        'PostingDate': 'first',     
        'LineNumber': lambda x: x[df['LinePlannedQuantity'] < 0].tolist(),
        'LinePlannedQuantity': lambda x: x[df['LinePlannedQuantity'] < 0].tolist(),
        'LineItemNo': lambda x: x[df['LinePlannedQuantity'] < 0].tolist(),
        'LineWarehouse': lambda x: x[df['LinePlannedQuantity'] < 0].tolist(),
    }).reset_index()

    # Display the result
    # print(result)
    new_rows = []

    for index, row in result.iterrows():
        if row['LinePlannedQuantity']:
            for qty_idx, qty in enumerate(row['LinePlannedQuantity']):
                if qty < 0:
                    # Check if 'ItemNo' and 'Warehouse' are lists
                    if isinstance(row['LineItemNo'], list):
                        item_no = row['LineItemNo'][qty_idx]
                    else:
                        item_no = row['LineItemNo']
                    
                    if isinstance(row['LineWarehouse'], list):
                        warehouse = row['LineWarehouse'][qty_idx]
                    else:
                        warehouse = row['LineWarehouse']
                    
                    # Create a new row with positive 'LinePlannedQuantity'
                    new_row = {'AbsoluteEntry': row['AbsoluteEntry'],
                            'ItemNo': item_no,  # Access the individual element or the whole string
                            'Warehouse': warehouse,  # Access the individual element or the whole string
                            'CompletedQuantity': abs(qty),
                            'LineNumber': [],  # No 'LineNumber' for this row
                            'LinePlannedQuantity': abs(qty),
                            'DocumentNumber': row['DocumentNumber'],
                            'Series': row['Series'],
                            'ProductionOrderStatus': row['ProductionOrderStatus'],
                            'ProductionOrderType': row['ProductionOrderType'],
                            'ProductionOrderOrigin': row['ProductionOrderOrigin'],
                            'UserSignature': row['UserSignature'],
                            'Remarks': row['Remarks'],
                            'ClosingDate': row['ClosingDate'],
                            'ReleaseDate': row['ReleaseDate'],
                            'CustomerCode': row['CustomerCode'],
                            'InventoryUOM': row['InventoryUOM'],
                            'JournalRemarks': row['JournalRemarks'],
                            'TransactionNumber': row['TransactionNumber'],
                            'CreationDate': row['CreationDate'],
                            'UoMEntry': row['UoMEntry'],
                            'StartDate': row['StartDate'],
                            'DueDate': row['DueDate'],
                            'PostingDate': row['PostingDate']
                            
                            
                            }
                    # Append the new row to the list
                    new_rows.append(new_row)

    # Convert the list of new rows to a DataFrame
    new_rows_df = pd.DataFrame(new_rows)

    result = pd.concat([result, new_rows_df], ignore_index=True)

    # Specify the columns to drop
    columns_to_drop = ['LineNumber', 'LinePlannedQuantity', 'LineItemNo', 'LineWarehouse']

    # Drop the specified columns
    result = result.drop(columns=columns_to_drop)
    # fields_to_add = ['Series', 'ProductionOrderStatus', 'ProductionOrderType', 'ProductionOrderOrigin',
    #              'UserSignature', 'Remarks', 'ClosingDate', 'ReleaseDate', 'CustomerCode',
    #              'InventoryUOM', 'JournalRemarks', 'TransactionNumber', 'CreationDate',
    #              'UoMEntry', 'StartDate']

    # # P erform the merge based on AbsoluteEntry
    # merged_results = result.merge(df[['AbsoluteEntry'] + fields_to_add], 
    #                                     on='AbsoluteEntry', 
    #                                     how='left')

    # # Display the merged DataFrame
    # print(result)
    Final_output = result.merge(BpData, how='left', left_on='ItemNo', right_on='Item No.')

    # Drop the duplicate 'Item No.' column
    Final_output.drop(['Item No.', 'UOM Weight'], axis=1, inplace=True)

    Final_output['Weight/Quantity (MIS) - Unit Weight'] = Final_output['Weight/Quantity (MIS) - Unit Weight'].replace(0, 1)

    # Add a new column 'Total QTY'
    Final_output['Total QTY'] = Final_output['CompletedQuantity'] * Final_output['Weight/Quantity (MIS) - Unit Weight']


    
    return Final_output


def UpdationDoc(FinalDf):
    print(FinalDf.columns)
    # Assuming merged_results is a pandas DataFrame
    FinalDf = FinalDf.where(pd.notnull(FinalDf), None)

    for index, row in FinalDf.iterrows():
        print(row['Brand'],'row['']')
        unique_key = f"{row['AbsoluteEntry']}-{row['ItemNo']}"
        # print(unique_key,'unique_key')
        if frappe.db.exists("SAP Production Orders", unique_key):
            # productionmaster = frappe.get_doc("SAP Production Orders",unique_key)
            # new_doc = False
            pass
        else:
           
            productionmaster = frappe.new_doc("SAP Production Orders")
            productionmaster.absoluteentry=row['AbsoluteEntry']
            productionmaster.itemno=row['ItemNo']
            productionmaster.completedquantity=row['CompletedQuantity']
            productionmaster.documentnumber=row['DocumentNumber']
            productionmaster.warehouse=row['Warehouse']
            productionmaster.series=row['Series']
            productionmaster.productionorderstatus=row['ProductionOrderStatus']
            productionmaster.productionordertype=row['ProductionOrderType']
            productionmaster.productionorderorigin=row['ProductionOrderOrigin']
            productionmaster.usersignature=row['UserSignature']
            productionmaster.remarks=row['Remarks']
            productionmaster.closingdate=row['ClosingDate']
            productionmaster.releasedate=row['ReleaseDate']
            productionmaster.data_qnro=row['CustomerCode']
            productionmaster.inventoryuom=row['InventoryUOM']
            productionmaster.journalremarks=row['JournalRemarks']
            productionmaster.transactionnumber=row['TransactionNumber']
            productionmaster.creationdate=row['CreationDate']
            productionmaster.uomentry=row['UoMEntry']
            productionmaster.duedate=row['DueDate']
            productionmaster.productdescription=row['Item Description']
            productionmaster.category=row['Category']
            productionmaster.brand=row['Brand']
            productionmaster.type=row['Type']
            productionmaster.wq=row['Weight/Quantity (MIS) - Unit Weight']
            productionmaster.uom=row['UoM (MIS)']
            productionmaster.totalqty=row['Total QTY']
            productionmaster.postingdate=row['PostingDate']
            productionmaster.startdate=row['StartDate']

            productionmaster.save()
            frappe.db.commit()
       


       
 
        
    #     # Save the document
    #     if new_doc:
            
    #         productionmaster.save()
    #     else:
    #         productionmaster.insert()
    #     # item_master_doc.insert()
    # frappe.db.commit()

    pass



# Index(['AbsoluteEntry', 'ItemNo', 'CompletedQuantity', 'Warehouse',
#        'DocumentNumber', 'Series', 'ProductionOrderStatus',
#        'ProductionOrderType', 'ProductionOrderOrigin', 'UserSignature',
#        'Remarks', 'ClosingDate', 'ReleaseDate', 'CustomerCode', 'InventoryUOM',
#        'JournalRemarks', 'TransactionNumber', 'CreationDate', 'UoMEntry',
#        'StartDate', 'DueDate', 'PostingDate', 'Item Description', 'Category',
#        'Brand', 'Type', 'Weight/Quantity (MIS) - Unit Weight', 'UoM (MIS)',
#        'Total QTY'],
#       dtype='object')