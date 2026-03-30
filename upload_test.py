import requests, io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

img = Image.new("RGB", (400,400), "white")
draw = ImageDraw.Draw(img)
draw.rectangle([20,20,380,380], outline="black", width=8)
draw.line([200,20,200,380], fill="black", width=5)
draw.line([20,200,200,200], fill="black", width=5)
buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

try:
    r = requests.post("http://127.0.0.1:5000/image-to-3d",
                      files={"image": ("test.png", buf, "image/png")}, timeout=15)
    print("Status:", r.status_code)
    data = r.json()
    print("Walls:", data.get("summary", {}).get("total_walls"))
    print("Rooms:", data.get("summary", {}).get("total_rooms"))
    print("Material analysis:", "YES" if data.get("material_analysis") else "NO")
    print("Quantities:", "YES" if data.get("material_analysis", {}).get("quantities") else "NO")
except Exception as e:
    print("ERROR:", e)
