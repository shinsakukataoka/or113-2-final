#!/usr/bin/env python3
"""
make_timmy_instance.py
----------------------
Create a single study-planning instance for *Timmy*.

Fixed choices
-------------
• Courses : all eight in the catalog
• β       : 0.0075
• H_k     : 6 (weekdays), 4 (weekends)
• Productivity P_{i,j,k,t} given by

      P_{i,j,k,t} = η_type(i,j) ⋅ (1+θ_i)
                    ⋅ [ 1 + cos( 2π/24 · (h_t − h_peak) ) ]

  with
      η_HW      = 1.0,   η_Lecture = 0.8,   η_Exam = 1.2
      θ_i       course-specific (see THETA dict)
      h_peak    = 5  (circadian peak hour, 0–23)
      h_t       mid-point clock time of shift t (16×1.5 h grid → 0–24)

Output
------
./instances/Timmy/instance_Timmy.json
"""

import json, math, os
from pathlib import Path

# ------------------------------------------------------------------ #
# Locate and load the course catalog                                 #
# ------------------------------------------------------------------ #
CATALOG_FILE = Path("courses.json")
if not CATALOG_FILE.exists():
    raise SystemExit("courses.json not found – run build_course_catalog.py first.")

with CATALOG_FILE.open() as f:
    catalog = json.load(f)

COURSES   = catalog["I"]           # list of 8 course codes
TASKS_ALL = catalog["J"]           # dict course → [task names]
course_cat = catalog["category"]   # course → STEM/SOC/HUM

# ------------------------------------------------------------------ #
# Global constants                                                   #
# ------------------------------------------------------------------ #
DAYS, SHIFTS = 115, 16
H_PEAK       = 5                   # Timmy’s daily energy peak hour (0–23)

# θ_i : enthusiasm per course (−1 … +1)
THETA = {
    "IM2010":   1.0,
    "MATH4008": 0.8,
    "MATH4010": 0.8,
    "CSIE1212": 1.0,
    "ECON1023": 0.6,
    "JPNL2018": 0.8,
    "IM3004":   0.4,
    "MGT1002":  0.8,
}

# Baseline credit-weights (unchanged)
CREDIT = {
    "IM2010":   3,
    "MATH4008": 2,
    "MATH4010": 2,
    "CSIE1212": 3,
    "ECON1023": 3,
    "JPNL2018": 3,
    "IM3004":   3,
    "MGT1002":  3,
}

# η for task categories
ETA = dict(Homework=1.0, Lecture=0.8, Exam=1.2)

# ------------------------------------------------------------------ #
# Helpers                                                            #
# ------------------------------------------------------------------ #
def detect_category(task_name: str) -> str:
    """Return 'Exam', 'Lecture', or 'Homework'."""
    name = task_name.lower()
    if "exam" in name or "quiz" in name:
        return "Exam"
    if "lecture" in name:
        return "Lecture"
    return "Homework"

def shift_midpoint_hour(t: int) -> float:
    """16 shifts, evenly covering 0‒24 h; return mid-point hour of shift t (1-based)."""
    slot = 24 / SHIFTS              # 1.5 h
    return (t - 0.5) * slot         # e.g. t=1 → 0.75h

def build_H_star() -> dict[str,int]:
    """H_k: 6 on weekdays, 4 on weekends (day1 = Monday)."""
    H = {}
    for k in range(1, DAYS + 1):
        weekday = (k % 7) not in (6, 0)   # k%7==6 (Sat), 0 (Sun) → weekend
        H[str(k)] = 4 if weekday else 2
    return H

def expand_P(tasks: dict[str,list]) -> dict:
    """
    P[c][task]['(k,t)'] = η_cat · (1+θ_i) · [1 + cos(2π/24·(h_t-h_peak))]
    """
    P_out = {}
    for c in COURSES:
        theta      = THETA[c]
        P_out[c]   = {}
        for task in tasks[c]:
            cat     = detect_category(task)
            eta     = ETA[cat]
            factor1 = eta * (1 + theta)   # constant over k,t
            P_out[c][task] = {}
            for k in range(1, DAYS + 1):
                for t in range(1, SHIFTS + 1):
                    h_t   = shift_midpoint_hour(t)
                    circ  = 1 + math.cos(2 * math.pi / 24 * (h_t - H_PEAK))
                    coeff = round(factor1 * circ, 3)
                    P_out[c][task][f"({k},{t})"] = coeff
    return P_out

# ------------------------------------------------------------------ #
# Assemble the single instance                                       #
# ------------------------------------------------------------------ #
STUDENT = "Timmy"
tasks_subset = {c: TASKS_ALL[c] for c in COURSES}

instance = dict(
    K=list(range(1, DAYS + 1)),
    T=list(range(1, SHIFTS + 1)),
    I=COURSES,
    J=tasks_subset,
    S={c: catalog["S"][c] for c in COURSES},
    E={c: catalog["E"][c] for c in COURSES},
    r={c: catalog["r"][c] for c in COURSES},
    d={c: catalog["d"][c] for c in COURSES},
    slot={c: catalog["slot"].get(c, {}) for c in COURSES},
    w={c: CREDIT[c] for c in COURSES},
    B={c: 0.6 for c in COURSES},
    beta=0.05,
    **{"H*": build_H_star()},
    P=expand_P(tasks_subset),
)

# ------------------------------------------------------------------ #
# Write result                                                       #
# ------------------------------------------------------------------ #
out_dir  = Path("instances") / STUDENT
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "instance_Timmy.json"

with out_file.open("w") as f:
    json.dump(instance, f, indent=2)

print(f"✓ Instance written to {out_file}")
