import json
import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime, today
from frappe.utils import now
import time
import requests
import datetime
from frappe.query_builder.functions import Sum
from khanal_tech_integrations.unicommerce.client.unicommerce import UCClient


def AuthenticateUniware():
    """Compatibility wrapper backed by UCClient."""
    client = UCClient()
    client.login()
    access_token = client.token or ""
    facility = (client.facility_code or "").split(",")[0].strip() if client.facility_code else ""
    return type("UCAuth", (), {"access_token": access_token, "facility": facility})()



headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
    }


@frappe.whitelist()
def single_order():
    uniware_session = AuthenticateUniware()
    headersList['Authorization'] = 'bearer ' + uniware_session['access_token']
    headersList["facility"] = uniware_session['facility']
    order_payload ={
            "saleOrder": {
            "code": "HN-230712612123",
            "displayOrderCode": "HN-2307126121233",
            "displayOrderDateTime": "1689190642000",
            "channelProcessingTime": "1689190642000",
            "customerCode": "C00213",
            "customerName": "Test Account",
            "customerGSTIN": "123456789012341",
            "channel": "HN_SITE_IN",
            "notificationEmail": "shahilkhan.7139@gmail.com",
            "notificationMobile": "",
            "cashOnDelivery": True,
            "paymentInstrument": "CASH",
            "additionalInfo": "",
            "thirdPartyShipping": True,
            # "shippingProviders": [
            #     {
            #         "packetNumber": 0,
            #         "code": "string",
            #         "trackingNumber": "string"
            #     }
            # ],
            # "saleOrderItemCombinations": [
            #     {
            #         "combinationIdentifier": "string",
            #         "combinationDescription": "string"
            #     }
            # ],
            "addresses": [
                {
                "id": "19",
                "name": "ABC",
                "addressLine1": "ABC",
                "addressLine2": "XYZ",
                "city": "New Delhi",
                "state": "DL",
                "country": "India",
                "pincode": "110020",
                "phone": "9999999999"
                }
            ],
            "billingAddress": {
                "referenceId": "19"
            },
            "shippingAddress": {
                "referenceId": "19"
            },
            "saleOrderItems":[
            {
                "itemSku": "FGDC0049",
                "channelProductId": "FGDC0049",
                "channelSaleOrderItemCode": "W-04",
                "shippingMethodCode": "STD",
                "code": "ABC-19",
                "giftWrap": True,
                "giftMessage": "TEST",
                "totalPrice": "1000",
                "sellingPrice": "950",
                "prepaidAmount": "50",
                "discount": "100",
                "shippingCharges": "50",
                "giftWrapCharges": "20",
                "facilityCode": "Test_Facility"
            }],
            # "customFieldValues": [
            #     {
            #         "name": "string",
            #         "value": "string"
            #     }
            # ],
            # "currencyCode": "INR",
            # "taxExempted": True,
            # "cformProvided": True,
            # "fulfillmentTat": "1689190642000",
            # "verificationRequired": True,
            # "priority": 0,
            # "totalDiscount": 0,
            # "totalShippingCharges": 0,
            # "totalCashOnDeliveryCharges": 0,
            # "totalGiftWrapCharges": 0,
            # "totalStoreCredit": 0,
            # "totalPrepaidAmount": 0,
            # "useVerifiedListings": True
        }
    }
    req_Url = "https://khanalfoods.unicommerce.com/services/rest/v1/oms/saleOrder/create" #create_SalesOrder
    response = requests.request("POST", req_Url, data=json.dumps(order_payload),  headers=headersList,verify=False)
    print(response,'response')
    # status_code = response.status_code
    # print(status_code,'status_code')
    ResponseDict = dict(response.json())
    print(ResponseDict,'ResponseDict')
    pass






@frappe.whitelist()
def Get_itemTypeInventory():
    skuCode_payload = {   "skuCode": 'FGDC0032' } 
    uniware_session = AuthenticateUniware()
    inventory_payload = "https://khanalfoods.unicommerce.com/services/rest/v1/product/itemTypeInventory/get"
    headersList["facility"] = uniware_session['facility']
    headersList['Authorization'] = 'bearer ' + uniware_session['access_token']
    inventory_details_response = requests.request("POST", inventory_payload, data=json.dumps(skuCode_payload),  headers=headersList)
    Inventory_Dict = inventory_details_response.json()
    print(Inventory_Dict['inventoryDTOs'])

