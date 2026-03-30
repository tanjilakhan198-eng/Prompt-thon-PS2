import io, sys
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw
from image_to_3d import image_to_3d

img  = Image.new("RGB", (500,500), "white")
draw = ImageDraw.Draw(img)
draw.rectangle([30,30,470,470], outline="black", width=8)
draw.line([250,30,250,470],  fill="black", width=6)
draw.line([30,250,250,250],  fill="black", width=5)
draw.line([250,300,470,300], fill="black", width=5)
buf = io.BytesIO()
img.save(buf, format="PNG")

r = image_to_3d(buf.getvalue())
print("Total rooms:", r["summary"]["total_rooms"])
print("Room types :", r["summary"]["room_types"])
for room in r["rooms"]:
    print(f"  {room['name']} ({room['type']}) {room['width_m']}x{room['depth_m']}m = {room['area_m2']} m2")
