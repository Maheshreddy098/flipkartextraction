#%%
# import frappe
# from frappe.utils.file_manager import get_file_path, get_files_path
# from frappe.client import attach_file
# from frappe.utils.file_manager import save_file
# from frappe.utils import file_manager
#%%

import requests
from PIL import Image
from io import BytesIO
import img2pdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import base64


# %%
def Pod_using_URL():
    """Get single pod details
    """
    url = 'http://192.168.68.49:8000/files/Sample_eee.tiff'
    response = requests.get(url, verify=False)
    # Check if the request was successful
    if response.status_code == 200:
        tiff_content = response.content
        # Convert TIFF content to JPEG
        jpg_bytes = convert_tiff_to_jpeg(tiff_content)
        jpg_file_name = "Sample_Pod.jpg"
        with open(jpg_file_name, "wb") as jpg_file:
            jpg_file.write(jpg_bytes)

        print("Conversion complete. JPEG saved as", jpg_file_name)
        return jpg_bytes
        
    else:
        print("Failed to retrieve the TIFF content from the URL.")



def convert_tiff_to_jpeg(tiff_content):
    try:
        # Convert TIFF content to JPEG using Pillow
        image = Image.open(BytesIO(tiff_content))
        jpeg_bytes = BytesIO()
        # Save the TIFF image as JPEG
        image.save(jpeg_bytes, format="JPEG")
        return jpeg_bytes.getvalue()
    except Exception as e:
        print("Error while converting TIFF to JPEG:", e)
        return b''

Pod_using_URL()
# bench --site dev.localhost execute khanal_tech_integrations.utils.safexpress.pod_test.Get_Single_Pod






#%%
headersList = {"Accept": "*/*",
                "User-Agent": "KhanalTech",
                "Content-Type": "application/json" ,
                "Accept-Encoding":"gzip, deflate, br",
                "Connection":"keep-alive",
                "x-api-key":'cr4Hmts1Za9jqIjUydRCa2CRi7GsdXCR5OANn0dZ',
                "Identifier":'khanalfoods.com',
                "authorization":'eyJraWQiOiJ4ZStWNmxscE9XWHM4NitFZ1JhWTdSTkIwdzhFZGNWR1UwZm5qWWw3bkNzPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiJmbXFhZGxjZnJjb2N1bmFjbHJpbGh1NGxtIiwidG9rZW5fdXNlIjoiYWNjZXNzIiwic2NvcGUiOiJzZXJ2ZXJcL3dheWJpbGxhcHBzIiwiYXV0aF90aW1lIjoxNjkyMjY2NzEyLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGgtMS5hbWF6b25hd3MuY29tXC9hcC1zb3V0aC0xXzJrR25OTFQwMiIsImV4cCI6MTY5MjM1MzExMiwiaWF0IjoxNjkyMjY2NzEyLCJ2ZXJzaW9uIjoyLCJqdGkiOiIzNGY5YTg3ZS1mOGNiLTRlZTQtYTM0ZC03Mjk1ODViOTQ5OWMiLCJjbGllbnRfaWQiOiJmbXFhZGxjZnJjb2N1bmFjbHJpbGh1NGxtIn0.08U6znJrfvs9J9X0gEjJ1zhHuLT-L-AJJ4SgsOyh2J4zD8O1MuhbpEDKlFr-dL1ZFSbWm4t4GYZby_49W4YOqmszUq8EZvoD3ZEcYj8xlZ5Oeg2kGh5S-8s3si-xsmv5v3eiaUk4X9K5CkG-WvesWduUvXIuyZz4sdCgJqTxTGN-Mdp4WE4Y3S2ECeMSyFUC40W0FrBUwWHllOeMlFcCpEmeN-UOnV0x4MSPIkmWmXnr1QNF5s-oDX35dHsCbaP2sIZTZHAb6Ggvez1GqqLXNz8u5bzHcyDyK6cI0w9WcLkPupY9dIwPQqnsB_7gnkkbZtEH88aTo7TzxdUF7jv7-g',
                }

def Pod_using_Base64():
    payload = {}
    url="https://apigateway.safexpress.com/bkg/booking/pod/100006084193"
    response = requests.request("GET", url, headers=headersList, data=payload)

    print(response)
    resp_json = response.json()
    base64_image = resp_json['data']['base64String']
    decoded_image = base64.b64decode(base64_image)
    pil_image = Image.open(BytesIO(decoded_image))
    output_path = "/Users/shahilkhan/Desktop/Sample_testing123.jpg"
    pil_image.save(output_path, "JPEG")
    # pil_image.show()
    image_content = pil_image.tobytes()
    print(image_content,'image_content')
    image_content.save()
    # output_path = "/Users/shahilkhan/Desktop/content.txt"

    # print('file saved in location',output_path)
    # file_obj = file_manager.save_file('pdf_file_name.pdf', pil_image, 'SAP Item Master', 'eee')

    # file_path = get_file_path(file_obj.file_url)
    # doc=frappe.get_doc('SAP Item Master','eee')
    # doc.qr_code = file_path
    # doc.save()
    # frappe.db.commit()
    pass
    # Save the PIL Image as PNG
    # pil_image.save("output_image1.png", "PNG")

    # # Convert the PIL Image to PDF using ReportLab
    # pdf_canvas = canvas.Canvas("output_image_reportlab1.pdf")
    # pdf_canvas.drawImage("output_image.png", 0, 0, width=pil_image.width, height=pil_image.height)
    # pdf_canvas.save()


Pod_using_Base64()


# %%
from PIL import Image

def testing():
    response = requests.get('http://beta.khanaltech.com/files/image%20(1).tif', verify=False)
    image = Image.open(BytesIO(response.content))
    # image.show()
    # image_content = image.tobytes()  # This gives you the raw pixel data
    # print(image_content)
    # You can also convert the content to a different format, like a NumPy array
    import numpy as np
    image_array = np.array(image)  # Convert the image to a NumPy array

    # If you want to see the content (pixel values) of the image, you can print the array
    print(image_array)
    pass

testing()
# %%
