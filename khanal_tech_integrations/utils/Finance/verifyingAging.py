
import frappe
import pandas as pd
import datetime
from io import BytesIO


# utils/Finance/verifyingAging.py
# bench --site dev.localhost execute  --args "( '2024-07-01','C03413' )"  khanal_tech_integrations.utils.Finance.verifyingAging.DataFormJournalEntries
# csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/APIResponse/MAY 20/'
csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Export/'


def DataFormJournalEntries(EndDate,Vendorcode):
    print(Vendorcode,'Vendorcode')
    print(EndDate,'EndDate')
    JournalEntriesList_List = frappe.get_list('SAP Journal Entries',
                    filters={
                            # 'referencedate': ['between', [StartDate, EndDate]],
                            # 'referencedate': ['<=', EndDate],
                            'customervendor_code': Vendorcode,
   
                        },
                        fields=['referencedate', 'memo', 'duedate', 'taxdate', 'reference', 'lineitem.customervendor_code', 'lineitem.debit', 'lineitem.credit'], as_list=True,order_by='referencedate asc',

                        )

    print(len(JournalEntriesList_List), 'Length of JournalEntriesList_List')

    formatted_entries = []
    for entry in JournalEntriesList_List:
        # entry_date = entry[0]
        # print('\n\n\n',entry_date)
        formatted_date = entry[0].strftime('%Y-%m-%d') if entry[0] else None

        # duedate = entry[2]
        formatted_duedate = entry[2].strftime('%Y-%m-%d') if entry[2] else None

       
        formatted_entry = (formatted_date,  entry[6], entry[7],entry[5],formatted_duedate)
        formatted_entries.append(formatted_entry)
    # print(len(formatted_entries),'formatted_entries')
 

    columns_to_select = ['ReferenceDate', 'Debit', 'Credit', 'Customer/Vendor Code', 'DueDate']

    # Create DataFrame
    filtered_df = pd.DataFrame(formatted_entries, columns=columns_to_select)
    # print(filtered_df,'formatted_entries')
    # print(filtered_df.info(),'filtered_df.info()')  # Check DataFrame information
    filtered_df.to_csv(csv_filename + 'CORE' + '.csv', index=False)
    


    # Convert date columns to datetime objects
    date_columns = ['ReferenceDate', 'DueDate',]
    filtered_df[date_columns] = filtered_df[date_columns].apply(pd.to_datetime)

    numeric_columns = ['Debit', 'Credit']
    filtered_df[numeric_columns] = filtered_df[numeric_columns].apply(pd.to_numeric, errors='coerce')
    # print(df,'dfdfdf')
    filtered_df['ReferenceDate'] = pd.to_datetime(filtered_df['ReferenceDate'], format='%d/%m/%y', errors='coerce')
    filtered_df['DueDate'] = pd.to_datetime(filtered_df['DueDate'], format='%d/%m/%y', errors='coerce')


    current_date = datetime.datetime.now()
    filtered_df['Age'] = (current_date - filtered_df['DueDate']).dt.days
    filtered_df.to_csv(csv_filename + 'Age' + '.csv', index=False)
    
    filtered_df = filtered_df.dropna(subset=['Customer/Vendor Code'])
    # filtered_df.to_csv(csv_filename + 'dropna' + '.csv', index=False)
    

    filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].str[0].isin(['V', 'C', 'E'])]
    bins = [0, 30, 60, 90, 120, float('inf')]
    labels = ['0-30', '31-60', '61-90', '91-120', '120+']
    filtered_df['Age Group'] = pd.cut(filtered_df['Age'], bins=bins, labels=labels, right=False)
    # filtered_df.to_csv(csv_filename + 'Age Group' + '.csv', index=False)
    filtered_df['Age Group'] = pd.Categorical(filtered_df['Age Group'], categories=labels, ordered=True)
    # filtered_df.to_csv(csv_filename + 'Categorical' + '.csv', index=False)
    
    # # Calculate document total and total
    filtered_df['Total'] = filtered_df['Debit'] - filtered_df['Credit']


    grouped_totals = filtered_df.groupby('Customer/Vendor Code')[['Total']].sum()

    print(grouped_totals, '\n\n', 'grouped_totals')

    threshold = 10e-10    # Adjust the threshold as needed



    print(grouped_totals,'\n\n','grouped_totals')
    non_zero_groups = grouped_totals[abs(grouped_totals['Total']) > threshold]

    print(non_zero_groups, '\n\n', 'non_zero_groups')



    # non_zero_groups.to_csv(csv_filename + 'non_zero_groups' + '.csv', index=False)

    filtered_df = filtered_df[filtered_df['Customer/Vendor Code'].isin(non_zero_groups.index)]
    print(filtered_df,'filtered_df')


    # !--------------Normal Excel---------------------
    filtered_df_E_V = filtered_df[filtered_df['Customer/Vendor Code'].str.startswith(('E', 'V'))]
    filtered_df_C = filtered_df[filtered_df['Customer/Vendor Code'].str.startswith('C')]

    # Create an Excel writer
    with pd.ExcelWriter(csv_filename + Vendorcode + '.xlsx') as writer:
        # Write 'filtered_df_E_V' to 'E_V' sheet
        filtered_df_E_V.to_excel(writer, sheet_name='Vendor', index=False)
        
        # Write 'filtered_df_C' to 'C' sheet
        filtered_df_C.to_excel(writer, sheet_name='Customer', index=False)



    
    # # Group by Customer/Vendor Code and Age Group, and calculate sum of Total
    aging_report = filtered_df.groupby(['Customer/Vendor Code', 'Age Group'], sort=False)[['Total']].sum().unstack(fill_value=0)
    
    # Group by Customer/Vendor Code and calculate sum of Debit and Credit
    customer_totals = filtered_df.groupby('Customer/Vendor Code')[['Debit', 'Credit']].sum()
    # print('\n\n\n',aging_report)
    # # Flatten the column index of aging_report
    aging_report.columns = [' '.join(map(str, col)) for col in aging_report.columns]

    # Merge the two DataFrames
    aging_report = aging_report.merge(customer_totals, how='left', on='Customer/Vendor Code')
    aging_report['Balance Due'] = aging_report['Debit'] - aging_report['Credit']
    aging_report.columns = labels + ['Total Debit', 'Total Credit', 'Balance Due']
    aging_report.index = aging_report.index.astype(str).fillna('')
    
    aging_report.reset_index(inplace=True)
    aging_report.to_csv(csv_filename + Vendorcode + 'ageing.csv', index=False)




    # !--------------Ageing Excel---------------------

    vendor_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('V')]
    # customer_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('C')]
    employee_sheet = aging_report[aging_report['Customer/Vendor Code'].str.startswith('E')]
    # Create a BytesIO buffer to hold the Excel file
    excel_buffer = BytesIO()
    combined_sheet = pd.concat([vendor_sheet, employee_sheet])


    # Write the Excel file to the buffer
    with pd.ExcelWriter(excel_buffer) as writer:
        # vendor_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        # customer_sheet.to_excel(writer, sheet_name='Customer', index=True)
        combined_sheet.to_excel(writer, sheet_name='Vendor', index=True)
        # employee_sheet.to_excel(writer, sheet_name='Employee', index=True)

    
    vendor_data = combined_sheet.copy()
    # customer_data = customer_sheet.copy()
    # employee_data = employee_sheet.copy()

    with pd.ExcelWriter(csv_filename + Vendorcode + 'ageing.xlsx') as writer:
    # Write vendor_data to 'Vendor' sheet
        vendor_data.to_excel(writer, sheet_name='Vendor', index=True)
        
        # Write customer_data to 'Customer' sheet
        # customer_data.to_excel(writer, sheet_name='Customer', index=True)
    pass
    # return aging_report
