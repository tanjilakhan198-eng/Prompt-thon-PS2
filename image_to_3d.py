import cv2
import numpy as np
import math
import io
from PIL import Image

WALL_HEIGHT   = 3.0
SLAB_THICK    = 0.15
DOOR_HEIGHT   = 2.1   # standard door height (m)
WIN_HEIGHT    = 1.2   # standard window height (m)
WIN_SILL      = 0.9   # window sill height from floor (m)

# ─────────────────────────────────────────────────────────────
# STEP 1: PREPROCESS
# Two binary images:
#   wall_mask  — thick strokes only  (walls)
#   full_mask  — all dark pixels     (walls + door arcs + window lines)
# ─────────────────────────────────────────────────────────────

def preprocess(image_bytes: bytes):
    img  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img  = img.resize((500, 500), Image.LANCZOS)
    arr  = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Full binary — captures everything dark
    _, full = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    # Wall mask — erode to kill thin strokes (text, arcs), keep thick walls
    kernel2 = np.ones((2, 2), np.uint8)
    kernel3 = np.ones((3, 3), np.uint8)
    walls   = cv2.erode(full,  kernel2, iterations=2)
    walls   = cv2.dilate(walls, kernel3, iterations=2)

    # Remove blobs smaller than 80px (text remnants)
    nl, lbl, stats, _ = cv2.connectedComponentsWithStats(walls, connectivity=8)
    wall_mask = np.zeros_like(walls)
    for i in range(1, nl):
        if stats[i, cv2.CC_STAT_AREA] >= 80:
            wall_mask[lbl == i] = 255

    return wall_mask, full, gray

# ─────────────────────────────────────────────────────────────
# STEP 2: DETECT WALLS
# Walls = long (>40px), straight (H or V), thick (>=3px) lines
# ─────────────────────────────────────────────────────────────

def detect_walls(wall_mask):
    edges = cv2.Canny(wall_mask, 30, 90, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180,
                            threshold=60, minLineLength=40, maxLineGap=10)
    if lines is None:
        return []

    raw = []
    for ln in lines:
        x1, y1, x2, y2 = ln[0]
        angle = abs(math.degrees(math.atan2(y2-y1, x2-x1)))
        # Only horizontal (0±15) or vertical (90±15)
        is_h = angle < 15 or angle > 165
        is_v = 75 < angle < 105
        if not (is_h or is_v):
            continue
        # Must be thick — walls are >= 3px wide
        if wall_thickness(wall_mask, x1, y1, x2, y2) < 3:
            continue
        raw.append((x1, y1, x2, y2, math.hypot(x2-x1, y2-y1)))

    return merge_lines(raw)

def wall_thickness(mask, x1, y1, x2, y2):
    """Measure perpendicular pixel width at 3 points along the line."""
    dx, dy = x2-x1, y2-y1
    dist   = math.hypot(dx, dy)
    if dist == 0: return 0
    nx, ny = -dy/dist, dx/dist
    H, W   = mask.shape
    counts = []
    for t in (0.25, 0.5, 0.75):
        cx, cy = int(x1+dx*t), int(y1+dy*t)
        c = sum(1 for r in range(-8, 9)
                if 0 <= int(cx+nx*r) < W and 0 <= int(cy+ny*r) < H
                and mask[int(cy+ny*r), int(cx+nx*r)] > 128)
        counts.append(c)
    return float(np.median(counts))