# bench --site dev.localhost execute khanal_tech_integrations.utils.ondc.create_order.Get_itemTypeInventory



@frappe.whitelist()
def Get_Sales_order():
    Code_payload = {"code":"HN-230712612"}
    uniware_session = AuthenticateUniware()
    payload = "https://khanalfoods.unicommerce.com/services/rest/v1/oms/saleorder/get"
    headersList["facility"] = 'khanalfoods'
    headersList['Authorization'] = 'bearer ' + uniware_session['access_token']
    sales_order_response = requests.request("POST", payload, data=json.dumps(Code_payload),  headers=headersList)
    sales_order = sales_order_response.json()
    print(sales_order['saleOrderDTO'])

# bench --site dev.localhost execute khanal_tech_integrations.utils.ondc.create_order.Get_Sales_order


# {
#    "code":"HN-230712612",
#    "displayOrderCode":"HN-230712612",
#    "channel":"HN_SITE_IN",
#    "source":"CUSTOM",
#    "displayOrderDateTime":1689190642000,
#    "status":"PROCESSING",
#    "created":1689190642000,
#    "updated":1689190808000,
#    "fulfillmentTat":1689363442000,
#    "notificationEmail":"",
#    "notificationMobile":"",
#    "customerGSTIN":"None",
#    "channelProcessingTime":1689190642000,
#    "cod":False,
#    "thirdPartyShipping":False,
#    "priority":0,
#    "currencyCode":"INR",
#    "customerCode":"None",
#    "billingAddress":{
#       "id":"45004249",
#       "name":"Anurup Jena",
#       "addressLine1":"House no. 4,Jaydev college road, Naharakanta",
#       "addressLine2":"200 metres from Siraj nursery",
#       "city":"Bhubaneshwar",
#       "district":"None",
#       "state":"OR",
#       "country":"IN",
#       "pincode":"752101",
#       "phone":"9439541494",
#       "email":"None",
#       "type":"None"
#    },
#    "addresses":[
#       {
#          "id":"45004249",
#          "name":"Anurup Jena",
#          "addressLine1":"House no. 4,Jaydev college road, Naharakanta",
#          "addressLine2":"200 metres from Siraj nursery",
#          "city":"Bhubaneshwar",
#          "district":"None",
#          "state":"OR",
#          "country":"IN",
#          "pincode":"752101",
#          "phone":"9439541494",
#          "email":"None",
#          "type":"None"
#       }
#    ],
#    "shippingPackages":[
#       {
#          "code":"KHAN126294",
#          "channelShipmentCode":"None",
#          "saleOrderCode":"HN-230712612",
#          "channel":"HN_SITE_IN",
#          "status":"READY_TO_SHIP",
#          "shippingPackageType":"LARGE_28_23",
#          "shippingProvider":"HN_ShipRocket",
#          "shippingCourier":"DTDC Surface",
#          "shippingMethod":"Standard-Prepaid",
#          "trackingNumber":"D61406490",
#          "trackingStatus":"None",
#          "courierStatus":"None",
#          "estimatedWeight":410.0,
#          "actualWeight":410.0,
#          "customer":"Anurup Jena",
#          "created":1689190807000,
#          "updated":1689312320000,
#          "dispatched":"None",
#          "delivered":"None",
#          "invoice":34688732,
#          "invoiceCode":"INS77892",
#          "invoiceDisplayCode":"INS77892",
#          "invoiceDate":1689312311000,
#          "noOfItems":1,
#          "city":"Bhubaneshwar",
#          "collectableAmount":220.0,
#          "collectedAmount":"None",
#          "paymentReconciled":False,
#          "podCode":"None",
#          "shippingManifestCode":"None",
#          "items":{
#             "FGHN0059":{
#                "itemSku":"FGHN0059",
#                "itemName":"HN Multifloral raw honey - 350G",
#                "itemTypeImageUrl":"None",
#                "itemTypePageUrl":"",
#                "quantity":1
#             }
#          },
#          "customFieldValues":[
            
