from xml.dom.expatbuilder import parseString
import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.logistics.alertList import SeriesName
# from xlsxwriter import Workbook
from frappe.utils.xlsxutils import make_xlsx
import xlsxwriter





#? pip install XlsxWriter

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

@frappe.whitelist()
def AR_Invoice_To_Excel(StartDate,EndDate):
    """
    Update Invoices from SAP to Khanal Tech Integrations 
    """
    session = AuthenticateSAPB1()
    payload = ''
    # EndDate = frappe.utils.nowdate()
    # print(EndDate, 'EndDate')
    # StartDate = add_to_date(EndDate, days=-45)
    # print(StartDate, 'StartDate')
    start_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    print(start_date,'start_date')
    end_date = datetime.now().strftime("%Y-%m-%d")
    print(end_date,'end_date')

    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "Invoices?$filter=DocDate ge '{StartDate}' and DocDate le '{EndDate}'&$skip=" 

    # Initialize an empty DataFrame to store the data
    df_all = pd.DataFrame()

    i = 1
    while True:
        try:
            modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate) + str(20 * (i - 1))
            print('Going into', i, modified_Url)
            session = AuthenticateSAPB1()
            response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
            PurchaseOrders = dict(response.json())

            if PurchaseOrders.get('value'):
                for Single_Order in PurchaseOrders['value']:
                    doc_entry = Single_Order.get('DocEntry')
                    DocNum = Single_Order.get('DocNum')
                    doc_date = Single_Order.get('DocDate')
                    card_code = Single_Order.get('CardCode')
                    card_name = Single_Order.get('CardName')
                    NumAtCard = Single_Order.get('NumAtCard')
                    doc_total = Single_Order.get('DocTotal')
                    due_date = Single_Order.get('DocDueDate')
                    Series = Single_Order.get('Series')
                    # Series = Single_Order.get('Series')
                    # if str(Single_Order.get('Series')) =='-1':
                    #     DocNum                 = Single_Order.get('DocNum')
                    # else:
                    #     DocNum                 = f"{SeriesName[str(Single_Order.get('Series'))]}/{Single_Order.get('DocNum')}"

                    # Iterate through DocumentLines
                    for line in Single_Order.get('DocumentLines', []):
                        item_code = line.get('ItemCode')
                        quantity = line.get('Quantity')
                        U_Purpose = line.get('U_Purpose')
                        remaning_quantity = line.get('RemainingOpenQuantity')
                        DeliveryDate = line.get('ShipDate')
                        Price = line.get('Price')
                        LineTotal = line.get('LineTotal')
                        WarehouseCode = line.get('WarehouseCode')
                        # if line.get('LineStatus')=='bost_Close':
                        #     LineStatus = 'C'
                        # else:
                        #     LineStatus = 'O'
                        LineStatus = 'C' if line.get('LineStatus') == 'bost_Close' else 'O'


                        data = {
                            'DocEntry': [doc_entry],
                            'Posting Date': [doc_date],
                            'Due Date': [due_date],
                            'DocNum': [DocNum],
                            'Series': [Series],
                            'Customer/Vendor Code': [card_code],
                            'Customer/Vendor Name': [card_name],
                            'Customer/Vendor Ref. No': [NumAtCard],
                            'Item No.': [item_code],
                            'Item Purpose.': [U_Purpose],
                            'Quantity': [quantity],
                            'Yet To Receive':[remaning_quantity],
                            'Received Qty':[int(quantity)-int(remaning_quantity)],
                            'Row Delivery Date':[DeliveryDate],
                            'Price': [Price],
                            'Row Total': [LineTotal],
                            'Warehouse Code': [WarehouseCode],
                            'Document Total': [doc_total],
                            'Row Status': [LineStatus],
                            
                        }

                        df = pd.DataFrame(data)
                        df_all = df_all.append(df, ignore_index=True)

                i += 1
            else:
                break

        except Exception as e:
            print(e)

    # Update the last page
    excel_filename =  '/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/AR_Invoice_JAN_DEC_AllData.xlsx'
    # excel_filename =  '/Users/shahilkhan/Desktop/testing/AR Invoice /purchase_invoicewithClosed.xlsx'
    df_all = df_all.sort_values(by='DocEntry', ascending=False)  # Sort DataFrame by DocEntry in descending order
    df_all.to_excel(excel_filename, index=False)
    # df_all.to_excel(excel_filename, index=False)
    # Get_pivot_data(df_all)

    return 'File Saved'


