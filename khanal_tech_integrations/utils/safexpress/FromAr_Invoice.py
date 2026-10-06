import frappe
import json
import requests

from khanal_tech_integrations.utils.sap import AuthenticateSAPB1
from khanal_tech_integrations.utils.safexpress.auth import AuthenticateSafexpress
import re
from khanal_tech_integrations.utils.logistics.alert_invoice import get_single_lineitem,updating_email,WareHouseUpdate
import base64
import time
from PIL import Image
from io import BytesIO
import os
from frappe.utils import add_to_date
from khanal_tech_integrations.utils.safexpress.attachpod_to_sap import Update_waybill_and_filePath
from khanal_tech_integrations.utils.safexpress.automated_invoice_attach import Saved_InvDoc

headersList = {
        "Accept": "*/*",
        "User-Agent": "Khanal Tech",
        "Content-Type": "application/json" ,
         "Prefer": "odata.maxpagesize=900",
    }

payload={}
#  bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.POD_Waybill_Update
# khanal_tech_integrations/utils/safexpress/FromAr_Invoice.py


@frappe.whitelist()
def POD_Waybill_Update():
    session = AuthenticateSAPB1()
    Today = frappe.utils.nowdate()
    FilterDate = add_to_date(Today,days=-369)
    print(FilterDate,'FilterDate')

    doc_settings = frappe.get_doc('SAP Settings')
    # reqUrl = doc_settings.sap_b1_url+"BusinessPartners?$filter(UpdateDate ge '{FilterDate}')" 
    req_url = f"{doc_settings.sap_b1_url}Invoices?$filter=UpdateDate ge '{FilterDate}' and U_TrackingNo ne null"

    # Modified_count_url = reqUrl.format(FilterDate=FilterDate)
    response = session.request("GET", req_url, data=payload,  headers=headersList,verify=False)
    inv_master = dict(response.json())
    # print (inv_master)
    
    # for i in range(1,2):
    while inv_master.get('odata.nextLink', None):
        update_inv_master(inv_master)
        print (inv_master['odata.nextLink'])
        next_url = doc_settings.sap_b1_url+inv_master['odata.nextLink']
        response = session.request("GET", next_url, data=payload, headers=headersList, verify=False)
        inv_master = dict(response.json())
        
    update_inv_master(inv_master)

def update_inv_master(inv_master):

    for i in range(len(inv_master['value'])):
        inv_DocEntry = inv_master['value'][i]['DocEntry']
        # print(inv_master['value'][i],'inv_DocEntry')
        if frappe.db.exists("SAP AR Invoice Detail", inv_DocEntry):
            print('present DocEntry',inv_DocEntry)
            Update_waybill_and_filePath(inv_DocEntry)
            
        else:
            print('not present DocEntry',inv_DocEntry)
            Saved_InvDoc(inv_master['value'][i])

    pass

import pandas as pd



# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.Update_Pod_FormWaybill
def Update_Pod_FormWaybill():
    # df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/Tracking Needed to Update.xlsx','KAIN23 & KAIN24')
    df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/Patch Ar Invoice .xlsx','Sheet2')
    print(df.columns,'df.columns')
    filtered_df = df[df['Pod Link'].isnull()]
    print(filtered_df)
    for i, row in filtered_df.iterrows():
        tracking_info = row['Portal tracking']
        Invoice_no = row['Internal Number']
        pod_link = Get_PodDocument(tracking_info,Invoice_no)
        print(pod_link,'pod_link')
        
        # Update the original DataFrame with the new Pod Link
        df.at[i, 'Pod Link'] = pod_link

    new_file_path = '/Users/shahilkhan/Desktop/WorkSpace/Export/Update error message.xlsx'
    df.to_excel(new_file_path, index=False)
    print(f"Updated DataFrame saved to {new_file_path}")


    pass

# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.Patch_Pod_SAP