def merge_lines(lines, tol=12):
    used, result = [False]*len(lines), []
    for i, (x1,y1,x2,y2,_) in enumerate(lines):
        if used[i]: continue
        ax,ay,bx,by,n = x1,y1,x2,y2,1
        for j, (x3,y3,x4,y4,_) in enumerate(lines):
            if i==j or used[j]: continue
            if abs(x1-x3)<tol and abs(y1-y3)<tol and abs(x2-x4)<tol and abs(y2-y4)<tol:
                ax+=x3; ay+=y3; bx+=x4; by+=y4; n+=1; used[j]=True
        result.append((ax//n, ay//n, bx//n, by//n))
        used[i] = True
    return result

# ─────────────────────────────────────────────────────────────
# STEP 3: AUTO-SCALE  (assume building ~10m wide)
# ─────────────────────────────────────────────────────────────

def compute_scale(lines, assumed_m=10.0):
    if not lines: return assumed_m / 500
    xs = [p for l in lines for p in [l[0], l[2]]]
    ys = [p for l in lines for p in [l[1], l[3]]]
    span = max(max(xs)-min(xs), max(ys)-min(ys))
    return assumed_m / span if span > 0 else assumed_m / 500

# ─────────────────────────────────────────────────────────────
# STEP 4: CLASSIFY WALLS
#
# Load-bearing rules (any one = load-bearing):
#   1. Near image boundary (outer perimeter)
#   2. Length > 35% of image span (long structural wall)
#   3. Thickness >= 6px (thick = structural)
#
# Partition rules:
#   - Short inner walls (< 35% span, not near edge, thin)
# ─────────────────────────────────────────────────────────────

def classify_wall(x1, y1, x2, y2, wall_mask, img_size=500):
    margin    = img_size * 0.07          # 7% from edge
    near_edge = (min(x1,x2) < margin or max(x1,x2) > img_size-margin or
                 min(y1,y2) < margin or max(y1,y2) > img_size-margin)
    length_px = math.hypot(x2-x1, y2-y1)
    long_wall = length_px > img_size * 0.35
    thick     = wall_thickness(wall_mask, x1, y1, x2, y2) >= 6

    if near_edge or long_wall or thick:
        return "load-bearing"
    return "partition"

# ─────────────────────────────────────────────────────────────
# STEP 5: DETECT DOORS & WINDOWS
#
# Method: scan along each wall line for gaps in the wall_mask.
# A gap = consecutive pixels where wall_mask == 0.
#
# Door identification:
#   - Gap width 0.6m – 1.4m
#   - Arc present near gap (quarter-circle in full_mask)
#   - Located in interior walls OR outer walls at ground level
#
# Window identification:
#   - Gap width 0.4m – 2.5m
#   - No arc (just a clean gap)
#   - Typically in outer/load-bearing walls
#   - Parallel thin lines on both sides of gap (window frame)
# ─────────────────────────────────────────────────────────────

def has_arc_near(full_mask, cx, cy, radius=20):
    """
    Check if there is a quarter-circle arc near (cx,cy).
    Arcs appear in floor plans to indicate door swing direction.
    We detect them by checking for curved pixel density in a region.
    """
    H, W = full_mask.shape
    x0, y0 = max(0, cx-radius), max(0, cy-radius)
    x1, y1 = min(W, cx+radius), min(H, cy+radius)
    roi = full_mask[y0:y1, x0:x1]
    if roi.size == 0:
        return False
    # Detect circles in the ROI
    roi_blur = cv2.GaussianBlur(roi, (5,5), 1)
    circles  = cv2.HoughCircles(roi_blur, cv2.HOUGH_GRADIENT, dp=1,
                                minDist=10, param1=30, param2=12,
                                minRadius=8, maxRadius=radius)
    return circles is not None

def has_parallel_lines(full_mask, cx, cy, is_horizontal, gap_w_px, tol=6):
    """
    Check for thin parallel lines on both sides of a gap — window frame indicator.
    """
    H, W = full_mask.shape
    checks = 0
    for side in (-1, 1):
        if is_horizontal:
            px = max(0, min(W-1, cx + side * (gap_w_px//2 + tol)))
            py = cy
        else:
            px = cx
            py = max(0, min(H-1, cy + side * (gap_w_px//2 + tol)))
        if full_mask[py, px] > 128:
            checks += 1
    return checks >= 1

def detect_openings(wall_mask, full_mask, lines, scale):
    openings = []
    H, W = wall_mask.shape

    for i, (x1, y1, x2, y2) in enumerate(lines):
        dx, dy   = x2-x1, y2-y1
        length   = math.hypot(dx, dy)
        is_h     = abs(dx) > abs(dy)
        steps    = max(int(length), 2)

        gap_start = None
        for s in range(steps + 1):
            t  = s / steps
            px = int(x1 + dx*t)
            py = int(y1 + dy*t)
            px = max(0, min(px, W-1))
            py = max(0, min(py, H-1))

            in_wall = wall_mask[py, px] > 64

            if not in_wall and gap_start is None:
                gap_start = (px, py)
            elif in_wall and gap_start is not None:
                # Gap ended — measure it
                gx1, gy1 = gap_start
                gap_px   = math.hypot(px-gx1, py-gy1)
                gap_m    = round(gap_px * scale, 2)
                mid_x    = (gx1 + px) // 2
                mid_y    = (gy1 + py) // 2

                if 0.4 <= gap_m <= 2.5:
                    arc      = has_arc_near(full_mask, mid_x, mid_y, radius=int(gap_px*0.8))
                    par_line = has_parallel_lines(full_mask, mid_x, mid_y, is_h, int(gap_px))

                    # Decision logic:
                    # Door:   arc present OR gap 0.6–1.4m in interior wall
                    # Window: parallel frame lines OR gap 0.4–2.5m in outer wall
                    wall_cls = classify_wall(x1, y1, x2, y2, wall_mask)

                    if arc and 0.6 <= gap_m <= 1.4:
                        otype = "door"
                    elif par_line and gap_m <= 2.5:
                        otype = "window"
                    elif gap_m <= 1.4 and wall_cls == "partition":
                        otype = "door"       # interior gap without arc = door
                    elif gap_m <= 2.5 and wall_cls == "load-bearing":
                        otype = "window"     # outer wall gap = window
                    else:
                        otype = "door" if gap_m <= 1.4 else "window"

                    openings.append({
                        "type":        otype,
                        "wall_id":     f"W{i+1}",
                        "wall_class":  wall_cls,
                        "position":    [round(mid_x*scale,2), round(mid_y*scale,2)],
                        "width_m":     gap_m,
                        "orientation": "horizontal" if is_h else "vertical",
                        "has_arc":     bool(arc),
                        "has_frame":   bool(par_line)
                    })
                gap_start = None

    # Assign IDs
    d_cnt = w_cnt = 0
    for o in openings:
        if o["type"] == "door":
            d_cnt += 1; o["id"] = f"D{d_cnt}"
        else:
            w_cnt += 1; o["id"] = f"WIN{w_cnt}"

    return openings

# ─────────────────────────────────────────────────────────────
# STEP 6: DETECT ROOMS
# ─────────────────────────────────────────────────────────────

ROOM_RULES = [
    ("Bathroom",    0.0,  6.0),
    ("Kitchen",     6.0, 12.0),
    ("Bedroom",    12.0, 25.0),
    ("Hall",       25.0, 45.0),
    ("Living Room",45.0, 500),
]

def classify_room(area_m2, cx_r, cy_r):
    near_entrance = cy_r > 0.72
    near_top      = cy_r < 0.28
    for name, lo, hi in ROOM_RULES:
        if lo <= area_m2 < hi:
            if name == "Bedroom" and near_entrance: return "Hall"
            if name == "Kitchen" and near_top:      return "Bathroom"
            return name
    return "Room"

def detect_rooms(wall_mask, scale):
    """
    Detect rooms by:
    1. Draw all wall lines onto a blank canvas to ensure closed regions
    2. Flood-fill from multiple seed points to find enclosed areas
    3. Filter by realistic room size
    """
    H, W = wall_mask.shape

    # Step 1: thicken walls to close small gaps
    kernel  = np.ones((5,5), np.uint8)
    closed  = cv2.dilate(wall_mask, kernel, iterations=2)

    # Step 2: invert — rooms are white space between walls
    inv = cv2.bitwise_not(closed)

    # Step 3: use RETR_TREE to get only innermost contours (actual rooms)
    contours, hierarchy = cv2.findContours(inv, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if hierarchy is None:
        return []

    # Only keep contours that have a parent (i.e. enclosed regions)
    # hierarchy shape: [1, N, 4] — [next, prev, child, parent]
    hier = hierarchy[0]
    all_areas = [cv2.contourArea(c) for c in contours]
    max_area  = max(all_areas) if all_areas else 1
    valid = []
    for i, cnt in enumerate(contours):
        parent  = hier[i][3]
        child   = hier[i][2]
        area_px = cv2.contourArea(cnt)
        area_m2 = round(area_px * (scale**2), 2)
        # Leaf nodes only (child == -1) = actual rooms, not containers
        # Must have a parent (enclosed) and realistic room size
        if child == -1 and parent >= 0 and 1.0 <= area_m2 <= 300:
            valid.append((cnt, area_m2))

    # If no enclosed contours found, fall back to largest non-overlapping regions
    if not valid:
        all_cnts = [(c, round(cv2.contourArea(c)*(scale**2),2)) for c in contours]
        all_cnts = [(c,a) for c,a in all_cnts if 1.0 <= a <= 300]
        # Remove contours that contain other contours (keep only leaf nodes)
        all_cnts.sort(key=lambda x: x[1])
        filtered = []
        for i, (c1, a1) in enumerate(all_cnts):
            dominated = False
            x1,y1,w1,h1 = cv2.boundingRect(c1)
            for j, (c2, a2) in enumerate(all_cnts):
                if i == j: continue
                x2,y2,w2,h2 = cv2.boundingRect(c2)
                # c2 contains c1 if c2 bbox is larger and overlaps
                if a2 > a1*1.5 and x2<=x1 and y2<=y1 and x2+w2>=x1+w1 and y2+h2>=y1+h1:
                    dominated = True; break
            if not dominated:
                filtered.append((c1, a1))
        valid = filtered

    valid.sort(key=lambda x: x[1], reverse=True)

    rooms, type_counts = [], {}
    for i, (cnt, area_m2) in enumerate(valid):
        approx  = cv2.approxPolyDP(cnt, 0.03*cv2.arcLength(cnt,True), True)
        corners = [[round(p[0][0]*scale,2), round(p[0][1]*scale,2)] for p in approx]
        x, y, w, h = cv2.boundingRect(cnt)
        M  = cv2.moments(cnt)
        cx = M["m10"]/M["m00"] if M["m00"] else x+w/2
        cy = M["m01"]/M["m00"] if M["m00"] else y+h/2

        rtype = classify_room(area_m2, cx/W, cy/H)
        type_counts[rtype] = type_counts.get(rtype, 0) + 1
        label = rtype if type_counts[rtype] == 1 else f"{rtype} {type_counts[rtype]}"

        rooms.append({
            "id":      f"R{i+1}",
            "name":    label,
            "type":    rtype,
            "corners": corners,
            "center":  [round(cx*scale,2), round(cy*scale,2)],
            "width_m": round(w*scale,2),
            "depth_m": round(h*scale,2),
            "area_m2": area_m2
        })
    return rooms

# ─────────────────────────────────────────────────────────────
# STEP 7: BUILD 3D MESHES
# ─────────────────────────────────────────────────────────────

def build_wall_mesh(wid, x1, y1, x2, y2, scale, cls):
    mx1,my1 = round(x1*scale,3), round(y1*scale,3)
    mx2,my2 = round(x2*scale,3), round(y2*scale,3)
    length  = round(math.hypot(mx2-mx1, my2-my1), 3)
    # Load-bearing walls are thicker (300mm) than partitions (150mm)
    thick   = 0.30 if cls == "load-bearing" else 0.15
    t = thick/2
    dx,dy = mx2-mx1, my2-my1
    d = math.hypot(dx,dy)
    if d < 0.01: return None
    nx,ny = -dy/d, dx/d
    base = [[round(mx1+nx*t,3),round(my1+ny*t,3),0],
            [round(mx1-nx*t,3),round(my1-ny*t,3),0],
            [round(mx2-nx*t,3),round(my2-ny*t,3),0],
            [round(mx2+nx*t,3),round(my2+ny*t,3),0]]
    top  = [[p[0],p[1],WALL_HEIGHT] for p in base]
    return {"wall_id":wid,"type":"box","start":[mx1,my1],"end":[mx2,my2],
            "vertices":base+top,"length_m":length,"height_m":WALL_HEIGHT,
            "thickness_m":thick,"classification":cls}

def build_slab(lines, scale):
    if not lines: return {}
    xs = [p*scale for l in lines for p in [l[0],l[2]]]
    ys = [p*scale for l in lines for p in [l[1],l[3]]]
    x0,x1 = min(xs),max(xs)
    y0,y1 = min(ys),max(ys)
    return {"type":"slab",
            "corners":[[round(x0,2),round(y0,2)],[round(x1,2),round(y0,2)],
                       [round(x1,2),round(y1,2)],[round(x0,2),round(y1,2)]],
            "center_x":round((x0+x1)/2,2),"center_z":round((y0+y1)/2,2),
            "width_m":round(x1-x0,2),"depth_m":round(y1-y0,2),
            "z":0,"thickness_m":SLAB_THICK,
            "area_m2":round((x1-x0)*(y1-y0),2)}

# ─────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

def image_to_3d(image_bytes: bytes) -> dict:
    wall_mask, full_mask, _ = preprocess(image_bytes)
    lines  = detect_walls(wall_mask)
    scale  = compute_scale(lines)

    wall_meshes, walls_2d = [], []
    lb = pt = 0
    for i, (x1,y1,x2,y2) in enumerate(lines):
        cls  = classify_wall(x1,y1,x2,y2, wall_mask)
        mesh = build_wall_mesh(f"W{i+1}", x1,y1,x2,y2, scale, cls)
        if mesh:
            wall_meshes.append(mesh)
            walls_2d.append({"id":f"W{i+1}","start":mesh["start"],"end":mesh["end"],
                              "length_m":mesh["length_m"],"thickness_m":mesh["thickness_m"],
                              "classification":cls})
            if cls == "load-bearing": lb += 1
            else:                     pt += 1

    rooms    = detect_rooms(wall_mask, scale)
    openings = detect_openings(wall_mask, full_mask, lines, scale)
    slab     = build_slab(lines, scale)

    doors   = [o for o in openings if o["type"] == "door"]
    windows = [o for o in openings if o["type"] == "window"]

    room_summary = {}
    for r in rooms:
        room_summary[r["type"]] = room_summary.get(r["type"], 0) + 1

    warnings = [
        f"{w['id']} is a {w['length_m']}m load-bearing span — add beam or column."
        for w in walls_2d if w["classification"]=="load-bearing" and w["length_m"]>4.0
    ]

    return {
        "summary": {
            "total_walls":         len(wall_meshes),
            "load_bearing":        lb,
            "partition":           pt,
            "total_rooms":         len(rooms),
            "total_doors":         len(doors),
            "total_windows":       len(windows),
            "room_types":          room_summary,
            "floor_area_m2":       slab.get("area_m2", 0),
            "building_width_m":    slab.get("width_m", 0),
            "building_depth_m":    slab.get("depth_m", 0),
            "wall_height_m":       WALL_HEIGHT,
            "scale_px_per_m":      round(1/scale, 2),
            "structural_warnings": warnings
        },
        "walls_2d":  walls_2d,
        "rooms":     rooms,
        "openings":  openings,
        "model_3d": {
            "wall_meshes": wall_meshes,
            "floor_slab":  slab,
            "render_hint": "red=load-bearing, blue=partition, green=slab, brown=door, skyblue=window"
        }
    }