# bench --site dev.localhost execute  --args "{ '2023-01-01','2023-07-31' }"  khanal_tech_integrations.utils.purchase.ToExcel.AR_Invoice_To_Excel



def Get_File(url,sheetname):
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        df = pd.read_excel(response.content,sheetname)
        return df
    else:
        print(f"Error: Unable to retrieve data from {url}")



@frappe.whitelist()
def trigger_function():
    purchase_df = Get_File("http://beta.khanaltech.com/files/purchase_invoice Jan-Dec.xlsx", 'Sheet1')
    print(purchase_df.columns,'purchase_df')
    item_details_df = Get_File("http://beta.khanaltech.com/files/Purchase Register.xlsx", 'Item Details')
    print(item_details_df.columns,'purchase_df')
    merged_df = pd.merge(purchase_df, item_details_df[['Item No.', 'Brand Group', 'ItemGroupDesc']], on='Item No.', how='left')
    merged_df.rename(columns={'Brand Group': 'BrandGroup_new', 'ItemGroupDesc': 'ItemGroupDesc_new'}, inplace=True)
    purchase_df['Brand Group'] = merged_df['BrandGroup_new']
    purchase_df['ItemGroupDesc'] = merged_df['ItemGroupDesc_new']
    # print(purchase_df['ItemGroupDesc'],'ItemGroupDesc')

    purchase_df['Brand Group'].fillna('NA', inplace=True)
    purchase_df['ItemGroupDesc'].fillna('NA', inplace=True)
    print(purchase_df,'purchase_df')
    purchase_df['Posting Date'] = pd.to_datetime(purchase_df['Posting Date'])
    excel_filename =  '/Users/shahilkhan/Desktop/testing/test Jan-Dec.xlsx'
    purchase_df = purchase_df.sort_values(by='DocEntry', ascending=False)  # Sort DataFrame by DocEntry in descending order
    purchase_df.to_excel(excel_filename, index=False)

    brand_groups = purchase_df['Brand Group'].unique()

    purchase_df['Posting Date'] = pd.to_datetime(purchase_df['Posting Date'])

    purchase_df['Month'] = purchase_df['Posting Date'].dt.strftime('%b')

    sorted_months = sorted(purchase_df['Month'].unique(), key=lambda x: pd.to_datetime(x, format='%b'))

    purchase_df['Month'] = pd.Categorical(purchase_df['Month'], categories=sorted_months, ordered=True)

    excel_writer = pd.ExcelWriter('/Users/shahilkhan/Desktop/testing/ResultPivorted_purchase_invoice_Jan-Dec.xlsx', engine='xlsxwriter')

    for brand_group in brand_groups:
        brand_group_data = purchase_df[purchase_df['Brand Group'] == brand_group]

        pivot_table = pd.pivot_table(
            brand_group_data,
            values='Document Total',
            index=['Month'],
            columns=['ItemGroupDesc'],
            aggfunc='sum',
            fill_value=0,
            margins=True,
            margins_name='Grand Total',
        )

        
        sheet_name = brand_group.replace('/', '_')  
        pivot_table.to_excel(excel_writer, sheet_name=sheet_name)

    excel_writer.save()

    print('Completed', '*'*10)

    return None





# bench --site dev.localhost execute  --args "{ '2023-01-01','2023-12-31' }"  khanal_tech_integrations.utils.purchase.ToExcel.Purchase_Order_To_Excel


# bench --site dev.localhost execute   khanal_tech_integrations.utils.purchase.ToExcel.trigger_function
# bench --site dev.localhost execute   khanal_tech_integrations.utils.purchase.ToExcel.save_function

