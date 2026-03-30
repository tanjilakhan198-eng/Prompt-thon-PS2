import cv2, numpy as np, io, json
from PIL import Image, ImageDraw
from image_to_3d import preprocess, detect_walls, compute_scale

# 4-room floor plan
img = Image.new('RGB', (500,500), 'white')
draw = ImageDraw.Draw(img)
draw.rectangle([30,30,470,470], outline='black', width=8)
draw.line([250,30,250,470], fill='black', width=6)
draw.line([30,250,250,250], fill='black', width=5)
draw.line([250,300,470,300], fill='black', width=5)

buf = io.BytesIO()
img.save(buf, format='PNG')
byt = buf.getvalue()

wall_mask, full_mask, _ = preprocess(byt)
lines = detect_walls(wall_mask)
scale = compute_scale(lines)

print("Scale:", round(scale,4))

# Check hierarchy
kernel = np.ones((5,5), np.uint8)
closed = cv2.dilate(wall_mask, kernel, iterations=2)
inv    = cv2.bitwise_not(closed)
contours, hierarchy = cv2.findContours(inv, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

print(f"Contours: {len(contours)}")
if hierarchy is not None:
    hier = hierarchy[0]
    for i,c in enumerate(contours):
        area_px = cv2.contourArea(c)
        area_m2 = round(area_px*scale**2, 2)
        parent  = hier[i][3]
        child   = hier[i][2]
        print(f"  [{i}] area_m2={area_m2} parent={parent} child={child}")
else:
    print("No hierarchy!")
