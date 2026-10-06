#%%
import requests
import frappe


def authorize():
    doc = frappe.get_doc('Cashfree Settings')
    default_url     = frappe.db.get_single_value('Cashfree Settings', 'cashfree_url')
    client_id       = frappe.db.get_single_value('Cashfree Settings', 'client_id')
    client_secret   = frappe.db.get_single_value('Cashfree Settings', 'client_secret')

    url = default_url + "/payout/v1/authorize"

    payload={}
    headers =           {
                    'X-Client-Id'       : client_id ,
                    'X-Client-Secret'   : client_secret
                        }

    response = requests.request("POST", url, headers=headers, data=payload)

    
    resp_json = response.json()
    #print(resp_json)
    #print (resp_json['data']['token'])
    return resp_json['data']['token']
    
# %%
def verify(token=None):
    #token = authorize()
    url = "https://payout-gamma.cashfree.com/payout/v1/verifyToken"

    payload={}
    headers =   {
                    'Authorization': 'Bearer ' + str(token) #ab9JCVXpkI6ICc5RnIsICN4MzUIJiOicGbhJye.ab9JCSUVVQflEUBRVVPlVQQJiOiIWdzJCLzYTN0gzNwcjNxojI0FWaiwyM2ETN4cDM3YTM6ICc4VmIsITM4kjNyojIklEduV2ZhJCLiQlTFJlUVN0XUV1TZFEUiojIsVmbuFGajJCLiQVVPlVQQJiOiQnbldWYiwiI34yMz4SNwIjL5QjI6ICcpJCLlNHbhZmOis2Ylh2QlJXd0Fmbnl2ciwiMxgTO2IjOiQWS05WdvN2YhJCLiADMWZVV3cEU4g0MzU1S3YVT3U0Q0MjM1YjMGNkI6ICZJRnbllGbjJye.abmE5LoC05Q6xVUwBHsQqRnnpxcEZSvJWuFZTwmg6JDmUx9qR93MgTpF3YXL9CpeMe'
                }

    response = requests.request("POST", url, headers=headers, data=payload)
    print(headers)

    print(response.text)

# %%