# bench --site dev.localhost execute   khanal_tech_integrations.utils.purchase.ToExcel.trigger_function_tofrappe

import time
from io import BytesIO

@frappe.whitelist()
def Get_pivot_data(purchase_df):
    # purchase_df = Get_File("http://beta.khanaltech.com/files/purchase_invoice Jan-Dec.xlsx", 'Sheet1')
    print(purchase_df.columns, 'purchase_df')
    item_details_df = Get_File("http://beta.khanaltech.com/files/Purchase Register.xlsx", 'Item Details')
    print(item_details_df.columns, 'purchase_df')
    merged_df = pd.merge(purchase_df, item_details_df[['Item No.', 'Brand Group', 'ItemGroupDesc']], on='Item No.', how='left')
    merged_df.rename(columns={'Brand Group': 'BrandGroup_new', 'ItemGroupDesc': 'ItemGroupDesc_new'}, inplace=True)
    purchase_df['Brand Group'] = merged_df['BrandGroup_new']
    purchase_df['ItemGroupDesc'] = merged_df['ItemGroupDesc_new']

    purchase_df['Brand Group'].fillna('NA', inplace=True)
    purchase_df['ItemGroupDesc'].fillna('NA', inplace=True)
    print(purchase_df, 'purchase_df')
    purchase_df['Posting Date'] = pd.to_datetime(purchase_df['Posting Date'])

    # Sort DataFrame by DocEntry in descending order
    purchase_df = purchase_df.sort_values(by='DocEntry', ascending=False)

    brand_groups = purchase_df['Brand Group'].unique()

    purchase_df['Posting Date'] = pd.to_datetime(purchase_df['Posting Date'])
    purchase_df['Month'] = purchase_df['Posting Date'].dt.strftime('%b')

    sorted_months = sorted(purchase_df['Month'].unique(), key=lambda x: pd.to_datetime(x, format='%b'))

    purchase_df['Month'] = pd.Categorical(purchase_df['Month'], categories=sorted_months, ordered=True)

    # Save the pivot_table to an Excel file in memory
    excel_buffer = BytesIO()
    excel_writer = pd.ExcelWriter(excel_buffer, engine='xlsxwriter')

    for brand_group in brand_groups:
        brand_group_data = purchase_df[purchase_df['Brand Group'] == brand_group]

        pivot_table = pd.pivot_table(
            brand_group_data,
            values='Document Total',
            index=['Month'],
            columns=['ItemGroupDesc'],
            aggfunc='sum',
            fill_value=0,
            margins=True,
            margins_name='Grand Total',
        )

        sheet_name = brand_group.replace('/', '_')
        pivot_table.to_excel(excel_writer, sheet_name=sheet_name)

    excel_writer.save()
    excel_buffer.seek(0)

    # Save the Excel file in the "Files" doctype in Frappe
    timestamp = str(int(time.time()))
    file_name = f"Purchase_Invoice_{timestamp}.xlsx"
    aws_upload_url="https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/"+file_name #!Test
    headers = {
                        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                
    }
    aws_response = requests.put(aws_upload_url, headers=headers, data=excel_buffer.read())
    print(aws_response,'aws_response')
    # file_doc = frappe.get_doc({
    #     'doctype': 'File',
    #     'file_name': file_name,
    #     'content': excel_buffer.read(),
    # })
    # # Set is_private attribute
    # # file_doc.set_is_private(1)
    # file_doc.insert()

    print('Completed', '*' * 10)
    print('File saved in AWS S3 Bucket is:', "https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/"+file_name)

    return None


# https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/ResultPivoted_purchase_invoice_Jan-Dec_1704879295.xlsx

    # ResultPivoted_purchase_invoice_Jan-Dec_1704879295.xlsx


# https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/Purchase_Invoice_1704881456.xlsx







