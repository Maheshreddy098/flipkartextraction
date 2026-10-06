import frappe
from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
import json
headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" 
    }
def get_context(context):
    if frappe.local.form_dict.ID:
        ID=frappe.local.form_dict.ID
    else:
        ID = ''
    doc=frappe.get_doc('SAP Vendor Registration', ID) 
    session =  AuthenticateSAPB1()
    payload = ''  
    i = 0
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl      = doc_settings.sap_b1_url+"States?$select=Code,Name&$filter=startswith(Country,'IN')&$skip=" + str(20*i)
    LineItem_list = []
    while True:
        response = session.request("GET", reqUrl, headers=headersList,data=payload, verify=False)
        Statename = dict(response.json())
        Inventory_items = Statename.get("value")
        next_page = Statename.get("odata.nextLink")
        if Inventory_items is not None:
            for item in Inventory_items:
                LineItem_list.append({
                    'Code':item['Code'],
                   'Name' : item['Name']
                })
        if next_page is None or Inventory_items is None:
            break

        i += 1
        base_url=doc_settings.sap_b1_url
        reqUrl = f"{base_url}/States?$select=Code,Name&$filter=startswith(Country,'IN')&$skip={20*i}"
    print(LineItem_list,'LineItem_list')
    # print(len(LineItem_list))
    context={
        "doc":doc,
        "LineItem_list":LineItem_list
    } 
    # print(doc.fssai_licence,'doc')
    return context


@frappe.whitelist()
def PostingVendor_to_SAP(name,vendor_type,bill_to,ship_to):
    doc=frappe.get_doc('SAP Vendor Registration', name) 
    Business_payload = {
        "Series": 86,
        "CardName": doc.company_name,
        "CardForeignName": doc.vendor_name,
        "Address": doc.address,
        "EmailAddress": doc.email,
        "Cellular": doc.mobile_number,
        "U_MSME": doc.mesme_present,
        "U_MSME_No":   doc.msmed_number.upper(),
        "CardType": "cSupplier",
        # "DefaultAccount":doc.account_number,
        # "DefaultBranch":doc.bank_name,
        # "DefaultBankCode":doc.ifsc_code,
        "BillToState": bill_to,
        "ShipToState": ship_to,
        "U_Vtype":vendor_type,
        # "DocumentLines": [],
        "ContactEmployees": [{
                                "Name":doc.contact_person_name,
                                "Position":doc.designation,
                                "MobilePhone":doc.contact_person_number,
                                "E_Mail":doc.contact_person_email,
                            }],
        "BPAddresses": [
                            {
                                "AddressName": "Bill to",
                                "Street": doc.address,
                                "State": bill_to,
                                "GSTIN": doc.gst_number,
                                "MYFType": '',
                                "TaasEnabled": "tYES",
                                "U_UTL_ST_ThLegName": '',
                                "U_UTL_ST_ThTrdName": '',
                                "GstType": 'gstRegularTDSISD',
                                "FederalTaxID": '',
                                "TaxCode": '',
                                "BuildingFloorRoom": "",
                                "AddressType": "bo_BillTo",
                                "AddressName2": '',
                                "AddressName3": '',
                                "TypeOfAddress": '',
                                "StreetNo": '',
                                "Block": '',
                                "ZipCode": '',
                                "City": '',
                                "County": '',
                            },
                            {
                                "AddressName": "Ship To",
                                "Street": doc.ship_to_address,
                                "State": ship_to,
                                "GSTIN": "",
                                "MYFType": '',
                                "TaasEnabled": "tYES",
                                "U_UTL_ST_ThLegName": '',
                                "U_UTL_ST_ThTrdName": '',
                                "GstType": '',
                                "FederalTaxID": '',
                                "TaxCode": '',
                                "BuildingFloorRoom": "",
                                "AddressType": "bo_ShipTo",
                                "AddressName2": '',
                                "AddressName3": '',
                                "TypeOfAddress": '',
                                "StreetNo": '',
                                "Block": '',
                                "ZipCode": '',
                                "City": '',
                                "County": '',
                            },],
        # 'BPBankAccounts' :[{
        #                "AccountNo": doc.account_number,
        #                "BankCode": doc.bank_name,
        #                "BICSwiftCode": doc.ifsc_code,            
        # }]
    }

    SAPsession =  AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    invoice_Url = doc_settings.sap_b1_url+"BusinessPartners" #DeliveryNotes
    response = SAPsession.request("POST", invoice_Url, data=json.dumps(Business_payload),  headers=headersList,verify=False)
    # print(response,'response')
    # print(response.text)
    # print(response.status_code)
    if response.status_code == 400:
        response_data = json.loads(response.text)
        error_value = response_data['error']['message']['value']
        return error_value
    else:
        doc.vendor_type  = vendor_type
        doc.bill_to_state= bill_to
        doc.ship_to_state= ship_to 
        doc.save()
        frappe.db.commit()
        return None


    # return response.text


