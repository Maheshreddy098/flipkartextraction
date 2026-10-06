# Sync SAP Customer data with Khanal Tech and Erpnext

import frappe
from frappe import _
from frappe.utils import validate_email_address

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.sap_bp_master.sap_vendors import states


headersList = {
                    "Accept": "*/*",
                    "User-Agent": "Khanal Tech",
                    "Content-Type": "application/json",
                    "Prefer": "odata.maxpagesize=100",
                }
payload = ''

# bench --site dev.localhost execute khanal_tech_integrations.utils.sap_bp_master.sap_customer.get_sap_customer
# bench --site dev.localhost execute khanal_tech_integrations.utils.sap_bp_master.sap_customer.initialize_customer

@frappe.whitelist()
def initialize_customer():
    update_bp_group()
    get_sap_customer()


@frappe.whitelist()
def get_sap_customer():
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"BusinessPartners?$filter=CardType eq 'C' and not startswith(CardCode, 'EMP')"

    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)

    customer_master = dict(response.json())

    # for i in range(1,2):
    while customer_master.get('odata.nextLink', None):
        try:
            update_customer_master(customer_master)
        except Exception as e:
            print (e)
            
        print (customer_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+customer_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        customer_master = dict(response.json())

def update_customer_master(customer_master):

    for i in range(len(customer_master['value'])):
        customer_code = customer_master['value'][i]['CardCode']
        if frappe.db.exists("Customer", {"custom_sap_customer_code": customer_code}):
            customer_master_doc = frappe.get_doc("Customer", {"custom_sap_customer_code": customer_code})
            new_doc = False
        else:
            customer_master_doc = frappe.new_doc("Customer")
            new_doc = True

        customer_master_doc.customer_name = customer_master['value'][i]['CardName'] if customer_master['value'][i]['CardName'] else ''
        customer_master_doc.disabled = 0 if customer_master['value'][i]['Valid'] == 'tYES' else 1
        customer_master_doc.custom_sap_customer_code = customer_code
        # try:
        #     customer_master_doc.custom_sap_customer_type = customer_master['value'][i]['U_Vtype'] if customer_master['value'][i]['U_Vtype'] else ''
        # except:
        #     customer_master_doc.custom_sap_customer_type = ''
        customer_master_doc.customer_group = frappe.get_value("Customer Group", {"custom_customer_group_code": customer_master['value'][i]['GroupCode']})
        customer_master_doc.custom_foreign_name = customer_master["value"][i].get(
            "CardForeignName", ""
        )
        customer_master_doc.save(ignore_permissions=True)
        frappe.db.commit()

        ShipToDefault = customer_master['value'][i].get('ShipToDefault', '')
        BillToDefault = customer_master['value'][i].get('BillToDefault', '')

        for address in customer_master['value'][i]['BPAddresses']:
            # if address['AddressType'] == 'bo_BillTo':
            # print (address['AddressName'])
            address_doc = frappe.new_doc("Address")
            address_doc.address_title = address['AddressName']
            address_doc.address_type = 'Billing' if address['AddressType'] == 'bo_BillTo' else 'Shipping'

            address_doc.address_line1 = address['Street'] if address['Street'] else 'NA'
            address_doc.address_line2 = address.get('Block', 'NA')
            address_doc.city = address['City'] if address['City'] else 'NA'
            address_doc.state = states.get(address.get("State", "NA"))
            address_doc.pincode = address.get('ZipCode', '')
            address_doc.country = frappe.get_value("Country", {"code": address.get('Country', '').lower()}, "name")
            address_doc.email_id = address.get('E_Mail', '')
            address_doc.phone = address.get('Phone1', '')
            address_doc.mobile_no = address.get('Cellolar', '')
            address_doc.fax = address.get('Fax', '')
            address_doc.website = address.get('WebSite', '')

            # Link the address to the supplier
            address_doc.append('links', {
                'link_doctype': 'Customer',
                'link_name': customer_master_doc
            })
            # print ('ShipToDefault : ',ShipToDefault,'BillToDefault : ', BillToDefault)
            # print (address['AddressType'], address['AddressName'])

            if (address['AddressType'] == 'bo_BillTo' and BillToDefault == address['AddressName']):
                address_doc.is_primary_address = 1
                customer_master_doc.supplier_primary_address = address_doc
                customer_master_doc.save()
                # print ('BillToDefault', address['AddressName'])
            if (address['AddressType'] == 'bo_ShipTo' and ShipToDefault == address['AddressName']):
                address_doc.is_shipping_address = 1

            address_doc.insert()
            # frappe.db.commit()

        for contact in customer_master['value'][i]['ContactEmployees']:
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
                'link_doctype': 'Customer',
                'link_name': customer_master_doc
            })

            contact_doc.insert()


# Update customer group
def update_bp_group():
    session = AuthenticateSAPB1()

    doc_settings = frappe.get_doc('SAP Settings')
    reqUrl = doc_settings.sap_b1_url+"BusinessPartnerGroups"

    response = session.request("GET", reqUrl, data=payload,  headers=headersList,verify=False)

    bp_group = dict(response.json())

    for i in range(len(bp_group['value'])):
        print (bp_group['value'][i])

        bp_data = bp_group['value'][i]

        if bp_data['Type'] == "bbpgt_CustomerGroup":
            if frappe.db.exists("Customer Group", {"custom_customer_group_code": bp_data['Code']}):
                bp_group_doc = frappe.get_doc("Customer Group", {"custom_customer_group_code": bp_data['Code']})
                new_doc = False
            else:
                bp_group_doc = frappe.new_doc("Customer Group")
                new_doc = True

            bp_group_doc.customer_group_name = bp_data['Name']
            bp_group_doc.custom_customer_group_code = bp_data['Code']

            if new_doc:
                bp_group_doc.insert()
            else:
                bp_group_doc.save()


        elif bp_data['Type'] == "bbpgt_VendorGroup":
            if frappe.db.exists("Supplier Group", {"custom_supplier_group_code": bp_data['Code']}):
                bp_group_doc = frappe.get_doc("Supplier Group", {"custom_supplier_group_code": bp_data['Code']})
                new_doc = False
            else:
                bp_group_doc = frappe.new_doc("Supplier Group")
                new_doc = True

            bp_group_doc.supplier_group_name = bp_data['Name']
            bp_group_doc.custom_supplier_group_code = bp_data['Code']

            if new_doc:
                bp_group_doc.insert()
            else:
                bp_group_doc.save()

    frappe.db.commit()