@frappe.whitelist()
def JournalEntries_To_Excel(StartDate,EndDate):

    """
    JournalEntries to Excel 
    """
    session = AuthenticateSAPB1()
    payload = ''
    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}' &$skip=" 

    # Initialize an empty DataFrame to store the data
    df_all = pd.DataFrame()

    i = 1
    while True:
        try:
            modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate) + str(20 * (i - 1))
            print('Going into', i, modified_Url)
            session = AuthenticateSAPB1()
            response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
            JournalEntries = dict(response.json())

            if JournalEntries.get('value'):
                for Single_Order in JournalEntries['value']:
                    ReferenceDate = Single_Order.get('ReferenceDate')
                    Memo = Single_Order.get('Memo')
                    Reference = Single_Order.get('Reference')
                    Reference2 = Single_Order.get('Reference2')
                    TransactionCode = Single_Order.get('TransactionCode')
                    ProjectCode = Single_Order.get('ProjectCode')
                    TaxDate = Single_Order.get('TaxDate')
                    JdtNum = Single_Order.get('JdtNum')
                    Indicator = Single_Order.get('Indicator')
                    UseAutoStorno = Single_Order.get('UseAutoStorno')
                    StornoDate = Single_Order.get('StornoDate')
                    VatDate = Single_Order.get('VatDate')
                    Series = Single_Order.get('Series')
                    StampTax = Single_Order.get('StampTax')
                    DueDate = Single_Order.get('DueDate')
                    AutoVAT = Single_Order.get('AutoVAT')
                    Number = Single_Order.get('Number')
                    FolioNumber = Single_Order.get('FolioNumber')
                    FolioPrefixString = Single_Order.get('FolioPrefixString')
                    ReportEU = Single_Order.get('ReportEU')
                    Report347 = Single_Order.get('Report347')
                    Printed = Single_Order.get('Printed')
                    LocationCode = Single_Order.get('LocationCode')
                    OriginalJournal = Single_Order.get('OriginalJournal')
                    Original = Single_Order.get('Original')
                    BaseReference = Single_Order.get('BaseReference')
                    BlockDunningLetter = Single_Order.get('BlockDunningLetter')
                    AutomaticWT = Single_Order.get('AutomaticWT')
                    WTSum = Single_Order.get('WTSum')
                    WTSumSC = Single_Order.get('WTSumSC')
                    WTSumFC = Single_Order.get('WTSumFC')
                    SignatureInputMessage = Single_Order.get('SignatureInputMessage')
                    SignatureDigest = Single_Order.get('SignatureDigest')
                    CertificationNumber = Single_Order.get('CertificationNumber')
                    PrivateKeyVersion = Single_Order.get('PrivateKeyVersion')
                    Corisptivi = Single_Order.get('Corisptivi')
                    Reference3 = Single_Order.get('Reference3')
                    DocumentType = Single_Order.get('DocumentType')
                    DeferredTax = Single_Order.get('DeferredTax')
                    BlanketAgreementNumber = Single_Order.get('BlanketAgreementNumber')
                    OperationCode = Single_Order.get('OperationCode')
                    ResidenceNumberType = Single_Order.get('ResidenceNumberType')
                    ECDPostingType = Single_Order.get('ECDPostingType')
                    ExposedTransNumber = Single_Order.get('ExposedTransNumber')
                    PointOfIssueCode = Single_Order.get('PointOfIssueCode')
                    Letter = Single_Order.get('Letter')
                    FolioNumberFrom = Single_Order.get('FolioNumberFrom')
                    FolioNumberTo = Single_Order.get('FolioNumberTo')
                    IsCostCenterTransfer = Single_Order.get('IsCostCenterTransfer')
                    ReportingSectionControlStatementVAT = Single_Order.get('ReportingSectionControlStatementVAT')
                    ExcludeFromTaxReportControlStatementVAT = Single_Order.get('ExcludeFromTaxReportControlStatementVAT')
                    SAPPassport = Single_Order.get('SAPPassport')
                    Cig = Single_Order.get('Cig')
                    Cup = Single_Order.get('Cup')
                    AdjustTransaction = Single_Order.get('AdjustTransaction')
                    AttachmentEntry = Single_Order.get('AttachmentEntry')
                    U_SrtDocEntry = Single_Order.get('U_SrtDocEntry')
                    U_SrtDocNum = Single_Order.get('U_SrtDocNum')
                   


                    for line in Single_Order.get('JournalEntryLines', []):
                        Line_ID = line.get('Line_ID')
                        AccountCode = line.get('AccountCode')
                        Debit = line.get('Debit')
                        Credit = line.get('Credit')
                        FCDebit = line.get('FCDebit')
                        FCCredit = line.get('FCCredit')
                        FCCurrency = line.get('FCCurrency')
                        Line_DueDate = line.get('DueDate')
                        ShortName = line.get('ShortName')
                        ContraAccount = line.get('ContraAccount')
                        LineMemo = line.get('LineMemo')
                        ReferenceDate1 = line.get('ReferenceDate1')
                        ReferenceDate2 = line.get('ReferenceDate2')
                        Reference1 = line.get('Reference1')
                        Line_Reference2 = line.get('Reference2')
                        Line_ProjectCode = line.get('ProjectCode')
                        CostingCode = line.get('CostingCode')
                        Line_TaxDate = line.get('TaxDate')
                        BaseSum = line.get('BaseSum')
                        TaxGroup = line.get('TaxGroup')
                        DebitSys = line.get('DebitSys')
                        CreditSys = line.get('CreditSys')
                        Line_VatDate = line.get('VatDate')
                        VatLine = line.get('VatLine')
                        SystemBaseAmount = line.get('SystemBaseAmount')
                        VatAmount = line.get('VatAmount')
                        SystemVatAmount = line.get('SystemVatAmount')
                        GrossValue = line.get('GrossValue')
                        AdditionalReference = line.get('AdditionalReference')
                        CheckAbs = line.get('CheckAbs')
                        CostingCode2 = line.get('CostingCode2')
                        CostingCode3 = line.get('CostingCode3')
                        CostingCode4 = line.get('CostingCode4')
                        TaxCode = line.get('TaxCode')
                        TaxPostAccount = line.get('TaxPostAccount')
                        CostingCode5 = line.get('CostingCode5')
                        Line_LocationCode = line.get('LocationCode')
                        ControlAccount = line.get('ControlAccount')
                        EqualizationTaxAmount = line.get('EqualizationTaxAmount')
                        SystemEqualizationTaxAmount = line.get('SystemEqualizationTaxAmount')
                        TotalTax = line.get('TotalTax')
                        SystemTotalTax = line.get('SystemTotalTax')
                        WTLiable = line.get('WTLiable')
                        WTRow = line.get('WTRow')
                        PaymentBlock = line.get('PaymentBlock')
                        BlockReason = line.get('BlockReason')
                        FederalTaxID = line.get('FederalTaxID')
                        BPLID = line.get('BPLID')
                        BPLName = line.get('BPLName')
                        VATRegNum = line.get('VATRegNum')
                        PaymentOrdered = line.get('PaymentOrdered')
                        Line_ExposedTransNumber = line.get('ExposedTransNumber')
                        DocumentArray = line.get('DocumentArray')
                        DocumentLine = line.get('DocumentLine')
                        CostElementCode = line.get('CostElementCode')
                        Line_Cig = line.get('Cig')
                        Line_Cup = line.get('Cup')
                        IncomeClassificationCategory = line.get('IncomeClassificationCategory')
                        IncomeClassificationType = line.get('IncomeClassificationType')
                        ExpensesClassificationCategory = line.get('ExpensesClassificationCategory')
                        ExpensesClassificationType = line.get('ExpensesClassificationType')
                        VATClassificationCategory = line.get('VATClassificationCategory')
                        VATClassificationType = line.get('VATClassificationType')
                        VATExemptionCause = line.get('VATExemptionCause')
                        data = {
                            'ReferenceDate': [ReferenceDate],
                            'Memo': [Memo],
                            'Reference': [Reference],
                            'Reference2': [Reference2],
                            'TransactionCode': [TransactionCode],
                            'ProjectCode': [ProjectCode],
                            'TaxDate': [TaxDate],
                            'JdtNum': [JdtNum],
                            'Indicator': [Indicator],
                            'UseAutoStorno': [UseAutoStorno],
                            'StornoDate': [StornoDate],
                            'VatDate': [VatDate],
                            'Series': [Series],
                            'StampTax': [StampTax],
                            'DueDate': [DueDate],
                            'AutoVAT': [AutoVAT],
                            'Number': [Number],
                            'FolioNumber': [FolioNumber],
                            'FolioPrefixString': [FolioPrefixString],
                            'ReportEU': [ReportEU],
                            'Report347': [Report347],
                            'Printed': [Printed],
                            'LocationCode': [LocationCode],
                            'OriginalJournal': [OriginalJournal],
                            'Original': [Original],
                            'BaseReference': [BaseReference],
                            'BlockDunningLetter': [BlockDunningLetter],
                            'AutomaticWT': [AutomaticWT],
                            'WTSum': [WTSum],
                            'WTSumSC': [WTSumSC],
                            'WTSumFC': [WTSumFC],
                            'SignatureInputMessage': [SignatureInputMessage],
                            'SignatureDigest': [SignatureDigest],
                            'CertificationNumber': [CertificationNumber],
                            'PrivateKeyVersion': [PrivateKeyVersion],
                            'Corisptivi': [Corisptivi],
                            'Reference3': [Reference3],
                            'DocumentType': [DocumentType],
                            'DeferredTax': [DeferredTax],
                            'BlanketAgreementNumber': [BlanketAgreementNumber],
                            'OperationCode': [OperationCode],
                            'ResidenceNumberType': [ResidenceNumberType],
                            'ECDPostingType': [ECDPostingType],
                            'ExposedTransNumber': [ExposedTransNumber],
                            'PointOfIssueCode': [PointOfIssueCode],
                            'Letter': [Letter],
                            'FolioNumberFrom': [FolioNumberFrom],
                            'FolioNumberTo': [FolioNumberTo],
                            'IsCostCenterTransfer': [IsCostCenterTransfer],
                            'ReportingSectionControlStatementVAT': [ReportingSectionControlStatementVAT],
                            'ExcludeFromTaxReportControlStatementVAT': [ExcludeFromTaxReportControlStatementVAT],
                            'SAPPassport': [SAPPassport],
                            'Cig': [Cig],
                            'Cup': [Cup],
                            'AdjustTransaction': [AdjustTransaction],
                            'AttachmentEntry': [AttachmentEntry],
                            'U_SrtDocEntry': [U_SrtDocEntry],
                            'U_SrtDocNum': [U_SrtDocNum],
                            'Line_ID': [Line_ID],
                            'AccountCode': [AccountCode],
                            'Debit': [Debit],
                            'Credit': [Credit],
                            'FCDebit': [FCDebit],
                            'FCCredit': [FCCredit],
                            'FCCurrency': [FCCurrency],
                            'Line_DueDate': [Line_DueDate],
                            'Customer/Vendor Code': [ShortName],
                            'ContraAccount': [ContraAccount],
                            'LineMemo': [LineMemo],
                            'ReferenceDate1': [ReferenceDate1],
                            'ReferenceDate2': [ReferenceDate2],
                            'Reference1': [Reference1],
                            'Line_Reference2': [Line_Reference2],
                            'Line_ProjectCode': [Line_ProjectCode],
                            'CostingCode': [CostingCode],
                            'Line_TaxDate': [Line_TaxDate],
                            'BaseSum': [BaseSum],
                            'TaxGroup': [TaxGroup],
                            'DebitSys': [DebitSys],
                            'CreditSys': [CreditSys],
                            'Line_VatDate': [Line_VatDate],
                            'VatLine': [VatLine],
                            'SystemBaseAmount': [SystemBaseAmount],
                            'VatAmount': [VatAmount],
                            'SystemVatAmount': [SystemVatAmount],
                            'GrossValue': [GrossValue],
                            'AdditionalReference': [AdditionalReference],
                            'CheckAbs': [CheckAbs],
                            'CostingCode2': [CostingCode2],
                            'CostingCode3': [CostingCode3],
                            'CostingCode4': [CostingCode4],
                            'TaxCode': [TaxCode],
                            'TaxPostAccount': [TaxPostAccount],
                            'CostingCode5': [CostingCode5],
                            'Line_LocationCode': [Line_LocationCode],
                            'ControlAccount': [ControlAccount],
                            'EqualizationTaxAmount': [EqualizationTaxAmount],
                            'SystemEqualizationTaxAmount': [SystemEqualizationTaxAmount],
                            'TotalTax': [TotalTax],
                            'SystemTotalTax': [SystemTotalTax],
                            'WTLiable': [WTLiable],
                            'WTRow': [WTRow],
                            'PaymentBlock': [PaymentBlock],
                            'BlockReason': [BlockReason],
                            'FederalTaxID': [FederalTaxID],
                            'BPLID': [BPLID],
                            'BPLName': [BPLName],
                            'VATRegNum': [VATRegNum],
                            'PaymentOrdered': [PaymentOrdered],
                            'Line_ExposedTransNumber': [Line_ExposedTransNumber],
                            'DocumentArray': [DocumentArray],
                            'DocumentLine': [DocumentLine],
                            'CostElementCode': [CostElementCode],
                            'Line_Cig': [Line_Cig],
                            'Line_Cup': [Line_Cup],
                            'IncomeClassificationCategory': [IncomeClassificationCategory],
                            'IncomeClassificationType': [IncomeClassificationType],
                            'ExpensesClassificationCategory': [ExpensesClassificationCategory],
                            'ExpensesClassificationType': [ExpensesClassificationType],
                            'VATClassificationCategory': [VATClassificationCategory],
                            'VATClassificationType': [VATClassificationType],
                            'VATExemptionCause': [VATExemptionCause],
                        }

                        df = pd.DataFrame(data)
                        df_all = df_all.append(df, ignore_index=True)

                i += 1
            else:
                break

        except Exception as e:
            print(e)

    # Update the last page
    excel_filename =  '/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/JournalEntries_JAn_June.xlsx'
    df_all.to_excel(excel_filename, index=False)


    return 'File Saved'



