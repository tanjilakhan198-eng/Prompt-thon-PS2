# material_analysis.py
# Stage 4: Material Analysis, Cost-Strength Tradeoff, Cost Estimation & Quantities

MATERIALS_DB = {
    "Reinforced Concrete":    {"strength":9,  "durability":9,  "cost":8,  "unit":"m3",   "cost_inr":6500},
    "Prestressed Concrete":   {"strength":10, "durability":10, "cost":9,  "unit":"m3",   "cost_inr":8000},
    "Steel Frame":            {"strength":10, "durability":9,  "cost":10, "unit":"kg",   "cost_inr":75},
    "AAC Blocks":             {"strength":5,  "durability":7,  "cost":3,  "unit":"m3",   "cost_inr":3500},
    "Fly Ash Bricks":         {"strength":6,  "durability":7,  "cost":4,  "unit":"1000", "cost_inr":5000},
    "Red Clay Bricks":        {"strength":6,  "durability":6,  "cost":5,  "unit":"1000", "cost_inr":7000},
    "Hollow Concrete Blocks": {"strength":5,  "durability":6,  "cost":3,  "unit":"m3",   "cost_inr":3200},
    "Timber Frame":           {"strength":6,  "durability":5,  "cost":6,  "unit":"m3",   "cost_inr":45000},
    "Glass Fibre Reinforced": {"strength":7,  "durability":8,  "cost":9,  "unit":"m2",   "cost_inr":1200},
}

ELEMENT_WEIGHTS = {
    "load-bearing wall": (0.6, 0.4),
    "partition wall":    (0.2, 0.3),
    "slab":              (0.6, 0.4),
    "column":            (0.7, 0.3),
}

ELEMENT_SUITABLE = {
    "load-bearing wall": ["Reinforced Concrete","Prestressed Concrete","Steel Frame","Red Clay Bricks","Fly Ash Bricks"],
    "partition wall":    ["AAC Blocks","Hollow Concrete Blocks","Fly Ash Bricks","Red Clay Bricks","Timber Frame"],
    "slab":              ["Reinforced Concrete","Prestressed Concrete","Steel Frame"],
    "column":            ["Reinforced Concrete","Steel Frame","Prestressed Concrete"],
}

REASONS = {
    "Reinforced Concrete":    "High compressive strength (9/10) and excellent durability. Standard choice for structural elements in Indian construction.",
    "Prestressed Concrete":   "Maximum strength (10/10) for long spans. Reduces deflection and cracking. Best for spans > 6m.",
    "Steel Frame":            "Highest strength-to-weight ratio. Ideal for large spans and columns. Higher cost but minimal cross-section.",
    "AAC Blocks":             "Lightweight (1/3 of brick weight), thermally efficient, easy to cut. Best for non-load-bearing partitions.",
    "Fly Ash Bricks":         "Eco-friendly (uses industrial waste), uniform size, moderate strength. Good cost-performance for partitions.",
    "Red Clay Bricks":        "Traditional material, proven durability, good thermal mass. Moderate cost, widely available.",
    "Hollow Concrete Blocks": "Lowest cost option, adequate for non-structural partitions. Reduces dead load.",
    "Timber Frame":           "Good strength-to-weight, natural insulator. Higher cost, requires treatment against moisture.",
    "Glass Fibre Reinforced": "Lightweight, corrosion-resistant. Suitable for decorative or non-structural panels.",
}

COST_RATES = {
    "concrete_per_m3":     6500,
    "steel_per_kg":        75,
    "formwork_per_m2":     350,
    "labour_per_m2":       450,
    "brick_per_1000":      7000,
    "aac_block_per_m3":    3500,
    "mortar_per_m3":       4500,
    "plaster_per_m2":      120,
    "paint_per_m2":        85,
    "tile_floor_per_m2":   650,
    "door_per_unit":       12000,
    "window_per_m2":       4500,
    "electrical_per_m2":   350,
    "plumbing_per_m2":     280,
    "sanitary_per_unit":   8000,
    "contractor_overhead": 0.15,
    "contingency":         0.10,
}

