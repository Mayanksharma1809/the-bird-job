import os
from PIL import Image
import shutil

src_img = r'C:\Users\lenovo\.gemini\antigravity\brain\7e7d270a-2e88-4da6-8f2b-7de42b7c928a\media__1774792067965.jpg'
dest_dir = r'c:\Users\lenovo\OneDrive\Desktop\THEbirdJOB\static\brand'

if os.path.exists(src_img):
    try:
        img = Image.open(src_img)
        # Convert to RGBA for PNG to support transparency if needed, though JPG is RGB
        img_png = img.convert("RGBA")
        img_png.save(os.path.join(dest_dir, 'logo.png'), "PNG")
        
        # Resize for favicon and save
        img_ico = img.resize((32, 32))
        img_ico.save(os.path.join(dest_dir, 'favicon.ico'), format='ICO')
        print("Success: Processed with Pillow.")
    except Exception as e:
        print(f"Pillow error: {e}")
        print("Copying directly instead...")
        shutil.copy(src_img, os.path.join(dest_dir, 'logo.png'))
        shutil.copy(src_img, os.path.join(dest_dir, 'favicon.ico'))
        print("Success: Copied directly.")
else:
    print(f"Source file not found: {src_img}")