def Patch_Pod_SAP():
    # df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Export/Tracking Needed to Update.xlsx','KAIN23 & KAIN24')
    df = pd.read_excel('/Users/shahilkhan/Downloads/Workspace/POD Local/Local POD 22 & 23.xlsx','Sheet1')
    # print(df.columns,'df.columns')
    
    filtered_df = df[~df['Active'].isin( ['Yes'])]
    # print(filtered_df)
    for i, row in filtered_df.iterrows():
        DocEntry = row['Internal Number']
        Invoice_no = row['Document Number']
        Pod_Link = row['Pod Link']
        Patch_message = Patch_POD_Link(DocEntry,Invoice_no,Pod_Link)
    #     print(pod_link,'pod_link')
        
    #     # Update the original DataFrame with the new Pod Link
        df.at[i, 'Patch Message Part 1'] = Patch_message

    new_file_path = '/Users/shahilkhan/Desktop/WorkSpace/Export/Patch Local Part 3 For No .xlsx'
    df.to_excel(new_file_path, index=False)
    # print(f"Updated DataFrame saved to {new_file_path}")


def Patch_POD_Link(DocEntry,Invoice_no,Pod_Link):
    
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')
    Url = doc_settings.sap_b1_url + "Invoices({inv_docentry})"
    reqUrl = Url.format(inv_docentry=DocEntry)
    try:
        payload = json.dumps(
            {
                "U_TN": "Local delivery partner",
                "TransportationCode": 4,
                "U_TrackingNo": 'Local Transport',
                "U_Pod_Link": Pod_Link,
            })
        response = session.request("PATCH", reqUrl, headers=headersList, data=payload, verify=False)
        
        print(DocEntry,Invoice_no,response.status_code,Pod_Link,'\n\n')
        if response.status_code == 204:
            return response.status_code
        else:
            error_message = response.json().get('error', {}).get('message', {}).get('value', 'Unknown error')
            print(error_message)
            return error_message

            # return response.text
        # print(response)
        
    except Exception as e:
        print(f"An error occurred while processing docentry {DocEntry}: {str(e)}")




def Get_PodDocument(tracking_info,Invoice_no):
    try:
        safexpress_session = AuthenticateSafexpress()
        headersList["x-api-key"] = safexpress_session.api_key
        headersList['authorization'] = safexpress_session.access_token
        headersList['Identifier'] = safexpress_session.identifier
        payload = {}
        req_url = safexpress_session.pod_url + str(tracking_info)
        response = requests.request("GET", req_url, headers=headersList, data=payload)
        print(response,'AuthenticateSafexpress')
        if response.status_code == 200:
            resp_json = response.json()

            # Check if 'data' key is present in the response
            if 'data' in resp_json and resp_json['data'] is not None:
                base64_string = resp_json['data'].get('base64String')
                if base64_string is not None and base64_string != "null":
                    print('base64_string is not none')
                    content_file = resp_json['data']['base64String']
                    tiff_data = base64.b64decode(content_file)
                    timestamp = str(int(time.time()))
                    file_name = str(Invoice_no) + '_' + timestamp + '.tiff'

                    # url="https://gmupurbzq9.execute-api.eu-north-1.amazonaws.com/beta/testingbucketsample/"+file_name #!Test
                    url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/" + file_name  #!Live

                    headers = {
                        'Content-Type': 'image/tiff',
                    }
                    if response.status_code == 200:
                        upload_response = requests.put(url, headers=headers, data=tiff_data)
                        if upload_response.status_code not in (200, 201):
                            print(f"S3 upload failed: {upload_response.status_code} — {upload_response.text[:200]}")
                            return None
                        # File_url='https://testingbucketsample.s3.eu-north-1.amazonaws.com/'+file_name #!Test
                        File_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + file_name  #!Live
                        return File_url
                else:
                    error = resp_json['data'].get('error')

                    return error
            else:
                pass
        else:
            print(response.status_code, 'is because of', response.text)
            return response.text
    except Exception as e:
        print(f"An error occurred: {str(e)}")












