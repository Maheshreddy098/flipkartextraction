import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import pandas as pd
from datetime import datetime, timedelta
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

csv_filename = '/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/newData.csv'
# df = pd.read_csv('/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/newData.csv')
headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=900",
                }
payload = ''


@frappe.whitelist()
def JournalEntries_To_csv(StartDate,EndDate):

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
    # existing_df = pd.read_csv(csv_filename)

    # Check if the file already exists
    # try:
    #     existing_df = pd.read_csv(csv_filename)
    # except FileNotFoundError:
    #     existing_df = pd.DataFrame()



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
                        # existing_df = existing_df.append(df, ignore_index=True)
                        # Check if the data already exists in existing_df
                        # existing_df = existing_df.append(df, ignore_index=True)

                        # if existing_df.empty or not existing_df.isin(df.to_dict()).all().any():
                        #     existing_df = existing_df.append(df, ignore_index=True)


                i += 1
            else:
                break

        except Exception as e:
            print(e)

    # Update the last page
    # df_all.to_csv(csv_filename, index=False)
    # updated_df = pd.concat([existing_df, df_all]).drop_duplicates()
    df_all.to_csv(csv_filename, index=False)
    # existing_df = existing_df.drop_duplicates()

    # Update the CSV file with existing and new data
    # existing_df.to_csv(csv_filename, index=False)




    return 'CSV File Saved'


# bench --site dev.localhost execute  --args "('2024-01-26','2024-04-24' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.JournalEntries_To_csv




# bench --site khanaltech.com execute  --args "('2024-01-01','2024-05-07','1' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Fetch_JournalEntries


# bench --site khanaltech.com execute  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Daily_Update_JournalEntries

@frappe.whitelist()
def Daily_Update_JournalEntries():
    try:
        Today = frappe.utils.nowdate()
        Day_before_Today = add_to_date(Today,days=-1)
        print(Day_before_Today,'Day_before_Today')
        # Fetch_JournalEntries(StartDate=Day_before_Today,EndDate=Day_before_Today,Count=1)
        get_sap_journalentries(StartDate=Day_before_Today,EndDate=Today)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), str(e))
    

    return 'Daily Update JournalEntries is Complete'


