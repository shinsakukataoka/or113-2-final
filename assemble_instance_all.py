"""
Create every combination of
  • 4 courses out of 8  (70 combos)
  • 3 study-style patterns  (stem / soc / hum)
  • 3 work-ethic levels     (lazy / normal / hard)
= 630 JSON instances.
Output goes to ./instances/
"""

import json, itertools, os, random, math
from pathlib import Path

# ------------------------------------------------------------------ #
# Load course catalog (must exist)                                   #
# ------------------------------------------------------------------ #
if not Path("courses.json").exists():
    raise SystemExit("Courses.json not found. Run build_course_catalog.py first.")

with open("courses.json") as f:
    catalog = json.load(f)

COURSES = catalog["I"]                # eight course codes
TASKS   = catalog["J"]                # dict of task lists

# ------------------------------------------------------------------ #
# Student-profile templates                                          #
# ------------------------------------------------------------------ #
STYLE2CAT = dict(stem="STEM", soc="SOC", hum="HUM")
WORK_LEVELS = {
    "lazy":   dict(beta=1.0,  H=4),
    "normal": dict(beta=0.5,  H=8),
    "hard":   dict(beta=0.2, H=12),
}
MULT = dict(fav=1.2, norm=1.0, weak=0.8)

course_cat = catalog["category"]      # course → STEM/SOC/HUM
DAYS, SHIFTS = 115, 16

def build_P_template(style):
    """Return {course: {"*": coeff}}"""
    fav = STYLE2CAT[style]
    P = {}
    for c, cat in course_cat.items():
        if cat == fav:
            group = "fav"
        elif (fav, cat) in {("STEM","HUM"), ("HUM","STEM")}:
            group = "weak"
        else:
            group = "norm"
        P[c] = {"*": MULT[group]}
    return P

def expand_P(template, tasks):
    """Expand {"*": coeff} to every (k,t) for the chosen tasks."""
    full = {}
    for c in tasks:                       # only selected courses
        coeff = template[c]["*"]
        full[c] = {}
        for t in tasks[c]:
            for k in range(1, DAYS+1):
                for s in range(2, SHIFTS):            # shifts 2-15
                    full[c].setdefault(t, {})[str((k,s))] = coeff
    return full

# ------------------------------------------------------------------ #
# Helper to slice big dicts                                          #
# ------------------------------------------------------------------ #
def sub(d):
    return {c: d[c] for c in combo}

# ------------------------------------------------------------------ #
# Make output dir                                                    #
# ------------------------------------------------------------------ #
os.makedirs("instances", exist_ok=True)

# ------------------------------------------------------------------ #
# Generate all 70 × 9 instances                                      #
# ------------------------------------------------------------------ #
count = 0
for combo in itertools.combinations(COURSES, 4):        # choose 4 courses
    combo = list(combo)
    task_subset = {c: TASKS[c] for c in combo}

    # data fixed across work-style loops
    base = dict(
        K=list(range(1, DAYS+1)),
        T=list(range(1, SHIFTS+1)),
        I=combo,
        J=task_subset,
        S=sub(catalog["S"]),
        E=sub(catalog["E"]),
        r=sub(catalog["r"]),
        d=sub(catalog["d"]),
        slot={c: catalog["slot"].get(c, {}) for c in combo},
        w={c: 1.0 for c in combo},                # equal weights
        B={c: 0.6 for c in combo},               # pass line
    )

    for style, work in itertools.product(STYLE2CAT, WORK_LEVELS):
        profP = build_P_template(style)
        inst = base.copy()
        inst["beta"] = WORK_LEVELS[work]["beta"]
        inst["H*"]   = {str(k): WORK_LEVELS[work]["H"] for k in range(1, DAYS+1)}
        inst["P"]    = expand_P(profP, task_subset)

        fname = (
            "instance_" + "_".join(combo) +
            f"__{style}_{work}.json"
        )
        with open(Path("instances") / fname, "w") as f:
            json.dump(inst, f, indent=2)
        count += 1

print(f"✅  {count} instances written to ./instances/")
