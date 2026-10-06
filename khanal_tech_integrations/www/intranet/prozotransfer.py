import frappe
import frappe.utils
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json" 
                }

def get_context(): #context
    SAPsession =  AuthenticateSAPB1()
    payload = ''
    doc_settings = frappe.get_doc('SAP Settings')
    url = doc_settings.sap_b1_url+"StockTransfers?$filter=DocDate ge '2022-07-20' and FromWarehouse eq 'HN-FG' and startswith(ToWarehouse, 'PZ' ) "	
    response = SAPsession.request("GET", url, data=payload,  headers=headersList,verify=False)	
    # print(response.json()['value'][0].keys())
    Minimal_list = []
    for item in response.json()['value']:
        keysss = ['Series','DocDate', 'DocNum','FromWarehouse' ,'ToWarehouse','JournalMemo','DocEntry']
        dict2 = {x:item[x] for x in keysss }
        Minimal_list.append(dict2)
    context={
        "Minimal_list":Minimal_list
    }  
    return context

# checking 
# @frappe.whitelist()
# def valuecheck(DocEntry):
#     print(DocEntry)
#     pass
    # dict_keys(['odata.etag', 'DocEntry', 'Series', 'Printed', 'DocDate', 'DueDate', 'CardCode', 'CardName',
    #  'Address', 'Reference1', 'Reference2', 'Comments', 'JournalMemo', 'PriceList', 'SalesPersonCode', 'FromWarehouse', 
    # 'ToWarehouse', 'CreationDate', 'UpdateDate', 'FinancialPeriod', 'TransNum', 'DocNum', 'TaxDate', 
    # 'ContactPerson', 'FolioPrefixString', 'FolioNumber', 'DocObjectCode', 'AuthorizationStatus', 'BPLID', 'BPLName', 
    # 'VATRegNum', 'AuthorizationCode', 'StartDeliveryDate', 'StartDeliveryTime', 'EndDeliveryDate', 'EndDeliveryTime', 'VehiclePlate', 'ATDocumentType', 'EDocExportFormat', 'ElecCommStatus',
    #  'ElecCommMessage', 'PointOfIssueCode', 'Letter', 'FolioNumberFrom', 'FolioNumberTo', 'AttachmentEntry', 'DocumentStatus', 'ShipToCode', 'SAPPassport', 'U_TN', 'U_TrackingNo', 'U_ShippingDate', 'U_Delivered', 'U_AddonChk', 'U_AddonChk1', 'U_PrdNo', 'U_TrnsfrTyp', 
    # 'U_WoSeries', 'U_WoSeriesNm', 'U_TransQty', 'U_SubConPONo', 'U_SubConPOEn', 'U_GrDocNum', 'U_GrSeries', 'U_GRType', 'U_GIEntry', 
    # 'U_GINo', 'U_VendRefNo', 'U_GateEntNo', 'U_ProNo', 'U_PlanQty', 'U_SrtDocEntry', 'U_SrtDocNum', 'U_GIEnt', 'U_BatchNo', 'U_PreDelInsp', 'U_GenType', 'U_UTL_ST_ADD', 'U_UTL_SC_JVCD', 'U_UTL_SC_JVNM', 
    # 'U_AWBNo', 'U_ExpRefNo', 'U_MfgLicNo', 'U_FDARegNo', 'U_PCB', 'U_PRC', 'U_COO', 'U_CFD', 'U_VrFNo',
    #  'U_POL', 'U_POD', 'U_PODn', 'U_TODP', 'U_KOP', 'U_TP', 'U_NW', 'U_GW', 'U_MOS', 'U_PM', 'U_TB', 'U_AppointmentReqd',
    #  'U_AppointmentSchDate', 'U_AppointmentTime', 'U_Proof_of_Delivery', 'U_BillingFrom', 'U_BillTo', 'U_TransProcessType', 'StockTransfer_ApprovalRequests', 
    # 'ElectronicProtocols', 'StockTransferLines', 'StockTransferTaxExtension', 'DocumentReferences'])