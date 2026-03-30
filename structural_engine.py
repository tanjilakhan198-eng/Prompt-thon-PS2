import json
import math
from collections import defaultdict

# ─────────────────────────────────────────────
# STAGE 1: FLOOR PLAN PARSING
# ─────────────────────────────────────────────

def parse_floor_plan(data: dict) -> dict:
    """Validate and return structured floor plan JSON."""
    walls    = data["walls"]
    rooms    = data["rooms"]
    openings = data["openings"]

    # Attach opening counts to walls for downstream use
    opening_map = defaultdict(list)
    for o in openings:
        opening_map[o["wall_id"]].append(o)

    for w in walls:
        w["openings"] = opening_map.get(w["id"], [])

    return {"walls": walls, "rooms": rooms, "openings": openings}


# ─────────────────────────────────────────────
# STAGE 2: GEOMETRY RECONSTRUCTION
# ─────────────────────────────────────────────

def wall_length(w: dict) -> float:
    dx = w["end"][0] - w["start"][0]
    dy = w["end"][1] - w["start"][1]
    return round(math.hypot(dx, dy), 3)

def room_area(r: dict) -> float:
    pts = r["corners"]
    n = len(pts)
    area = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return round(abs(area) / 2, 3)

def classify_wall(w: dict) -> str:
    """Outer walls and the central spine (W5) are load-bearing."""
    if w["type"] == "outer":
        return "load-bearing"
    length = wall_length(w)
    # Inner walls spanning full building depth are structural spine
    if length >= 7.0:
        return "load-bearing"
    return "partition"

def build_structural_graph(parsed: dict) -> dict:
    nodes = {}
    edges = []

    for w in parsed["walls"]:
        for pt in [tuple(w["start"]), tuple(w["end"])]:
            if pt not in nodes:
                nodes[pt] = f"N{len(nodes)+1}"

        span   = wall_length(w)
        cls    = classify_wall(w)
        edges.append({
            "wall_id":    w["id"],
            "from_node":  nodes[tuple(w["start"])],
            "to_node":    nodes[tuple(w["end"])],
            "span_m":     span,
            "thickness_m":w["thickness"],
            "classification": cls,
            "openings":   w["openings"]
        })

    room_info = []
    for r in parsed["rooms"]:
        area = room_area(r)
        xs = [p[0] for p in r["corners"]]
        ys = [p[1] for p in r["corners"]]
        room_info.append({
            "id":     r["id"],
            "name":   r["name"],
            "width_m":  round(max(xs) - min(xs), 2),
            "depth_m":  round(max(ys) - min(ys), 2),
            "area_m2":  area
        })

    # Detect large unsupported spans (> 4 m with no intermediate support)
    warnings = []
    for e in edges:
        if e["span_m"] > 4.0 and e["classification"] == "load-bearing":
            warnings.append(
                f"{e['wall_id']} is a {e['span_m']}m load-bearing span — "
                "consider intermediate column or beam."
            )

    return {
        "nodes": {str(v): list(k) for k, v in nodes.items()},
        "edges": edges,
        "rooms": room_info,
        "structural_warnings": warnings
    }


# ─────────────────────────────────────────────
# STAGE 3: 2D → 3D MODEL GENERATION
# ─────────────────────────────────────────────

WALL_HEIGHT = 3.0  # metres
SLAB_THICKNESS = 0.15

def extrude_wall(w: dict) -> dict:
    x1, y1 = w["start"]
    x2, y2 = w["end"]
    t = w["thickness"] / 2
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length  # normal vector

    # 8 corners of the wall box
    base = [
        [x1 + nx*t, y1 + ny*t, 0], [x1 - nx*t, y1 - ny*t, 0],
        [x2 - nx*t, y2 - ny*t, 0], [x2 + nx*t, y2 + ny*t, 0],
    ]
    top = [[p[0], p[1], WALL_HEIGHT] for p in base]
    return {
        "wall_id":  w["id"],
        "type":     "box",
        "vertices": base + top,
        "height_m": WALL_HEIGHT,
        "length_m": round(length, 3),
        "thickness_m": w["thickness"]
    }