# def ManullyUpdate_POD():
#     getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2022'
    
#     # List all files in the directory
#     files = os.listdir(getFile)
#     print(len(files))
#     # Filter out only the .tiff files


#     FileName=''
#     df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'KAIN22')
#     # print(df['Document Number'].values,'df')
#     for pof_file in files:
#         # print(pof_file,'pof_file')
#         file_name_without_ext = os.path.splitext(pof_file)[0].strip('.')
#         # print(f"Processing file: {pof_file} as {file_name_without_ext}")
#         # if file_name_without_ext in df['Document Number'].values:
#         #     print(f"Match found for: {file_name_without_ext}")
#         for i, row in df.iterrows():
#             DocumntNumber = str(row['Document Number'])  
#             if file_name_without_ext == DocumntNumber:
#                 print(f"Match found for: {file_name_without_ext} as DocEntry is {row['Internal Number']}")
#                 file_path = os.path.join(getFile, pof_file)
#                 with Image.open(file_path) as img:
#                     img_data = img.tobytes()
#                     # print(img_data,'img_data')
#                     file_name = f"{str(row['Internal Number'])}.jpeg" 
#                     url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/" + file_name  #!Live

              
#                     headers = {
#                         'Content-Type': 'image/jpeg',
#                     }
#                     aws_response = requests.put(url, headers=headers, data=img_data)




#         # file_path = os.path.join(getFile, pof_file)
#         # print(file_path)
        
#     #     # Open the .tiff file
#         # with Image.open(file_path) as img:
#         #     # Show image (optional)
#         #     img.show()
            
#         #     # If you want to get the content in some other way, like text, you'll need OCR
#         #     # For now, let's just get the image data itself
#         #     img_data = img.tobytes()
            
#         #     print(f"Content of {tiff_file}:")
#         #     print(img_data[:100])  # Print the first 100 bytes as a sample
#         #     return None
            

#     pass


# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.ManullyUpdate_POD

# !------------Working
# def resize_image(img, max_size=(1024, 1024)):
#     """Resize the image to a maximum size."""
#     img.thumbnail(max_size, Image.LANCZOS)
#     return img

# def compress_image(img, quality=85):
#     """Compress the image and return the bytes."""
#     img_byte_arr = BytesIO()
#     img.save(img_byte_arr, format='JPEG', quality=quality)
#     return img_byte_arr.getvalue()


# def ManullyUpdate_POD():
#     getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2022'
    
#     # List all files in the directory
#     files = os.listdir(getFile)
#     print(len(files))
#     # Filter out only the .tiff files
#     df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'KAIN22')
#     # print(df['Document Number'].values,'df')
#     for pof_file in files:
#         # print(pof_file,'pof_file')
#         file_name_without_ext = os.path.splitext(pof_file)[0].strip('.')
#         for i, row in df.iterrows():
#             DocumntNumber = str(row['Document Number'])  
#             if file_name_without_ext == DocumntNumber:
#                 print(f"Match found for: {file_name_without_ext} as DocEntry is {row['Internal Number']}")
#                 file_path = os.path.join(getFile, pof_file)
#                 # print(file_name_without_ext,'file_name_without_ext')
#                 with Image.open(file_path) as img:
#                     img = resize_image(img)  # Resize the image
#                     img_data = compress_image(img)  


#                     # print(img_data,'img_data')
#                     file_name = f"{str(row['Internal Number'])}.jpg" 
#                     url = "https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/" + file_name  #!Live

              
#                     headers = {
#                         'Content-Type': 'image/jpg',
#                     } 
#                     aws_response = requests.put(url, headers=headers, data=img_data)
#                     print(aws_response,'aws_response')
#                     File_url = 'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/' + file_name  #!Live
#                     print(File_url)
#                     df.at[i, 'Pod Link'] = File_url

