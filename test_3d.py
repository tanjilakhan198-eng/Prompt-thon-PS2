import numpy as np
import cv2
import io
import json
import traceback
from PIL import Image, ImageDraw

# Build a simple synthetic floor plan
img = Image.new("RGB", (400, 400), "white")
draw = ImageDraw.Draw(img)
draw.rectangle([20, 20, 380, 380], outline="black", width=6)
draw.line([200, 20, 200, 380], fill="black", width=4)
draw.line([20, 200, 200, 200], fill="black", width=4)
draw.line([200, 250, 380, 250], fill="black", width=4)
buf = io.BytesIO()
img.save(buf, format="PNG")
image_bytes = buf.getvalue()

print("=== STEP BY STEP DEBUG ===")

# Step 1: preprocess
from PIL import Image as PILImage
img2 = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
img2 = img2.resize((800, 800), PILImage.LANCZOS)
arr  = np.array(img2)
gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
_, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
kernel = np.ones((3, 3), np.uint8)
binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
print(f"Binary image shape: {binary.shape}, nonzero pixels: {np.count_nonzero(binary)}")

# Step 2: edges + hough
edges = cv2.Canny(binary, 50, 150, apertureSize=3)
print(f"Edge pixels: {np.count_nonzero(edges)}")

lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80, minLineLength=40, maxLineGap=10)
print(f"Raw Hough lines: {len(lines) if lines is not None else 0}")

# Step 3: rooms
inv = cv2.bitwise_not(binary)
contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Contours found: {len(contours)}")
for i, c in enumerate(contours):
    area = cv2.contourArea(c) * (0.05**2)
    print(f"  Contour {i}: area={area:.2f} m2")

# Full pipeline
try:
    from image_to_3d import image_to_3d
    result = image_to_3d(image_bytes)
    print("\n=== RESULT ===")
    print(json.dumps(result["summary"], indent=2))
    print(f"Wall meshes: {len(result['model_3d']['wall_meshes'])}")
    print(f"Rooms: {len(result['rooms'])}")
    if result["model_3d"]["wall_meshes"]:
        print("First mesh sample:", json.dumps(result["model_3d"]["wall_meshes"][0], indent=2))
except Exception:
    traceback.print_exc()