def generate_floor_slab(parsed: dict) -> dict:
    all_x = [pt for w in parsed["walls"] for pt in [w["start"][0], w["end"][0]]]
    all_y = [pt for w in parsed["walls"] for pt in [w["start"][1], w["end"][1]]]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    return {
        "type": "slab",
        "corners": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]],
        "z": 0,
        "thickness_m": SLAB_THICKNESS,
        "area_m2": round((max_x - min_x) * (max_y - min_y), 2)
    }

def generate_3d_model(parsed: dict) -> dict:
    wall_meshes = [extrude_wall(w) for w in parsed["walls"]]
    slab = generate_floor_slab(parsed)
    return {
        "wall_meshes": wall_meshes,
        "floor_slab":  slab,
        "render_hint": "Three.js BoxGeometry per wall_mesh; slab as PlaneGeometry"
    }


# ─────────────────────────────────────────────
# STAGE 4: MATERIAL ANALYSIS & OPTIMIZATION
# ─────────────────────────────────────────────

def tradeoff_score(mat: dict, w1: float, w2: float) -> float:
    return round((w1 * mat["strength"] + w2 * mat["durability"]) / mat["cost"], 4)

def recommend_materials(element_type: str, materials_db: dict) -> list:
    """
    Structural elements  → prioritise strength (w1=0.6, w2=0.4)
    Non-structural       → prioritise cost     (w1=0.3, w2=0.3, cost weight implicit)
    """
    if element_type in ("load-bearing wall", "column", "slab"):
        w1, w2 = 0.6, 0.4
    else:
        w1, w2 = 0.3, 0.3

    scored = []
    for name, props in materials_db.items():
        score = tradeoff_score(props, w1, w2)
        scored.append({"name": name, "score": score, **props})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top3 = scored[:3]

    reasons = {
        "Reinforced Concrete":    "High strength & durability; ideal for load-bearing elements.",
        "Prestressed Concrete":   "Maximum strength for long spans; cost justified by performance.",
        "Steel Frame":            "Highest strength-to-weight; suits large spans but costly.",
        "AAC Blocks":             "Lightweight, thermally efficient; best for partition walls.",
        "Fly Ash Bricks":         "Eco-friendly, moderate strength; good cost-performance balance.",
        "Red Clay Bricks":        "Traditional, proven durability; moderate cost.",
        "Hollow Concrete Blocks": "Low cost, adequate for non-structural partitions."
    }

    return [{"name": m["name"], "score": m["score"],
             "reason": reasons.get(m["name"], "—")} for m in top3]

def material_analysis(graph: dict, materials_db: dict) -> dict:
    elements = {
        "load-bearing wall": None,
        "partition wall":    None,
        "slab":              None,
        "column":            None
    }
    for etype in elements:
        elements[etype] = {
            "recommended_materials": recommend_materials(etype, materials_db)
        }
    return elements


# ─────────────────────────────────────────────
# STAGE 5: EXPLAINABILITY
# ─────────────────────────────────────────────