@frappe.whitelist()
def Rejecting_vendor(name,Reason):
    doc=frappe.get_doc('SAP Vendor Registration', name)
    msg = """
          <div style="margin:0 auto;background:#f2f5f7">
            <table style="margin:auto;background:#f2f5f7 url() top center no-repeat;padding:35px 0 20px;width:750px"
                cellpadding="0" cellspacing="0" border="0">

                <tbody>
                    <tr>
                        <td align="center" valign="middle" style="margin:0;padding:0">
                            <table width="750" border="0" cellpadding="0" cellspacing="0" style="width:750px;margin:auto">
                                <tbody>
                                    <tr>
                                        <td align="center" valign="middle" style="padding:0 0 24px;margin:0"><a href=""
                                                target="_blank" data-saferedirecturl="#">
                                                <img src="https://khanaltech.com/files/khanalfoods_logo.jpg" width="60"
                                                    height="60" alt="" class="CToWUd" data-bit="iit">
                                            </a></td>
                                    </tr>
                                </tbody>
                            </table>
                            <table width="750" border="0" cellpadding="0" cellspacing="0"
                                style="width:750px;margin:auto;background:url(https://ci4.googleusercontent.com/proxy/Ic7NVCs2Hj_DUbcW_VKD5QvRjPm2GWgt48QKJi4p_q_TwwHtaNtOUd4PVcqphtxPXNMQDPBpwtKKV8j66a1_vVo9p_9KaGNuw6eYmf36zKEmWv6w00ZEoep59VD08NHGsqUhTzzGjkXpAs91f5FZLAggHNgiejaDrJ8=s0-d-e1-ft) top center no-repeat;padding:0 0 21px">
                                <tbody>
                                    <tr>
                                        <td align="left" valign="top" style="padding:40px 54px 0;margin:0" colspan="2">
                                            <p style="font-size:17px;color:#666666;font-family:sans-serif;margin:0">Dear
                                                {company_name},</p>
                                            <p>We regret to inform you that your Vendor Registration has been canceled due to
                                                {reason}. To rectify the issue, kindly visit the following link: {base_url}/vendor-registration/{name}</p>
                                            <br>
                                            <p>Thank you for your attention to this matter</p>
                                        </td>
                                    </tr>
                                    <tr></tr>

                                </tbody>
                            </table>
                        </td>
                    </tr>

                </tbody>
            </table>
            <table border="0" cellpadding="0" cellspacing="0" width="750" style="width:750px;margin:auto">
                <tbody>
                    <tr>
                        <td align="center" valign="top"
                            style="padding:0;margin:0;color:#666;font-size:13px;font-family:sans-serif">
                            <p style="font-size: 12px; color: #777;font-style: italic;">Note: This is a system generated email.
                                Please do
                                not reply to this email.</p><br>
                            Copyright © 2023 khanalFoods Pvt. Ltd. | All rights reserved.
                        </td>
                    </tr>

                </tbody>
            </table>

        </div> 
                
    """.format(company_name=doc.company_name, reason=Reason, name=doc.name, base_url=frappe.utils.get_url())
                ######################################## pdf adding 
            # attachments=[frappe.attach_print('SAP AR Invoice Detail',doc.docentry,file_name=doc.docentry )]
            # recipients=[sales_personemail,contact_email]
   
    email_args = {
            "recipients": doc.email,
            "message": msg,
            "subject": 'Vendor Registration Cancellation Notice',
        }
    # if attachments:email_args['attachments']=attachments
    frappe.enqueue(method=frappe.sendmail, queue='short', timeout=300, **email_args)
    pass



@frappe.whitelist()
def Edit_Vendor_Detais(FormData_value):
    Value_dict = json.loads(FormData_value)
    vendorlist =frappe.db.get_list('SAP Vendor Registration',filters={  'email':Value_dict['email']},pluck='name')
    doc                                = frappe.get_doc("SAP Vendor Registration", vendorlist[0])
    doc.company_name                   = Value_dict['company_name']
    doc.vendor_name                    = Value_dict['vendor_name']
    doc.telephone_number               = Value_dict['telephone_number']
    doc.mobile_number                  = Value_dict['mobile_number']
    doc.email                          = Value_dict['email']
    doc.contact_person_name            = Value_dict['contact_person_name']
    doc.designation                    = Value_dict['designation']
    doc.gst_number                     = Value_dict['gst_number']
    doc.msmed_number                   = Value_dict['msmed_number']
    doc.payment_terms                  = Value_dict['payment_terms']
    doc.days                           = Value_dict['days']
    doc.return_policy                  = Value_dict['return_policy']
    doc.address                        = Value_dict['address']
    doc.save()
    frappe.db.commit()
    print('saved',doc)
    return {'name': doc.name}

# {"company_name":"ABC","vendor_name":"Shahil","telephone_number":"93405230357","mobile_number":"124124y1y",
# "email":"shahilkhan.7139@gmail.com","gst_number":"Dicta quos at debitis ad quis voluptatibus in cupidatat"," contact_person_name":"Shahil Khan"
# ,"designation":"sjsj","msmed_number":"2","return_policy":"12o93","payment_terms":"22","days":"2","address":"kurikkanmar kandi (h)"}