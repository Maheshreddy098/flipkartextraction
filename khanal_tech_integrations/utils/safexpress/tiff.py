#%%
import requests
from PIL import Image
from io import BytesIO
import os
# %%
im = Image.open('/Users/shahilkhan/Desktop/tempfile.tiff')
# %%
im.save('/Users/shahilkhan/Desktop/outfile.jpg', "JPEG", quality=100)
# %%

response = requests.get('http://beta.khanaltech.com/files/image%20(1).tif', verify=False)
im = Image.open(response.content)

# %%


from PIL import Image
  
# urllib.request.urlretrieve(
#   'https://media.geeksforgeeks.org/wp-content/uploads/20210318103632/gfg-300x300.png',
#    "gfg.png")
# urllib.request.urlretrieve(
#   'http://beta.khanaltech.com/files/image%20(1).tif',
#    "gfg.tif")

response = requests.get('http://beta.khanaltech.com/files/image%20(1).tif', verify=False)
image = Image.open(BytesIO(response.content))
image
#img = Image.open("gfg.tif")
#img
# %%
