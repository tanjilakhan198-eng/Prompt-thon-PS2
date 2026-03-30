import requests, io, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

img = Image.new("RGB", (400,400), "white")
draw = ImageDraw.Draw(img)
draw.rectangle([20,20,380,380], outline="black", width=8)
buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

r = requests.post("http://127.0.0.1:5000/image-to-3d",
                  files={"image": ("test.png", buf, "image/png")}, timeout=15)
print("Status:", r.status_code)
print("Body:", r.text[:1000])