# bench --site dev.localhost execute  --args "{ '2023-01-01','2023-07-31' }"  khanal_tech_integrations.utils.purchase.ToExcel.JournalEntries_To_Excel



@frappe.whitelist()
def JournalEntries_To_Excel_Modified(StartDate, EndDate):
    """
    JournalEntries to Excel
    """
  
    session = AuthenticateSAPB1()
    payload = ''
    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}' &$skip=" 

    # Initialize an empty DataFrame to store the data
    df_all = pd.DataFrame()

    i = 1
    while True:
        try:
            modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate) + str(20 * (i - 1))
            print('Going into', i, modified_Url)
            session = AuthenticateSAPB1()
            response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
            JournalEntries = dict(response.json())

            if JournalEntries.get('value'):
                for single_order in JournalEntries['value']:
                  
                    data = {
                        f"Order_{key}": [value] for key, value in single_order.items()
                    }

                    for line_index, line in enumerate(single_order.get('JournalEntryLines', [])):
                        line_data = {
                            f"Line_{line_index + 1}_{key}": [value] for key, value in line.items()
                        }
                        data.update(line_data)
                    # print(data,'data')
                    df = pd.DataFrame(data)
                    df_all = df_all.append(df, ignore_index=True)

                i += 1
            else:
                break

        except Exception as e:
            print(e)

    # Update the last page
    excel_filename = '/Users/shahilkhan/Desktop/WorkSpace/JournalEntries/All_LIve2nd method_JournalEntries_Dec_Jan.xlsx'
    df_all.to_excel(excel_filename, index=False)

    return 'File Saved'


def extract_data_from_order(single_order):
    data = {
        f"Order_{key}": [value] for key, value in single_order.items()
    }
    # print(data,'data')

    for line in single_order.get('JournalEntryLines', []):
        line_data = {
            f"Line_{key}": [value] for key, value in line.items()
        }
        data.update(line_data)

    return pd.DataFrame(data)