#          ],
#          "shippingLabelLink":"https://unicommerce-channel-shippinglabels-in.s3.amazonaws.com/shipping-label-373502096-D61406490.pdf",
#          "irn":"None"
#       }
#    ],
#    "saleOrderItems":[
#       {
#          "id":62487298,
#          "shippingPackageCode":"KHAN126294",
#          "shippingPackageStatus":"READY_TO_SHIP",
#          "facilityCode":"khanalfoods",
#          "facilityName":"khanalfoods",
#          "alternateFacilityCode":"None",
#          "reversePickupCode":"None",
#          "shippingAddressId":45004249,
#          "packetNumber":0,
#          "combinationIdentifier":"None",
#          "combinationDescription":"None",
#          "type":"NORMAL",
#          "item":"None",
#          "shippingMethodCode":"STD",
#          "itemName":"HN Multifloral raw honey - 350G",
#          "itemSku":"FGHN0059",
#          "sellerSkuCode":"FGHN0059",
#          "channelProductId":"FGHN0059",
#          "imageUrl":"None",
#          "statusCode":"PICKING_FOR_INVOICING",
#          "code":"8906115980218",
#          "shelfCode":"ST-001-004-002",
#          "totalPrice":220.0,
#          "sellingPrice":220.0,
#          "shippingCharges":0.0,
#          "shippingMethodCharges":0.0,
#          "cashOnDeliveryCharges":0.0,
#          "prepaidAmount":0.0,
#          "voucherCode":"None",
#          "voucherValue":0.0,
#          "storeCredit":0.0,
#          "discount":0.0,
#          "giftWrap":"None",
#          "giftWrapCharges":0.0,
#          "taxPercentage":0.0,
#          "giftMessage":"",
#          "cancellable":True,
#          "editAddress":False,
#          "reversePickable":False,
#          "packetConfigurable":False,
#          "created":1689190642000,
#          "updated":1689312311000,
#          "onHold":False,
#          "saleOrderItemAlternateId":"None",
#          "cancellationReason":"None",
#          "cancelledBySeller":"None",
#          "pageUrl":"",
#          "color":"None",
#          "brand":"Himalyan Natives",
#          "size":"None",
#          "replacementSaleOrderCode":"None",
#          "bundleSkuCode":"None",
#          "customFieldValues":[
            
#          ],
#          "itemDetailFieldDTOList":[
            
#          ],
#          "hsnCode":"",
#          "totalIntegratedGst":10.48,
#          "integratedGstPercentage":5.0,
#          "totalUnionTerritoryGst":0.0,
#          "unionTerritoryGstPercentage":0.0,
#          "totalStateGst":0.0,
#          "stateGstPercentage":0.0,
#          "totalCentralGst":0.0,
#          "centralGstPercentage":0.0,
#          "maxRetailPrice":220.0,
#          "sellingPriceWithoutTaxesAndDiscount":209.52,
#          "batchDTO":{
#             "batchCode":"BA000266",
#             "batchFieldsDTO":{
#                "mrp":"None",
#                "cost":"None",
#                "vendorCode":"None",
#                "expiryDate":"None",
#                "mfd":"None",
#                "vendorBatchNumber":"H1L117C23D",
#                "coo":"None",
#                "boe":"None",
#                "status":"ACTIVE"
#             }
#          },
#          "shippingChargeTaxPercentage":0,
#          "tcs":0.0,
#          "ucBatchCode":"None",
#          "channelMrp":"None",
#          "channelExpiryDate":"None",
#          "channelVendorBatchNumber":"None",
#          "channelMfd":"None",
#          "countryOfOrigin":"None",
#          "expectedDeliveryDate":"None",
#          "itemDetailFields":"None",
#          "channelSaleOrderItemCode":"FGHN0059",
#          "effectiveTolerance":"None"
#       }
#    ],
#    "returns":[
      
#    ],
#    "customFieldValues":[
      
#    ],
#    "cancellable":True,
#    "reversePickable":False,
#    "packetConfigurable":False,
#    "cFormProvided":False,
#    "totalDiscount":"None",
#    "totalShippingCharges":"None",
#    "additionalInfo":"None",
#    "paymentInstrument":"None",
#    "paymentDetail":"None",
#    "saleOrderMetadata":[
      
#    ]
# }



# {
#     "successful": false,
#     "message": null,
#     "errors": [
#         {
#             "code": 1000,
#             "fieldName": null,
#             "description": "please fill valid value",
#             "message": "Unrecognized field \"source\" (Class com.uniware.core.api.model.WsSaleOrder), not marked as ignorable\n at [Source: org.apache.catalina.connector.CoyoteInputStream@14a43fce; line: 6, column: 27] (through reference chain: com.uniware.core.api.saleorder.CreateSaleOrderRequest[\"saleOrder\"]->com.uniware.core.api.model.WsSaleOrder[\"source\"])",
#             "errorParams": null
#         }
#     ],
#     "warnings": null
# }