@frappe.whitelist()
def Fetch_JournalEntries(StartDate=None,EndDate=None,Count=None):

    """
    JournalEntries to Excel 
    """
    session = AuthenticateSAPB1()
    payload = ''
    # INITIALIZATION
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url + "JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}' &$skip=" 
    i = int(Count)
    while True:
        try:
            modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate) + str(20 * (i - 1))
            print('Going into', i, modified_Url)
            session = AuthenticateSAPB1()
            response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
            JournalEntries = dict(response.json())

            if JournalEntries.get('value'):
                for Single_Order in JournalEntries['value']:
                    doc                     =frappe.new_doc('SAP Journal Entries')
                    doc.referencedate       = Single_Order.get('ReferenceDate')
                    doc.memo                = Single_Order.get('Memo')
                    doc.taxdate             = Single_Order.get('TaxDate')
                    doc.duedate             = Single_Order.get('DueDate')
                    doc.reference           = Single_Order.get('Reference')
                    doc.reference2          = Single_Order.get('Reference2')
                    doc.transactioncode     = Single_Order.get('TransactionCode')
                    doc.projectcode         = Single_Order.get('ProjectCode')
                    doc.jdtnum              = Single_Order.get('JdtNum')
                    doc.indicator           = Single_Order.get('Indicator')
                    doc.number              = Single_Order.get('Number')
                    doc.locationcode        = Single_Order.get('LocationCode')
                    doc.basereference       = Single_Order.get('BaseReference')
                    doc.original            = Single_Order.get('Original')
                    doc.useautostorno       = Single_Order.get('UseAutoStorno')
                    doc.stornodate          = Single_Order.get('StornoDate')
                    doc.vatdate             = Single_Order.get('VatDate')
                    doc.series              = Single_Order.get('Series')
                    doc.wtsum               = Single_Order.get('WTSum')
                    doc.wtsumsc             = Single_Order.get('WTSumSC')
                    doc.wtsumfc             = Single_Order.get('WTSumFC')
                    doc.originaljournal     = Single_Order.get('OriginalJournal')
                    doc.reference3          = Single_Order.get('Reference3')
                    doc.documenttype        = Single_Order.get('DocumentType')
                    doc.operationcode       = Single_Order.get('OperationCode')
                    doc.residencenumbertype = Single_Order.get('ResidenceNumberType')
                    doc.ecdpostingtype      = Single_Order.get('ECDPostingType')

                    LineItem_list = []
                    
                    for line in Single_Order.get('JournalEntryLines', []):
                        LineItem_list.append(
                            {
                            "line_id"               :line.get('Line_ID'),
                            "customervendor_code"   :line.get('ShortName'),
                            'accountcode'           :line.get('AccountCode'),
                            'debit'                 :line.get('Debit'),
                            "credit"                :line.get('Credit'),
                            "fcdebit"               :line.get('FCDebit'),
                            "fccredit"              :line.get('FCCredit'),
                            "fccurrency"            :line.get('FCCurrency'),
                            "line_duedate"          :line.get('DueDate'),
                            "contraaccount"         :line.get('ContraAccount'),
                            "linememo"              :line.get('LineMemo'),
                            "referencedate1"        :line.get('ReferenceDate1'),
                            "reference1"            :line.get('Reference1'),
                            "projectcode"           :line.get('ProjectCode'),
                            "line_taxdate"          :line.get('TaxDate'),
                            "costingcode2"          :line.get('CostingCode2'),
                            "costingcode3"          :line.get('CostingCode3'),
                            "costingcode4"          :line.get('CostingCode4'),
                            "taxcode"               :line.get('TaxCode'),
                            "taxpostaccount"        :line.get('TaxPostAccount'),
                            "costingcode5"          :line.get('CostingCode5'),
                            "locationcode"          :line.get('LocationCode'),
                            "controlaccount"        :line.get('ControlAccount'),
                            "totaltax"              :line.get('TotalTax'),
                            })
                                                
                       
                    for LineItem in LineItem_list:
                        doc.append("lineitem",LineItem)


                    
                    try:
                        doc.save()
                        frappe.db.commit()
                        print(doc,'saved')
                    except frappe.DuplicateEntryError:
                        print(doc,'duplicate')
                        pass


                i += 1
            else:
                break

        except Exception as e:
            print(e)


    return 'File Saved'


@frappe.whitelist()
def delete():
    x = 'SAP Journal Entries'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        # print(documentt,'documentt')
        documentt.delete()
        print(documentt,'documentt Delected')



# bench --site dev.localhost execute  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.delete


@frappe.whitelist()
def Scheduled_delete():
    x = 'Scheduled Job Type'
    print(len(frappe.get_list(x)))
    for documentt in frappe.get_list(x):
        documentt = frappe.get_doc( x , documentt.name)
        # print(documentt,'documentt')
        documentt.delete()
        print(documentt,'documentt Delected')



# bench --site dev.localhost execute  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Scheduled_delete


# bench --site khanaltech.com execute  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Scheduled_delete
# bench --site khanaltech.com execute  --args "('2024-01-01','2024-02-29','1' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Fetch_JournalEntries






# Bulk_Data = '/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/Bulk_DataNew.csv'


# bench --site dev.localhost execute  --args "('2023-01-26','2024-04-24' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Bulk_Updation

