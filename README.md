# 2D Floor Plan to 3D Model Converter

An AI-powered web application that converts 2D floor plan images into interactive 3D models with material analysis, cost estimation, and quantity takeoff.

---

## Project Structure

```
Prompt-thon-PS2/
├── app.py                  # Flask web server & API routes
├── image_to_3d.py          # Core image processing pipeline (6 steps)
├── material_analysis.py    # Material recommendations, cost & quantity estimation
├── structural_engine.py    # 5-stage structural analysis engine
├── home.html               # Upload UI with all result panels
├── viewer.html             # Interactive Three.js 3D viewer
├── floor_plan_data.json    # Sample floor plan input data
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

---

## Features

| Feature | Description |
|---------|-------------|
| Wall Detection | Detects thick wall lines, filters out text and dimensions |
| Room Detection | Finds enclosed rooms, classifies as Bedroom/Kitchen/Hall/Bathroom/Living Room |
| Door & Window Detection | Detects gaps in walls, identifies doors (arc) vs windows (frame) |
| 3D Model | Extrudes walls to 3m, renders in Three.js with BoxGeometry, CylinderGeometry, SphereGeometry |
| Material Analysis | Recommends top 3 materials per element with tradeoff score |
| Cost Estimation | Full itemized construction cost in INR with overhead and contingency |
| Quantity Estimation | Material quantities (concrete, steel, bricks, cement, tiles etc.) |

---

## 5-Stage Pipeline

```
Floor Plan Image
      │
      ▼
Stage 1: Floor Plan Parsing
  - Preprocess image (resize, threshold, erode, blob filter)
  - Detect walls using Canny + HoughLinesP
  - Filter: only H/V lines, thickness >= 3px, length >= 40px
      │
      ▼
Stage 2: Geometry Reconstruction
  - Build structural graph (nodes = junctions, edges = walls)
  - Classify walls: Load-Bearing (outer/long/thick) vs Partition
  - Detect rooms using RETR_TREE contour hierarchy
  - Classify rooms by area: Bathroom/Kitchen/Bedroom/Hall/Living Room
  - Detect doors (arc near gap) and windows (parallel frame lines)
      │
      ▼
Stage 3: 2D to 3D Model Generation
  - Extrude each wall to 3m height (BoxGeometry)
  - Generate floor slab (PlaneGeometry + ShapeGeometry)
  - Add columns (CylinderGeometry) at load-bearing junctions
  - Add joints (SphereGeometry) at column tops
  - Add roof edge (EdgesGeometry)
  - Render doors (wood panel + frame + brass knob + swing arc)
  - Render windows (glass panes + frame + mullion + sill)
      │
      ▼
Stage 4: Material Analysis & Cost-Strength Tradeoff
  - Score = (W1 x Strength + W2 x Durability) / Cost
  - Structural: W1=0.6, W2=0.4 (strength-first)
  - Partition:  W1=0.2, W2=0.3 (cost-first)
  - Top 3 materials per element with INR price
  - Full construction cost breakdown (15 line items)
  - Material quantity takeoff (12 materials)
      │
      ▼
Stage 5: Explainability
  - Plain-English explanation for each material choice
  - Structural warnings for spans > 4m
  - Optimization suggestions
```

---

## Installation

**Requirements:** Python 3.8+

```bash
# Clone the repository
git clone https://github.com/tanjilakhan198-eng/Prompt-thon-PS2.git
cd Prompt-thon-PS2

# Install dependencies
pip install -r requirements.txt
```

**Dependencies:**
- flask
- opencv-python
- numpy
- Pillow

---

## Running the App

```bash
py app.py
```

Open browser at:
```
http://127.0.0.1:5000/
```

---

## Usage

| Step | Action |
|------|--------|
| 1 | Open `http://127.0.0.1:5000/` |
| 2 | Click the upload zone or drag & drop a floor plan image |
| 3 | Click **Convert to 3D** |
| 4 | View: Detection Results, Room Count, Material Analysis, Cost Estimate, Quantities |
| 5 | Click **View 3D Model** for interactive Three.js viewer |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page |
| POST | `/image-to-3d` | Upload image → returns full analysis JSON |
| GET | `/viewer` | Three.js 3D viewer |

---

## Material Analysis

**Tradeoff Formula:**
```
Score = (W1 x Strength + W2 x Durability) / Cost
```

| Element | W1 | W2 | Priority |
|---------|----|----|----------|
| Load-Bearing Wall | 0.6 | 0.4 | Strength-first |
| Partition Wall | 0.2 | 0.3 | Cost-first |
| Slab | 0.6 | 0.4 | Strength-first |
| Column | 0.7 | 0.3 | Max strength |

**Materials Database:** Reinforced Concrete, Prestressed Concrete, Steel Frame, AAC Blocks, Fly Ash Bricks, Red Clay Bricks, Hollow Concrete Blocks, Timber Frame, Glass Fibre Reinforced

---

## Cost Estimation

Full itemized breakdown including:
- Foundation, Columns, Load-Bearing Walls, Partition Walls
- Floor Slab, Roof Slab, Flooring (Tiles)
- Plaster, Paint, Doors, Windows
- Electrical, Plumbing, Sanitary, Labour
- 15% Contractor Overhead + 10% Contingency

Output: Total in INR, Lakhs, Cost/sq.ft, Cost/m2

---

## Material Quantities

| Material | Unit |
|----------|------|
| Concrete (RCC) | m3 |
| Steel (TMT Bars) | kg |
| Red Clay Bricks | nos |
| AAC Blocks | m3 |
| Cement (OPC 53) | bags |
| Sand, Aggregate | m3 |
| Plaster, Paint | m2 / litres |
| Floor Tiles | m2 |
| Doors, Windows | nos |

All quantities include 5% wastage factor.

---

## 3D Viewer Controls

| Control | Action |
|---------|--------|
| Left drag | Rotate |
| Right drag | Pan |
| Scroll | Zoom |
| R key | Reset camera |
| Toolbar buttons | Toggle Walls / Slab / Columns / Doors / Roof / Wireframe |

### Color Legend

| Color | Element |
|-------|---------|
| Red | Load-bearing wall |
| Blue | Partition wall |
| Green | Floor slab |
| Orange | Columns |
| Pink | Joints |
| Brown | Doors |
| Sky Blue | Windows |
| Purple | Roof edge |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, Flask |
| Image Processing | OpenCV, NumPy, Pillow |
| 3D Rendering | Three.js r128, OrbitControls |
| Frontend | HTML5, CSS3, Vanilla JS |

---

## Best Image Types

- Black walls on white background
- Thick wall lines (3px or more)
- Mostly horizontal and vertical walls
- Clear contrast between walls and background

---

## License

MIT License
