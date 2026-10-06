# Sync BP Masters of SAP B1 with Khanal Tech and Erpnext and vice versa

import frappe
from frappe import _
from frappe.utils import validate_email_address

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=100",
                }
payload = ''

# Sync BP Masters of SAP B1 with Khanal Tech and Erpnext and vice versa
# bench --site dev.localhost execute khanal_tech_integrations.utils.sap_bp_master.sap_vendors.get_sap_bp_master
@frappe.whitelist()
def get_sap_bp_master():
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"BusinessPartners?$filter=CardType eq 'S' and not startswith(CardCode, 'EMP')" #+ str(20*i)
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    bp_master = dict(response.json())
    # print (bp_master['odata.nextLink'])
    
    # for i in range(1,2):
    while bp_master.get('odata.nextLink', None):
        update_bp_master(bp_master)
        print (bp_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+bp_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        bp_master = dict(response.json())
        
    update_bp_master(bp_master)

def update_bp_master(bp_master):

    for i in range(len(bp_master['value'])):
        bp_code = bp_master['value'][i]['CardCode']
        if frappe.db.exists("Supplier", {"custom_sap_vendor_code": bp_code}):
            bp_master_doc = frappe.get_doc("Supplier", {"custom_sap_vendor_code": bp_code})
            new_doc = False
        else:
            bp_master_doc = frappe.new_doc("Supplier")
            new_doc = True

        # bp_master_doc = frappe.new_doc("Supplier")
        bp_master_doc.supplier_name = bp_master['value'][i]['CardName'] if bp_master['value'][i]['CardName'] else ''
        # bp_master_doc.supplier_type = bp_master['value'][i]['CardType']
        bp_master_doc.disabled = 0 if bp_master['value'][i]['Valid'] == 'tYES' else 1 # "Frozen": "tNO",
        bp_master_doc.custom_sap_vendor_code = bp_code
        try:
            bp_master_doc.custom_sap_vendor_type = bp_master['value'][i]['U_Vtype'] if bp_master['value'][i]['U_Vtype'] else ''
        except:
            bp_master_doc.custom_sap_vendor_type = ''
        bp_master_doc.supplier_group = frappe.get_value("Supplier Group", {"custom_supplier_group_code": bp_master['value'][i]['GroupCode']})
        bp_master_doc.custom_foreign_name = bp_master["value"][i].get(
            "CardForeignName", ""
        )

        ShipToDefault = bp_master['value'][i].get('ShipToDefault', '')
        BillToDefault = bp_master['value'][i].get('BillToDefault', '')

        if new_doc:
            bp_master_doc.insert()
        else:
            bp_master_doc.save()

        for address in bp_master['value'][i]['BPAddresses']:
            # if address['AddressType'] == 'bo_BillTo':
            # print (address['AddressName'])
            address_doc = frappe.new_doc("Address")
            address_doc.address_title = address['AddressName']
            address_doc.address_type = 'Billing' if address['AddressType'] == 'bo_BillTo' else 'Shipping'

            address_doc.address_line1 = address['Street'] if address['Street'] else 'NA'
            address_doc.address_line2 = address.get('Block', 'NA')
            address_doc.city = address['City'] if address['City'] else 'NA'
            address_doc.state = states.get(address.get('State', 'NA'))
            address_doc.pincode = address.get('ZipCode', '')
            address_doc.country = frappe.get_value("Country", {"code": address.get('Country', '').lower()}, "name")
            address_doc.email_id = address.get('E_Mail', '')
            address_doc.phone = address.get('Phone1', '')
            address_doc.mobile_no = address.get('Cellolar', '')
            address_doc.fax = address.get('Fax', '')
            address_doc.website = address.get('WebSite', '')

            # Link the address to the supplier
            address_doc.append('links', {
                'link_doctype': 'Supplier',
                'link_name': bp_master_doc
            })
            # print ('ShipToDefault : ',ShipToDefault,'BillToDefault : ', BillToDefault)
            # print (address['AddressType'], address['AddressName'])

            if (address['AddressType'] == 'bo_BillTo' and BillToDefault == address['AddressName']):
                address_doc.is_primary_address = 1
                bp_master_doc.supplier_primary_address = address_doc
                bp_master_doc.save()
                # print ('BillToDefault', address['AddressName'])
            if (address['AddressType'] == 'bo_ShipTo' and ShipToDefault == address['AddressName']):
                address_doc.is_shipping_address = 1

            address_doc.insert()
            # frappe.db.commit()

        for contact in bp_master['value'][i]['ContactEmployees']:
            contact_doc = frappe.new_doc("Contact")
            contact_doc.first_name = contact['Name']
            contact_doc.designation = contact.get('Position', '')
            contact_doc.department = contact.get('Department', '')
            contact_doc.remarks = contact.get('Remarks1', '')

            # Add email to the 'Email' child table
            if (contact.get('E_Mail')):
                if validate_email_address(contact['E_Mail']):
                    # frappe.throw(_("Invalid Email Address: {0}").format(contact['E_Mail']))
                    contact_doc.append('email_ids', {
                        'email_id': contact['E_Mail'],
                        'is_primary': 1
                    })

            # Add phone to the 'Phone' child table
            if contact.get('Phone1'):
                phone_number = frappe.utils.validate_phone_number(contact['Phone1'],throw=False)

                if phone_number:
                    print (contact.get('Phone1'))
                    contact_doc.append('phone_nos', {
                        'phone': contact.get('Phone1'),
                        'is_primary_phone': 1
                    })

            # Add mobile no to the 'Phone' child table
            if contact.get('Cellolar'):
                contact_doc.append('phone_nos', {
                    'phone': contact['Cellolar'],
                    'is_primary_mobile_no': 1
                })

            contact_doc.append('links', {
                'link_doctype': 'Supplier',
                'link_name': bp_master_doc
            })

            contact_doc.insert()
        frappe.db.commit()

# bench --site dev.localhost execute khanal_tech_integrations.utils.procure_to_pay.syncBP_master.update_bp_groups
# Sync the Business Partner Groups from SAP B1 to Khanal Tech and Erpnext
@frappe.whitelist()
def update_bp_groups():
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"BusinessPartnerGroups"
    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)
    bp_groups = dict(response.json())['value']
    # print (bp_groups)

    for i in range(len(bp_groups)):
        # update_bp_groups(bp_groups)
        if frappe.db.exists("Supplier Group", {"custom_supplier_group_code": bp_groups[i]['Code']}):
            bp_group_doc = frappe.get_doc("Supplier Group", {"custom_supplier_group_code": bp_groups[i]['Code']})
            new_doc = False
        else:
            bp_group_doc = frappe.new_doc("Supplier Group")
            new_doc = True

        bp_group_doc.supplier_group_name = bp_groups[i]['Name']
        bp_group_doc.custom_supplier_group_code = bp_groups[i]['Code']

        if new_doc:
            bp_group_doc.insert()
        else:
            bp_group_doc.save()
    frappe.db.commit()


states = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chattisgarh",
    "DN": "Dadra and Nagar Haveli",
    "DD": "Daman and Diu",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir",
    "JH": "Jharkhand",
    "KT": "Karnataka",
    "KL": "Kerala",
    "LD": "Lakshadweep Islands",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PY": "Pondicherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
    "NA": "Other Territory",
}
