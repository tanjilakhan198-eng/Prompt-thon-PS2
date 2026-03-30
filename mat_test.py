import sys
sys.stdout.reconfigure(encoding="utf-8")
from material_analysis import analyse_materials

summary = {"floor_area_m2": 80, "building_width_m": 10}
walls   = [
    {"classification": "load-bearing", "length_m": 10.0},
    {"classification": "load-bearing", "length_m": 8.0},
    {"classification": "partition",    "length_m": 5.0},
]
result = analyse_materials(summary, walls)

for etype, mats in result["elements"].items():
    print(f"\n{etype.upper()}")
    for m in mats:
        print(f"  #{m['rank']} {m['name']:<30} score={m['score']}  {m['cost_inr']}")
    print(f"  Explain: {result['explanations'][etype][:120]}...")

print("\n" + result["formula_note"])
print("\nApp import check:")
from app import app
print("app OK")