#     new_file_path = '/Users/shahilkhan/Desktop/WorkSpace/Export/Local POD Part 1.xlsx'
#     df.to_excel(new_file_path, index=False)
#     print(f"Updated DataFrame saved to {new_file_path}")

# !End Working------------------



#
def ManullyCHECK_POD():
    getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2023'
    
    # List all files in the directory
    files = os.listdir(getFile)
    print(len(files))
    # Filter out only the .tiff files
    file_names=[]

    df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'KAIN23')
    # print(df['Document Number'].values,'df')
    for pof_file in files:
        # print(pof_file,'pof_file')
        file_name_without_ext = os.path.splitext(pof_file)[0].strip('.')
        file_names.append(file_name_without_ext)


    file_names_df = pd.DataFrame(file_names, columns=['FileNameWithoutExt'])

    new_file_path = '/Users/shahilkhan/Desktop/WorkSpace/Export/Local POD CHECKING 2023 Part 1.xlsx'
    file_names_df.to_excel(new_file_path, index=False)
    print(f"Updated DataFrame saved to {new_file_path}")

# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.ManullyCHECK_POD



# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.ManullyUpdate_POD
def resize_image(img, max_size=(1024, 1024)):
    """Resize the image to a maximum size."""
    img.thumbnail(max_size, Image.LANCZOS)
    return img

def compress_image(img, quality=85):
    """Compress the image and return the bytes."""
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=quality)
    return img_byte_arr.getvalue()

def merge_images(images):
    """Merge a list of images into a single image."""
    widths, heights = zip(*(img.size for img in images))
    total_height = sum(heights)
    max_width = max(widths)
    
    merged_image = Image.new('RGB', (max_width, total_height))
    
    y_offset = 0
    for img in images:
        merged_image.paste(img, (0, y_offset))
        y_offset += img.height
    
    return merged_image



def ManullyUpdate_POD():
    getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2023'
    
    # List all files in the directory
    files = os.listdir(getFile)
    print(len(files))
    
    # Load the Excel file
    df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'INTSER23')

    for i, row in df.iterrows():
        DocumntNumber = str(row['Document Number'])
        matching_files = [f for f in files if os.path.splitext(f)[0].strip('.') == DocumntNumber]

        if matching_files:
            print(f"Match found for: {DocumntNumber} as DocEntry is {row['Internal Number']}")
            images = []
            
            for pof_file in matching_files:
                file_path = os.path.join(getFile, pof_file)
                with Image.open(file_path) as img:
                    img = resize_image(img)  # Resize the image
                    images.append(img)

            if len(images) > 1:
                # Merge images if more than one
                merged_image = merge_images(images)
            else:
                # If only one image, no need to merge
                merged_image = images[0]
            
            # Convert the merged image to bytes
            img_byte_arr = BytesIO()
            merged_image.save(img_byte_arr, format='PDF')
            img_data = img_byte_arr.getvalue()

            # Upload to AWS S3
            timestamp = str(int(time.time()))
            file_name = f"{DocumntNumber}_{timestamp}.pdf"
            url = f"https://tg31l9q380.execute-api.us-west-1.amazonaws.com/dev/khanalfoods-fileupload-bucket/{file_name}"  #!Live
            
            headers = {
                'Content-Type': 'application/pdf',
            } 
            aws_response = requests.put(url, headers=headers, data=img_data)
            print(aws_response.status_code, 'aws_response')

            if aws_response.status_code == 200:
                File_url = f'https://khanalfoods-fileupload-bucket.s3.us-west-1.amazonaws.com/{file_name}'  #!Live
                print(File_url)
                df.at[i, 'Pod Link'] = File_url

    # Optionally, save the updated DataFrame to a new Excel file
    df.to_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Updated_Local Tracking INTSER23 Part 1.xlsx', index=False)


# def ManullyUpdate_POD():
#     getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2022'
    
