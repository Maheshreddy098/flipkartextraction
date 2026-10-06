import requests
import json
import frappe
from frappe.utils import add_to_date, now, get_datetime, now_datetime
import re

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1

headersList = {
                "Accept": "*/*",
                "User-Agent": "Khanal Tech",
                "Content-Type": "application/json" 
            }

@frappe.whitelist()
def Update_Tracking_by_INV(days: int = 20):
    """
    Update Safexpress tracking for delivery notes via invoice numbers.
    
    Args:
        days: Lookback window in days (default 20, can be up to 365 for one year).
    """
    days = min(int(days), 365)  # Cap at one year
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today, days=-days)
    delivery_notes = frappe.db.get_list(
        'SAP Delivery Notes',
        filters={
            'tracking_id': ['in', ['', None]],
            'transporter_name': ['in', ['', None]],
            'updated': ['>', FilterDate]
        },
        pluck="docentry",
        order_by="updated desc",
        limit_page_length=10000,  # Increase limit for one-year lookback
    )
    print(len(delivery_notes), 'length of delivery notes')
    
    processed = 0
    failed = 0
    
    for Docentry in delivery_notes:
        getDoc = frappe.db.get_list('SAP AR Invoice', filters={'ref_delivery_note': Docentry} ,pluck='docnum')
        # print(getDoc)
        if len(getDoc) == 0:
            # The list is empty, do something
            pass
        else:
            # The list is not empty, do something
            # print('else check safe',getDoc)
            for doc in getDoc:
                print(doc)
                url = "https://webs.safexpress.com:8443/SafexWaybillTracking/webresources/tracking/all"

                # prefixes = ["KAIN24", "AR2024", "HRIN24", "MHIN24","KAIN23", "AR2023", "HRIN23", "MHIN23","Manual"]
                prefixes = ["KAIN24", "AR2024", "HRIN24", "MHIN24","KAIN23", "AR2023", "HRIN23", "MHIN23"]
                for prefix in prefixes:
                    # if prefix == "Manual":
                    #     formatted_doc = str(doc)
                    # else:
                    formatted_doc = f"{prefix}/{doc}"
                    payload = {
                        "docNo": formatted_doc,
                        "docType": "INV"
                    }

                    try:
                        response = requests.post(
                            url, 
                            headers=headersList, 
                            json=payload,
                            verify=False,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            if result.get('shipment') and 'waybill' in result['shipment']:
                                DNList = frappe.get_doc('SAP Delivery Notes', Docentry)
                                waybill = result['shipment']['waybill']
                                print(f"Found waybill {waybill} for DN {Docentry}")
                                
                                DNList.transporter_name = "Safexpress"
                                DNList.tracking_id = waybill
                                DNList.shipping_details = result
                                
                                if 'shipment' in result and 'status' in result['shipment']:
                                    DNList.delivery_status = result['shipment']['status']
                                else:
                                    DNList.delivery_status = 'Error'
                                
                                DNList.save()
                                frappe.db.commit()
                                
                                try:
                                    logistics_detail_PATCH(
                                        Docentry=Docentry,
                                        TrackingNo=result['shipment']['waybill']
                                    )
                                    processed += 1
                                    break  # Exit prefix loop on success
                                except Exception as patch_error:
                                    frappe.log_error(
                                        f"Error patching SAP for DN {Docentry}: {str(patch_error)}",
                                        "Safexpress Tracking Patch"
                                    )
                                    failed += 1
                        else:
                            print(f"Failed for prefix {prefix} (DN {Docentry}): {response.status_code} - {response.text}")
                    except Exception as e:
                        error_msg = f"Error processing DN {Docentry} with prefix {prefix}: {str(e)}"
                        frappe.log_error(error_msg, "Safexpress Tracking")
                        print(error_msg)
                        failed += 1

    print(f"Tracking update complete: Processed={processed}, Failed={failed}")
    return {"processed": processed, "failed": failed}

def logistics_detail_PATCH(Docentry=None, TrackingNo=None):
    """Patch SAP B1 Delivery Note with tracking information."""
    try:
        session = AuthenticateSAPB1()
        doc_settings = frappe.get_doc('SAP Settings')
        Url = doc_settings.sap_b1_url + "DeliveryNotes({Docentry})"
        reqUrl_modified = Url.format(Docentry=Docentry)
        payload = json.dumps({
            "U_TN": "Safexpress",
            "U_TrackingNo": TrackingNo,
        })
        
        response = session.request(
            "PATCH",
            reqUrl_modified,
            headers=headersList,
            data=payload,
            verify=False,
            timeout=30
        )
        
        if response.status_code in [200, 204]:
            print(f"Successfully patched DN {Docentry} with tracking {TrackingNo}")
            return 'DN Patched'
        else:
            error_msg = f"SAP patch failed for DN {Docentry}: {response.status_code} - {response.text}"
            frappe.log_error(error_msg, "Safexpress SAP Patch")
            print(error_msg)
            return None
    except Exception as e:
        error_msg = f"Error patching SAP for DN {Docentry}: {str(e)}"
        frappe.log_error(error_msg, "Safexpress SAP Patch")
        print(error_msg)
        return None








@frappe.whitelist()   
def Update_Tracking_by_WayBill():
    """Update Safexpress tracking for delivery notes using existing waybills."""
    delivery_notes = frappe.db.get_list(
        'SAP Delivery Notes',
        filters={
            'transporter_name': ['=', 'Safexpress'],
            'tracking_id': ['!=', '']
        },
        pluck="docentry",
        limit_page_length=10000,
    )
    print(len(delivery_notes), 'length of delivery notes with waybills')
    
    processed = 0
    failed = 0
    
    for Docentry in delivery_notes:
        try:
            print(Docentry, 'Docentry')
            doc = frappe.get_doc("SAP Delivery Notes", Docentry)
            
            if not doc.tracking_id:
                continue
                
            url = "https://webs.safexpress.com:8443/SafexWaybillTracking/webresources/tracking/all"
            payload = json.dumps({
                "docNo": doc.tracking_id,
                "docType": "WB"
            })
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.request(
                "POST",
                url,
                headers=headers,
                data=payload,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('shipment') and result['shipment'].get('message') != 'Invalid Request':
                    doc.shipping_details = result
                    
                    if result['shipment'].get('result') == 'success':
                        doc.shipping_details = result
                        doc.delivery_status = result['shipment'].get('status', 'Unknown')
                    else:
                        doc.delivery_status = 'Data Not Found'
                    
                    doc.save()
                    frappe.db.commit()
                    processed += 1
                    print(f"Updated DN {Docentry}: {doc.delivery_status}")
                else:
                    print(f"Invalid response for DN {Docentry}")
                    failed += 1
            else:
                error_msg = f"API error for DN {Docentry}: {response.status_code} - {response.text}"
                frappe.log_error(error_msg, "Safexpress Tracking by Waybill")
                print(error_msg)
                failed += 1
        except Exception as e:
            error_msg = f"Error processing DN {Docentry}: {str(e)}"
            frappe.log_error(error_msg, "Safexpress Tracking by Waybill")
            print(error_msg)
            failed += 1
    
    print(f"Tracking update by waybill complete: Processed={processed}, Failed={failed}")
    return {"processed": processed, "failed": failed}





# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_INV
# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_WayBill
# bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_INV
# bench --site khanaltech.com execute  --args "{ '365' }"  khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_INV

# bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_WayBill
# bench --site khanaltech.com execute khanal_tech_integrations.utils.safexpress.tracking.Update_Tracking_by_WayBill