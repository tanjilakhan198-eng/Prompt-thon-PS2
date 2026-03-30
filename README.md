# 2D Floor Plan to 3D Model Converter

An AI-powered web application that converts 2D floor plan images into interactive 3D models using computer vision and Three.js rendering.

---

## Project Structure

```
iiitnr/
├── app.py                  # Flask web server & API routes
├── image_to_3d.py          # Core image processing pipeline
├── structural_engine.py    # 5-stage structural analysis engine
├── viewer.html             # Interactive Three.js 3D viewer
├── floor_plan_data.json    # Sample floor plan input data
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## How It Works

### Pipeline (image_to_3d.py)

```
Floor Plan Image
      │
      ▼
Step 1: Preprocess
  - Resize to 400×400
  - Threshold to isolate dark pixels
  - Erode thin strokes (removes text, dimensions)
  - Remove small blobs (dots, arrows, labels)
      │
      ▼
Step 2: Detect Walls
  - Canny edge detection
  - Hough Line Transform (only horizontal/vertical lines)
  - Filter by thickness (walls > 2px, text < 2px)
  - Merge duplicate lines
      │
      ▼
Step 3: Auto-Scale
  - Detect bounding box of all lines
  - Assume building is ~10m wide
  - Compute pixels-per-metre ratio
      │
      ▼
Step 4: Classify Walls
  - Near edge or long → Load-Bearing (red)
  - Short inner lines  → Partition (blue)
      │
      ▼
Step 5: Detect Rooms
  - Invert binary image
  - Find enclosed contours
  - Filter by area (1–500 m²)
      │
      ▼
Step 6: Build 3D Meshes
  - Extrude each wall to 3m height
  - Generate 8-vertex box per wall
  - Build floor slab from bounding box
      │
      ▼
JSON Output → Three.js Viewer
```

---

## Installation

**Requirements:** Python 3.8+

```bash
# 1. Clone or download the project
cd "C:\Users\omen\OneDrive\Desktop\iiitnr"

# 2. Install dependencies
pip install -r requirements.txt
```

**requirements.txt includes:**
- flask
- opencv-python
- numpy
- Pillow

---

## Running the App

```bash
py app.py
```

Then open your browser at:
```
http://127.0.0.1:5000/
```

---

## Usage

| Step | Action |
|------|--------|
| 1 | Open `http://127.0.0.1:5000/` |
| 2 | Click **"Click here to choose a floor plan image"** |
| 3 | Select a PNG or JPG floor plan image |
| 4 | Click **"Convert to 3D"** |
| 5 | View detection results (walls, rooms, area) |
| 6 | Click **"View 3D Model"** to open the interactive viewer |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page with upload UI |
| POST | `/image-to-3d` | Upload image, returns 3D JSON |
| GET | `/viewer` | Interactive Three.js 3D viewer |

### POST /image-to-3d

**Request:**
```
Content-Type: multipart/form-data
Field: image (PNG/JPG file)
```

**Response:**
```json
{
  "summary": {
    "total_walls": 8,
    "load_bearing": 5,
    "partition": 3,
    "total_rooms": 4,
    "floor_area_m2": 98.5,
    "building_width_m": 10.0,
    "building_depth_m": 9.85,
    "wall_height_m": 3.0,
    "structural_warnings": ["W1 is a 10.0m load-bearing span..."]
  },
  "walls_2d": [...],
  "rooms": [...],
  "model_3d": {
    "wall_meshes": [...],
    "floor_slab": {...}
  }
}
```

---

## 3D Viewer Controls

| Control | Action |
|---------|--------|
| Left drag | Rotate model |
| Right drag | Pan |
| Scroll wheel | Zoom in/out |
| R key | Reset camera view |
| Walls button | Toggle walls on/off |
| Slab button | Toggle floor slab on/off |
| Wireframe button | Toggle wireframe edges |

### Color Legend

| Color | Meaning |
|-------|---------|
| 🔴 Red | Load-bearing wall |
| 🔵 Blue | Partition wall |
| 🟢 Green | Floor slab |

---

## Wall Detection Logic

### Why text is ignored
Text and dimension labels are filtered out using 3 methods:

1. **Morphological erosion** — erodes 2px, destroying thin text strokes (1–2px) while keeping thick walls (5–8px)
2. **Blob size filter** — removes any connected component smaller than 60px²
3. **Thickness measurement** — samples perpendicular width at 3 points along each line; skips lines thinner than 2px
4. **Angle filter** — only keeps lines within 15° of horizontal or vertical (walls are always straight)
5. **Length filter** — minimum 40px line length; short text strokes are ignored

### Wall Classification
```
Near image edge (within 8%)  →  Load-Bearing
Line length > 30% of image   →  Load-Bearing
Everything else              →  Partition
```

---

## Best Image Types

For best results, use floor plan images that have:
- ✅ Black walls on white background
- ✅ Thick wall lines (3px or more)
- ✅ Mostly horizontal and vertical walls
- ✅ Clear contrast between walls and background

Avoid:
- ❌ Very low resolution images (below 200×200)
- ❌ Colored or shaded walls
- ❌ Hand-drawn sketches with rough lines
- ❌ Images with heavy watermarks over walls

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Image Processing | OpenCV, NumPy, Pillow |
| 3D Rendering | Three.js r128, OrbitControls |
| Frontend | HTML5, CSS3, Vanilla JS |

---

## Structural Analysis Engine (structural_engine.py)

Separate from the image pipeline, this engine processes structured JSON floor plan data through 5 stages:

| Stage | Description |
|-------|-------------|
| 1 — Parsing | Extract walls, rooms, openings from JSON |
| 2 — Geometry | Build structural graph, classify walls, detect spans |
| 3 — 3D Model | Extrude walls to 3m, generate slab mesh |
| 4 — Materials | Score materials using tradeoff formula |
| 5 — Explain | Generate human-readable structural report |

**Material Tradeoff Formula:**
```
Score = (W1 × Strength + W2 × Durability) / Cost

Structural elements:  W1=0.6, W2=0.4  (strength-first)
Partition elements:   W1=0.3, W2=0.3  (cost-first)
```

---

## License

MIT License — free to use and modify.