@frappe.whitelist()
def Bulk_Updation(StartDate,EndDate):
    print(StartDate,EndDate,'StartDate,EndDate')
    df_all = pd.DataFrame()
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    # item_master = sap.get_item_master()
    reqUrl = doc_settings.sap_b1_url+ "JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}'" 
    modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate) 
    response = session.request("GET", modified_Url, data=payload,  headers=headersList,verify=False)
    JournalEntries_list = dict(response.json())
    while JournalEntries_list.get('odata.nextLink', None):
        update_jounalEntries(JournalEntries_list,df_all)
        print (JournalEntries_list['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+JournalEntries_list['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        JournalEntries_list = dict(response.json())
        # update_jounalEntries(item_master)

    update_jounalEntries(JournalEntries_list,df_all)
    # df_all.to_csv(Bulk_Data, index=False)

def update_jounalEntries(JournalEntries_data,df_all):
    
    if JournalEntries_data.get('value'):
        for Single_Order in JournalEntries_data['value']:
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
    
    
    df_all.to_csv(csv_filename, index=False)
    

    return 'File Saved'





# bench --site dev.localhost execute  --args "('2023-01-01','2023-01-31' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.Bulk_UpdationTEST

csv_filenametest = '/Users/shahilkhan/Desktop/WorkSpace/Aging Report/journalentry/TestData1.csv'


# @frappe.whitelist()
# def Bulk_UpdationTEST(StartDate, EndDate):
#     print(StartDate, EndDate, 'StartDate,EndDate')
#     df_all = pd.DataFrame()  # Initialize DataFrame outside the loop
#     session = AuthenticateSAPB1()
#     doc_settings = frappe.get_doc('SAP Settings')
#     reqUrl = doc_settings.sap_b1_url + "JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}'"
#     modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate)
#     response = session.request("GET", modified_Url, data=payload, headers=headersList, verify=False)
#     JournalEntries_list = dict(response.json())
#     while JournalEntries_list.get('odata.nextLink', None):
#         update_journalEntriestest(JournalEntries_list, df_all)
#         print(JournalEntries_list['odata.nextLink'])
#         next_url = doc_settings.sap_b1_url + JournalEntries_list['odata.nextLink']
#         response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
#         JournalEntries_list = dict(response.json())
    


#     update_journalEntriestest(JournalEntries_list, df_all)
#     # print('\n\n\n',df_all,'\n\n\n')
#     # df_all.to_csv(csv_filenametest, index=False)  # Save the DataFrame to CSV

# def update_journalEntriestest(JournalEntries_data, df_all):
#     if JournalEntries_data.get('value'):
#         for Single_Order in JournalEntries_data['value']:
#             ReferenceDate = Single_Order.get('ReferenceDate')
#             Memo = Single_Order.get('Memo')
#             for line in Single_Order.get('JournalEntryLines', []):
#                 Line_ID = line.get('Line_ID')
#                 AccountCode = line.get('AccountCode')
#                 Debit = line.get('Debit')
#                 Credit = line.get('Credit')

#                 data = {
#                     'ReferenceDate': [ReferenceDate],
#                     'Memo': [Memo],
#                     'Line_ID': [Line_ID],
#                     'AccountCode': [AccountCode],
#                     'Debit': [Debit],
#                     'Credit': [Credit],
#                 }

#                 df = pd.DataFrame(data)
                
#                 # print(df_all,'df_all')
#                 try:
#                     df_all = df_all.append(df, ignore_index=True)  # Append data to df_all DataFrame
#                 except frappe.DuplicateEntryError:
#                     pass

# # Calling function to get all S
#                 pass

#     return 'File Saved'


def get_sap_journalentries(StartDate=None,EndDate=None):
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    # item_master = sap.get_item_master()
    reqUrl = doc_settings.sap_b1_url+"JournalEntries?$filter=ReferenceDate ge '{StartDate}' and ReferenceDate le '{EndDate}'" #+ str(20*i)
    modified_Url = reqUrl.format(StartDate=StartDate, EndDate=EndDate)
    response = session.request("GET", modified_Url, data=payload,  headers=headersList,verify=False)
    journalentries = dict(response.json())
    # print (journalentries['odata.nextLink'])

    while journalentries.get('odata.nextLink', None):
        update_journalentries(journalentries)
        print (journalentries['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+journalentries['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        journalentries = dict(response.json())
        # update_journalentries(journalentries)

    update_journalentries(journalentries)


def update_journalentries(journalentries_data):
    # Sync Item Masters of SAP B1 with Khanal Tech and Erpnext and vice versa
    for i in range(len(journalentries_data['value'])):
        JdtNum = journalentries_data['value'][i]['JdtNum']
        # print(journalentries_data['value'][i].get('ReferenceDate', ''),'*8******')
        # print (JdtNum)
        if frappe.db.exists("SAP Journal Entries", JdtNum):
            journalentries_doc = frappe.get_doc("SAP Journal Entries",JdtNum)
            new_doc = False
            pass
        else:
            doc = frappe.new_doc("SAP Journal Entries")
            new_doc = True
            # doc.referencedate       = journalentries_data['value'][i]['ReferenceDate']
            # doc.memo                = journalentries_data['value'][i]['Memo']
            # doc.taxdate             = journalentries_data['value'][i]['TaxDate']
            # doc.duedate             = journalentries_data['value'][i]['DueDate']
            # doc.reference           = journalentries_data['value'][i]['Reference']
            # doc.reference2          = journalentries_data['value'][i]['Reference2']
            # doc.transactioncode     = journalentries_data['value'][i]['TransactionCode']
            # doc.projectcode         = journalentries_data['value'][i]['ProjectCode']
            # doc.jdtnum              = journalentries_data['value'][i]['JdtNum']
            # doc.indicator           = journalentries_data['value'][i]['Indicator']
            # doc.number              = journalentries_data['value'][i]['Number']
            # doc.locationcode        = journalentries_data['value'][i]['LocationCode']
            # doc.basereference       = journalentries_data['value'][i]['BaseReference']
            # doc.original            = journalentries_data['value'][i]['Original']
            # doc.useautostorno       = journalentries_data['value'][i]['UseAutoStorno']
            # doc.stornodate          = journalentries_data['value'][i]['StornoDate']
            # doc.vatdate             = journalentries_data['value'][i]['VatDate']
            # doc.series              = journalentries_data['value'][i]['Series']
            # doc.wtsum               = journalentries_data['value'][i]['WTSum']
            # doc.wtsumsc             = journalentries_data['value'][i]['WTSumSC']
            # doc.wtsumfc             = journalentries_data['value'][i]['WTSumFC']
            # doc.originaljournal     = journalentries_data['value'][i]['OriginalJournal']
            # doc.reference3          = journalentries_data['value'][i]['Reference3']
            # doc.documenttype        = journalentries_data['value'][i]['DocumentType']
            # doc.operationcode       = journalentries_data['value'][i]['OperationCode']
            # doc.residencenumbertype = journalentries_data['value'][i]['ResidenceNumberType']
            # doc.ecdpostingtype      = journalentries_data['value'][i]['ECDPostingType']
            doc.referencedate       = journalentries_data['value'][i].get('ReferenceDate', '')
            doc.memo                = journalentries_data['value'][i].get('Memo', '')
            doc.taxdate             = journalentries_data['value'][i].get('TaxDate', '')
            doc.duedate             = journalentries_data['value'][i].get('DueDate', '')
            doc.reference           = journalentries_data['value'][i].get('Reference', '')
            doc.reference2          = journalentries_data['value'][i].get('Reference2', '')
            doc.transactioncode     = journalentries_data['value'][i].get('TransactionCode', '')
            doc.projectcode         = journalentries_data['value'][i].get('ProjectCode', '')
            doc.jdtnum              = journalentries_data['value'][i].get('JdtNum', '')
            doc.indicator           = journalentries_data['value'][i].get('Indicator', '')
            doc.number              = journalentries_data['value'][i].get('Number', '')
            doc.locationcode        = journalentries_data['value'][i].get('LocationCode', '')
            doc.basereference       = journalentries_data['value'][i].get('BaseReference', '')
            doc.original            = journalentries_data['value'][i].get('Original', '')
            doc.useautostorno       = journalentries_data['value'][i].get('UseAutoStorno', '')
            doc.stornodate          = journalentries_data['value'][i].get('StornoDate', '')
            doc.vatdate             = journalentries_data['value'][i].get('VatDate', '')
            doc.series              = journalentries_data['value'][i].get('Series', '')
            doc.wtsum               = journalentries_data['value'][i].get('WTSum', '')
            doc.wtsumsc             = journalentries_data['value'][i].get('WTSumSC', '')
            doc.wtsumfc             = journalentries_data['value'][i].get('WTSumFC', '')
            doc.originaljournal     = journalentries_data['value'][i].get('OriginalJournal', '')
            doc.reference3          = journalentries_data['value'][i].get('Reference3', '')
            doc.documenttype        = journalentries_data['value'][i].get('DocumentType', '')
            doc.operationcode       = journalentries_data['value'][i].get('OperationCode', '')
            doc.residencenumbertype = journalentries_data['value'][i].get('ResidenceNumberType', '')
            doc.ecdpostingtype      = journalentries_data['value'][i].get('ECDPostingType', '')


            LineItem_list = []
            
            for line in journalentries_data['value'][i].get('JournalEntryLines', []):
                LineItem_list.append(
                    {
                        "line_id": line.get('Line_ID'),
                        "customervendor_code": line.get('ShortName'),
                        'accountcode': line.get('AccountCode'),
                        'debit': line.get('Debit'),
                        "credit": line.get('Credit'),
                        "fcdebit": line.get('FCDebit'),
                        "fccredit": line.get('FCCredit'),
                        "fccurrency": line.get('FCCurrency'),
                        "line_duedate": line.get('DueDate'),
                        "contraaccount": line.get('ContraAccount'),
                        "linememo": line.get('LineMemo'),
                        "referencedate1": line.get('ReferenceDate1'),
                        "reference1": line.get('Reference1'),
                        "projectcode": line.get('ProjectCode'),
                        "line_taxdate": line.get('TaxDate'),
                        "costingcode2": line.get('CostingCode2'),
                        "costingcode3": line.get('CostingCode3'),
                        "costingcode4": line.get('CostingCode4'),
                        "taxcode": line.get('TaxCode'),
                        "taxpostaccount": line.get('TaxPostAccount'),
                        "costingcode5": line.get('CostingCode5'),
                        "locationcode": line.get('LocationCode'),
                        "controlaccount": line.get('ControlAccount'),
                        "totaltax": line.get('TotalTax'),
                    })
                                        
                
            for LineItem in LineItem_list:
                doc.append("lineitem",LineItem)

      
            doc.save()
    frappe.db.commit()


# bench --site khanaltech.com execute  --args "('2022-01-01','2024-09-06' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.get_sap_journalentries
# bench --site khanaltech.com execute  --args "('2022-04-01','2024-09-16' )"  khanal_tech_integrations.utils.React_Api.Ledger.JournalEntries.get_sap_journalentries


# bench --site khanaltech.com execute  khanal_tech_integrations.utils.schedulejob.AgeingReport_Ap_Ar

# bench --site khanaltech.com execute  khanal_tech_integrations.utils.unicommerce.fill_15days_orders

# bench --site khanaltech.com execute  khanal_tech_integrations.utils.unicommerceFile.DeliveryNotes.Unicommerce_Dispatch_INV

# bench --site khanaltech.com execute  khanal_tech_integrations.utils.unicommerceFile.CreditNote.Unicommerce_CreditNote_FromINN

# bench --site khanaltech.com execute  khanal_tech_integrations.utils.schedulejob.EcomReport_Weekly

# bench --site khanaltech.com execute  khanal_tech_integrations.utils.schedulejob.ExportReport_Weekly