WALL_HEIGHT  = 3.0
SLAB_THICK   = 0.15
COL_SIZE     = 0.3
WASTE_FACTOR = 1.05
BRICK_PER_M3 = 500
MORTAR_RATIO = 0.30

# ── 1. TRADEOFF SCORING ───────────────────────────────────────

def tradeoff_score(mat, w1, w2):
    return round((w1 * mat["strength"] + w2 * mat["durability"]) / mat["cost"], 4)

def rank_materials(element_type, span_m=0):
    w1, w2   = ELEMENT_WEIGHTS.get(element_type, (0.4, 0.3))
    suitable = ELEMENT_SUITABLE.get(element_type, list(MATERIALS_DB.keys()))
    scored   = []
    for name in suitable:
        mat   = MATERIALS_DB[name]
        score = tradeoff_score(mat, w1, w2)
        if element_type in ("load-bearing wall", "slab", "column") and mat["strength"] < 8:
            score = round(score * 0.5, 4)
        if span_m > 6.0 and mat["strength"] >= 9:
            score = round(score * 1.15, 4)
        if span_m > 4.0 and mat["strength"] <= 6:
            score = round(score * 0.85, 4)
        scored.append({
            "rank": 0, "name": name, "score": score,
            "strength": mat["strength"], "durability": mat["durability"],
            "cost_index": mat["cost"],
            "cost_inr": f"Rs.{mat['cost_inr']:,}/{mat['unit']}",
            "reason": REASONS[name],
            "formula": f"({w1}x{mat['strength']} + {w2}x{mat['durability']}) / {mat['cost']} = {score}"
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, m in enumerate(scored[:3]):
        m["rank"] = i + 1
    return scored[:3]

# ── 2. COST ESTIMATION ────────────────────────────────────────

def estimate_cost(summary, walls_2d, rooms):
    R        = COST_RATES
    fa       = summary.get("floor_area_m2", 50)
    lb_walls = [w for w in walls_2d if w.get("classification") == "load-bearing"]
    pt_walls = [w for w in walls_2d if w.get("classification") == "partition"]
    num_cols = max(len(lb_walls), 4)

    footing_vol  = num_cols * 1.5 * 1.5 * 0.6
    foundation   = round(footing_vol * R["concrete_per_m3"] + footing_vol * 120 * R["steel_per_kg"])

    col_vol      = num_cols * COL_SIZE * COL_SIZE * (WALL_HEIGHT + 0.5)
    columns_cost = round(col_vol * R["concrete_per_m3"] + col_vol * 120 * R["steel_per_kg"])

    lb_area      = sum(w["length_m"] * WALL_HEIGHT for w in lb_walls)
    lb_vol       = lb_area * 0.23
    lb_wall_cost = round(lb_vol * R["concrete_per_m3"] * 0.4 + lb_area * 250 * R["brick_per_1000"] / 1000 * 0.6)

    pt_area      = sum(w["length_m"] * WALL_HEIGHT for w in pt_walls)
    pt_vol       = pt_area * 0.15
    pt_wall_cost = round(pt_vol * R["aac_block_per_m3"] + pt_area * R["plaster_per_m2"] * 2)

    slab_vol     = fa * SLAB_THICK
    slab_cost    = round(slab_vol * R["concrete_per_m3"] + slab_vol * 80 * R["steel_per_kg"] + fa * R["formwork_per_m2"])
    roof_cost    = round(slab_cost * 1.1)
    floor_cost   = round(fa * R["tile_floor_per_m2"])

    total_wall   = lb_area + pt_area
    plaster_cost = round(total_wall * R["plaster_per_m2"])
    paint_cost   = round((total_wall + fa) * R["paint_per_m2"])

    num_doors    = max(summary.get("total_doors",   2), 2)
    num_windows  = max(summary.get("total_windows", 3), 2)
    door_cost    = round(num_doors   * R["door_per_unit"])
    window_cost  = round(num_windows * 1.2 * R["window_per_m2"])

    electrical   = round(fa * R["electrical_per_m2"])
    plumbing     = round(fa * R["plumbing_per_m2"])
    num_baths    = sum(1 for r in rooms if r.get("type") == "Bathroom")
    sanitary     = round(max(num_baths, 1) * R["sanitary_per_unit"])
    labour       = round(fa * R["labour_per_m2"] * 2.5)

    direct = (foundation + columns_cost + lb_wall_cost + pt_wall_cost +
              slab_cost + roof_cost + floor_cost + plaster_cost +
              paint_cost + door_cost + window_cost + electrical +
              plumbing + sanitary + labour)

    overhead    = round(direct * R["contractor_overhead"])
    contingency = round(direct * R["contingency"])
    total       = direct + overhead + contingency
    fa_sqft     = round(fa * 10.764, 1)

    return {
        "breakdown": {
            "Foundation":         foundation,
            "Columns":            columns_cost,
            "Load-Bearing Walls": lb_wall_cost,
            "Partition Walls":    pt_wall_cost,
            "Floor Slab":         slab_cost,
            "Roof Slab":          roof_cost,
            "Flooring (Tiles)":   floor_cost,
            "Plaster":            plaster_cost,
            "Paint":              paint_cost,
            "Doors":              door_cost,
            "Windows":            window_cost,
            "Electrical":         electrical,
            "Plumbing":           plumbing,
            "Sanitary":           sanitary,
            "Labour":             labour,
        },
        "subtotal":           direct,
        "overhead_15pct":     overhead,
        "contingency_10pct":  contingency,
        "total_inr":          total,
        "total_lakhs":        round(total / 100000, 2),
        "floor_area_m2":      fa,
        "floor_area_sqft":    fa_sqft,
        "cost_per_sqft":      round(total / fa_sqft) if fa_sqft > 0 else 0,
        "cost_per_m2":        round(total / fa)      if fa > 0      else 0,
    }

# ── 3. MATERIAL QUANTITIES ────────────────────────────────────

def calc_quantities(summary, walls_2d, rooms):
    fa       = summary.get("floor_area_m2", 50)
    lb       = [w for w in walls_2d if w.get("classification") == "load-bearing"]
    pt       = [w for w in walls_2d if w.get("classification") == "partition"]
    num_cols = max(len(lb), 4)

    lb_area  = sum(w["length_m"] * WALL_HEIGHT for w in lb)
    pt_area  = sum(w["length_m"] * WALL_HEIGHT for w in pt)

    lb_vol    = round(lb_area * 0.23 * WASTE_FACTOR, 2)
    pt_vol    = round(pt_area * 0.15 * WASTE_FACTOR, 2)
    slab_vol  = round(fa * SLAB_THICK * WASTE_FACTOR, 2)
    col_vol   = round(num_cols * COL_SIZE * COL_SIZE * (WALL_HEIGHT + 0.5) * WASTE_FACTOR, 2)
    found_vol = round(num_cols * 1.5 * 1.5 * 0.6 * WASTE_FACTOR, 2)

    total_concrete = round(lb_vol * 0.4 + slab_vol + col_vol + found_vol, 2)
    total_steel_kg = round(total_concrete * 100, 1)

    brick_vol    = round(lb_vol * 0.6, 2)
    num_bricks   = round(brick_vol * BRICK_PER_M3)
    mortar_m3    = round(brick_vol * MORTAR_RATIO, 2)
    aac_m3       = round(pt_vol, 2)
    plaster_m2   = round((lb_area + pt_area) * 2, 1)
    plaster_bags = round(plaster_m2 * 0.45)
    cement_bags  = round(mortar_m3 * 8 + slab_vol * 6 + col_vol * 6)
    sand_m3      = round(mortar_m3 * 0.45 + slab_vol * 0.45, 2)
    aggregate_m3 = round(slab_vol * 0.9 + col_vol * 0.9, 2)
    paint_area   = round(plaster_m2 + fa, 1)
    paint_ltrs   = round(paint_area / 10)
    tile_m2      = round(fa * WASTE_FACTOR, 1)
    num_doors    = max(summary.get("total_doors",   2), 2)
    num_windows  = max(summary.get("total_windows", 3), 2)

    return {
        "Concrete (RCC)":        {"qty": total_concrete, "unit": "m3",        "note": f"Slab {slab_vol} + Columns {col_vol} + Foundation {found_vol} + LB walls {round(lb_vol*0.4,2)} m3"},
        "Steel (TMT Bars)":      {"qty": total_steel_kg, "unit": "kg",        "note": f"~100 kg per m3 of concrete ({total_concrete} m3)"},
        "Red Clay Bricks":       {"qty": num_bricks,     "unit": "nos",       "note": f"{brick_vol} m3 brickwork x {BRICK_PER_M3} bricks/m3"},
        "AAC Blocks (Partition)":{"qty": aac_m3,         "unit": "m3",        "note": f"{pt_area:.1f} m2 partition wall x 0.15m thick"},
        "Cement (OPC 53)":       {"qty": cement_bags,    "unit": "bags(50kg)","note": "For mortar, slab, columns and plaster"},
        "Sand (Fine)":           {"qty": sand_m3,        "unit": "m3",        "note": "For mortar and plastering"},
        "Aggregate (20mm)":      {"qty": aggregate_m3,   "unit": "m3",        "note": "For RCC slab and columns"},
        "Plaster (12mm)":        {"qty": plaster_m2,     "unit": "m2",        "note": f"Both sides of all walls ({plaster_bags} bags)"},
        "Paint (Emulsion)":      {"qty": paint_ltrs,     "unit": "litres",    "note": f"{paint_area} m2 total area (walls + ceiling)"},
        "Floor Tiles":           {"qty": tile_m2,        "unit": "m2",        "note": f"{fa} m2 floor + 5% wastage"},
        "Doors":                 {"qty": num_doors,      "unit": "nos",       "note": "Main door + room doors"},
        "Windows":               {"qty": num_windows,    "unit": "nos",       "note": "UPVC / aluminium frame windows"},
    }

# ── 4. MAIN FUNCTION ──────────────────────────────────────────

def analyse_materials(summary, walls_2d, rooms=None):
    if rooms is None:
        rooms = []

    lb_spans   = [w["length_m"] for w in walls_2d if w.get("classification") == "load-bearing"]
    pt_spans   = [w["length_m"] for w in walls_2d if w.get("classification") == "partition"]
    max_lb     = max(lb_spans) if lb_spans else 5.0
    max_pt     = max(pt_spans) if pt_spans else 3.0
    floor_area = summary.get("floor_area_m2", 50)

    elements = {
        "load-bearing wall": rank_materials("load-bearing wall", max_lb),
        "partition wall":    rank_materials("partition wall",    max_pt),
        "slab":              rank_materials("slab",              max_lb),
        "column":            rank_materials("column",            max_lb),
    }

    explanations = {}
    for etype, mats in elements.items():
        top = mats[0]
        note = {"load-bearing wall": f" Longest span: {max_lb}m.",
                "slab":              f" Floor area: {floor_area} m2.",
                "column":            f" Reduces {max_lb}m span to ~5m.",
                "partition wall":    ""}.get(etype, "")
        explanations[etype] = (
            f"{top['name']} recommended (score={top['score']}).{note} "
            f"{top['reason']} Runner-up: {mats[1]['name']} (score={mats[1]['score']})."
        )

    return {
        "elements":     elements,
        "explanations": explanations,
        "cost_estimate": estimate_cost(summary, walls_2d, rooms),
        "quantities":    calc_quantities(summary, walls_2d, rooms),
        "formula_note":  "Score = (W1 x Strength + W2 x Durability) / Cost. Structural: W1=0.6, W2=0.4. Partition: W1=0.2, W2=0.3.",
        "context": {"max_lb_span_m": max_lb, "max_pt_span_m": max_pt, "floor_area_m2": floor_area}
    }