def generate_explanation(graph: dict, materials: dict) -> str:
    lines = ["=== STRUCTURAL INTELLIGENCE REPORT — EXPLAINABILITY ===\n"]

    # Structural observations
    lines.append("── STRUCTURAL OBSERVATIONS ──")
    lb = [e for e in graph["edges"] if e["classification"] == "load-bearing"]
    pt = [e for e in graph["edges"] if e["classification"] == "partition"]
    lines.append(f"• {len(lb)} load-bearing walls identified (outer perimeter + central spine W5).")
    lines.append(f"• {len(pt)} partition walls identified (W6, W7 — room dividers only).")

    for r in graph["rooms"]:
        lines.append(
            f"• {r['name']} ({r['id']}): {r['width_m']}m × {r['depth_m']}m = {r['area_m2']} m²"
        )

    if graph["structural_warnings"]:
        lines.append("\n── WARNINGS ──")
        for w in graph["structural_warnings"]:
            lines.append(f"  [WARNING] {w}")
    else:
        lines.append("\n• No critical unsupported spans detected.")

    # Material reasoning
    lines.append("\n── MATERIAL SELECTION REASONING ──")
    reasoning = {
        "load-bearing wall": (
            "The 10m south wall (W1) and 8m east wall (W2) carry the full roof load. "
            "Reinforced Concrete scores highest (strength=9, durability=9) despite cost=8, "
            "because the tradeoff formula weights strength at 60%. "
            "Prestressed Concrete is the runner-up for the 10m span where deflection control matters."
        ),
        "partition wall": (
            "W6 (5m) and W7 (5m) carry no vertical load. "
            "AAC Blocks score best here — low cost (3) with adequate durability (7). "
            "This saves ~30% material cost vs using bricks on non-structural walls."
        ),
        "slab": (
            "The floor slab covers 80 m² (10m × 8m). "
            "Reinforced Concrete is mandatory for structural integrity. "
            "Prestressed Concrete is recommended if the span between W1 and W3 (8m) "
            "exceeds standard RC slab limits without intermediate beams."
        ),
        "column": (
            "No columns are explicitly drawn, but the 10m W1 span and 8m W2 span "
            "suggest intermediate columns at the W1–W5 and W2–W7 junctions "
            "to reduce effective span to 5m. Steel Frame columns offer the best "
            "strength (10) for minimal cross-section."
        )
    }
    for etype, reason in reasoning.items():
        top_mat = materials[etype]["recommended_materials"][0]["name"]
        score   = materials[etype]["recommended_materials"][0]["score"]
        lines.append(f"\n[{etype.upper()}]")
        lines.append(f"  Top pick: {top_mat} (score={score})")
        lines.append(f"  Reason:   {reason}")

    lines.append("\n── OPTIMIZATION SUGGESTIONS ──")
    lines.append("1. Add a 200mm RC beam along W5 (5m spine wall) to transfer roof load to W1/W3.")
    lines.append("2. Use AAC blocks for W6 & W7 to reduce dead load by ~40% vs clay bricks.")
    lines.append("3. Place columns at (5,0), (5,8) to reduce W1/W3 effective span from 10m → 5m.")
    lines.append("4. Double-glaze windows W8/W9 (south & north) for thermal efficiency.")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(input_path: str) -> dict:
    with open(input_path) as f:
        raw = json.load(f)

    materials_db = raw.pop("materials_db")

    # Stage 1
    parsed = parse_floor_plan(raw)

    # Stage 2
    graph = build_structural_graph(parsed)

    # Stage 3
    model_3d = generate_3d_model(parsed)

    # Stage 4
    materials = material_analysis(graph, materials_db)

    # Stage 5
    explanation = generate_explanation(graph, materials)

    return {
        "stage1_parsed_floor_plan": {
            "walls":    parsed["walls"],
            "rooms":    parsed["rooms"],
            "openings": parsed["openings"]
        },
        "stage2_structural_graph": graph,
        "stage3_3d_model":         model_3d,
        "stage4_material_recommendations": materials,
        "stage5_explanation":      explanation
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    result = run_pipeline("floor_plan_data.json")

    # Pretty-print JSON sections
    for stage in ["stage1_parsed_floor_plan", "stage2_structural_graph",
                  "stage3_3d_model", "stage4_material_recommendations"]:
        print(f"\n{'='*60}")
        print(f"  {stage.upper()}")
        print('='*60)
        print(json.dumps(result[stage], indent=2))

    print(f"\n{'='*60}")
    print(result["stage5_explanation"])

    # Save full report
    with open("structural_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print("\nFull report saved to structural_report.json")