#     # List all files in the directory
#     files = os.listdir(getFile)
#     print(len(files))
    
#     # Filter out only the .tiff files
#     df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'KAIN22')

#     for i, row in df.iterrows():
#         DocumntNumber = str(row['Document Number'])
#         matching_files = [f for f in files if os.path.splitext(f)[0].strip('.') == DocumntNumber]

#         if matching_files:
#             print(f"Match found for: {DocumntNumber} as DocEntry is {row['Internal Number']}")
#             images = []
            
#             for pof_file in matching_files:
#                 file_path = os.path.join(getFile, pof_file)
#                 with Image.open(file_path) as img:
#                     img = resize_image(img)  # Resize the image
#                     images.append(img)

#             if len(images) > 1:
#                 # Merge images if more than one
#                 merged_image = merge_images(images)
#             else:
#                 # If only one image, no need to merge
#                 merged_image = images[0]
            
#             # Save the final image as a PDF
#             output_path = f"/Users/shahilkhan/Downloads/Workspace/pdf Pod/{DocumntNumber}_merged.pdf"
#             merged_image.save(output_path, "PDF", quality=85)
#             print(f"PDF saved as {output_path}")


# def resize_image(img, max_size=(1024, 1024)):
#     """Resize the image to a maximum size."""
#     img.thumbnail(max_size, Image.LANCZOS)
#     return img

# def ManullyUpdate_POD():
#     getFile = '/Users/shahilkhan/Downloads/LOCAL POD_S/2022'
    
#     # List all files in the directory
#     files = os.listdir(getFile)
#     print(len(files))
    
#     # Filter out only the .tiff files
#     df = pd.read_excel('/Users/shahilkhan/Desktop/WorkSpace/Ecom/Tracking Invoice with Waybill.xlsx', 'KAIN22')

#     for i, row in df.iterrows():
#         DocumntNumber = str(row['Document Number'])
#         matching_files = [f for f in files if os.path.splitext(f)[0].strip('.') == DocumntNumber]

#         if matching_files:
#             print(f"Match found for: {DocumntNumber} as DocEntry is {row['Internal Number']}")
#             images = []
            
#             for pof_file in matching_files:
#                 file_path = os.path.join(getFile, pof_file)
#                 with Image.open(file_path) as img:
#                     img = resize_image(img)  # Resize the image
#                     img = img.convert('RGB')  # Convert to RGB (required for saving as PDF)
#                     images.append(img)

#             if images:
#                 # Save the images as a single PDF
#                 output_pdf_path = f"/Users/shahilkhan/Desktop/WorkSpace/Ecom/{DocumntNumber}_merged.pdf"
#                 images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
#                 print(f"PDF saved as {output_pdf_path}")


import pandas as pd
# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.FromAr_Invoice.patch_invoice_data

def patch_invoice_data():
    filename='/Users/shahilkhan/Downloads/Workspace/SAP Safexpress Miss match.xlsx'
    df_unique=pd.read_excel(filename,'Sheet3')
    print(df_unique)
    session = AuthenticateSAPB1()
    doc_settings = frappe.get_doc('SAP Settings')

    for _, row in df_unique.iterrows():
        doc_entry = row['Internal Number']
        
    #     # Prepare the PATCH URL
        patch_url = doc_settings.sap_b1_url + f"Invoices({doc_entry})"
        
    #     # Prepare the data for PATCH request
        payload = {
            "U_TN": 'SafeExpress',  # The new U_TN value
            "TransportCode": 1  # The new TransportCode
        }

    #     # Send PATCH request
        response = session.request("PATCH", patch_url, json=payload, headers=headersList, verify=False)
        
    #     # Check the response
        if response.status_code == 204:
            print(f"Invoice {doc_entry} updated successfully")
            message=f"Invoice {doc_entry} updated successfully"
        else:
            print(f"Failed to update Invoice {doc_entry}: {response.text}")

    # return "Patch Process Completed"