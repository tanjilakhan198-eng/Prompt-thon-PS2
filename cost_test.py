import sys
sys.stdout.reconfigure(encoding="utf-8")
from material_analysis import estimate_cost

summary = {"floor_area_m2":80,"building_width_m":10,"total_doors":3,"total_windows":4}
walls   = [{"classification":"load-bearing","length_m":10},
           {"classification":"load-bearing","length_m":8},
           {"classification":"partition","length_m":5}]
rooms   = [{"type":"Bathroom"},{"type":"Bedroom"},{"type":"Living Room"}]

ce = estimate_cost(summary, walls, rooms)
print(f"Total Cost  : Rs.{ce['total_inr']:,}")
print(f"In Lakhs    : {ce['total_lakhs']} Lakhs")
print(f"Per sq.ft   : Rs.{ce['cost_per_sqft']:,}")
print(f"Per m2      : Rs.{ce['cost_per_m2']:,}")
print(f"Area        : {ce['floor_area_sqft']} sq.ft")
print("\nBreakdown:")
for k, v in ce["breakdown"].items():
    print(f"  {k:<25} Rs.{v:>10,}")
print(f"  {'Overhead (15%)':<25} Rs.{ce['overhead_15pct']:>10,}")
print(f"  {'Contingency (10%)':<25} Rs.{ce['contingency_10pct']:>10,}")
print(f"  {'TOTAL':<25} Rs.{ce['total_inr']:>10,}")
