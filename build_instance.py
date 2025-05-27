#!/usr/bin/env python3
"""
Convert the detailed 115-day course schedule into a MILP-ready JSON instance.

* 16 one-hour shifts per day:
    1 = 07-08, …, 16 = 22-23
* Productivity P is set to 1.0 for every (k,t) within a task’s release-deadline window.
  That keeps the JSON compact while still letting the solver work.
* Fixed-slot exams are handled by
  – allowing preparation any time up to the exam day, and
  – forcing attendance in the exact exam shifts.

Written for the table supplied 27-May-2025.
"""

import json
from collections import defaultdict

# ---------------------------------------------------------------------#
# 1. CONTRACT:  Put every task below as one dictionary row              #
# ---------------------------------------------------------------------#
TASKS = [
    # ---- IM2010 Operations Research ---------------------------------
    dict(course="IM2010", name="HW0",              type="Homework", weight=0,
         rel=1,  due=7,   slot=None, E=2),
    dict(course="IM2010", name="Homework 1",       type="Homework", weight=5,
         rel=22, due=26,  slot=None, E=4),
    dict(course="IM2010", name="Homework 2",       type="Homework", weight=5,
         rel=29, due=33,  slot=None, E=4),
    dict(course="IM2010", name="Homework 3",       type="Homework", weight=5,
         rel=78, due=82,  slot=None, E=4),
    dict(course="IM2010", name="FPP",              type="Homework", weight=0,
         rel=36, due=40,  slot=None, E=3),
    dict(course="IM2010", name="Midterm Project",  type="Homework", weight=20,
         rel=64, due=82,  slot=None, E=12),
    dict(course="IM2010", name="FP Video",         type="Homework", weight=0,
         rel=85, due=96,  slot=None, E=8),
    dict(course="IM2010", name="FP Report",        type="Homework", weight=25,
         rel=85, due=96,  slot=None, E=10),
    dict(course="IM2010", name="Midterm Exam",     type="Exam",     weight=12,
         rel=1,  due=50,  slot=[(50,2), (50,3), (50,4)], E=6),
    dict(course="IM2010", name="Final Exam",       type="Exam",     weight=18,
         rel=1,  due=106, slot=[(106,2), (106,3), (106,4)], E=6),
    dict(course="IM2010", name="Survey/Admin",     type="Homework", weight=5,
         rel=1,  due=106, slot=None, E=1),

    dict(course="IM2010", name="Pre-lecture W1",   type="Homework", weight=1,
         rel=44, due=44,  slot=[(44,2), (44,3), (44,4)], E=1),
    dict(course="IM2010", name="Pre-lecture W2",   type="Homework", weight=1,
         rel=51, due=51,  slot=[(51,2), (51,3), (51,4)], E=1),
    dict(course="IM2010", name="Pre-lecture W3",   type="Homework", weight=1,
         rel=58, due=58,  slot=[(58,2), (58,3), (58,4)], E=1),
    dict(course="IM2010", name="Pre-lecture W4",   type="Homework", weight=1,
         rel=65, due=65,  slot=[(65,2), (65,3), (65,4)], E=1),
    dict(course="IM2010", name="Pre-lecture W5",   type="Homework", weight=1,
         rel=72, due=72,  slot=[(72,2), (72,3), (72,4)], E=1),

    # ---- MATH4008 Calculus III --------------------------------------
    dict(course="MATH4008", name="Worksheet 1", type="Homework", weight=7,
         rel=8,  due=22,  slot=None, E=2),
    dict(course="MATH4008", name="Worksheet 2", type="Homework", weight=7,
         rel=22, due=36,  slot=None, E=2),
    dict(course="MATH4008", name="Worksheet 3", type="Homework", weight=7,
         rel=36, due=50,  slot=None, E=2),
    dict(course="MATH4008", name="WeBWorK",    type="Homework", weight=10,
         rel=1,  due=56,  slot=None, E=4),
    dict(course="MATH4008", name="Quiz 1",     type="Exam",     weight=10,
         rel=1,  due=18,  slot=[(18,11)], E=3),
    dict(course="MATH4008", name="Quiz 2",     type="Exam",     weight=10,
         rel=1,  due=39,  slot=[(39,11)], E=3),
    dict(course="MATH4008", name="Final Exam", type="Exam",     weight=50,
         rel=1,  due=57,  slot=[(57,7), (57,8), (57,9)], E=8),

    # ---- MATH4010 Calculus IV ---------------------------------------
    dict(course="MATH4010", name="HW1",       type="Homework", weight=5,
         rel=68, due=82,  slot=None, E=2),
    dict(course="MATH4010", name="HW2",       type="Homework", weight=5,
         rel=82, due=96,  slot=None, E=2),
    dict(course="MATH4010", name="HW3",       type="Homework", weight=5,
         rel=96, due=109, slot=None, E=2),
    dict(course="MATH4010", name="WebWork",   type="Homework", weight=5,
         rel=57, due=109, slot=None, E=4),
    dict(course="MATH4010", name="Quiz 1",    type="Exam",     weight=15,
         rel=1,  due=82,  slot=[(82,11)], E=3),
    dict(course="MATH4010", name="Quiz 2",    type="Exam",     weight=15,
         rel=1,  due=96,  slot=[(96,11)], E=3),
    dict(course="MATH4010", name="Final Exam",type="Exam",     weight=50,
         rel=1,  due=111, slot=[(111,7), (111,8), (111,9)], E=8),

    # ---- CSIE1212 Data Structures & Algorithms ----------------------
    dict(course="CSIE1212", name="Homework 0", type="Homework", weight=4,
         rel=1,  due=64,  slot=None, E=6),
    dict(course="CSIE1212", name="Homework 1", type="Homework", weight=4,
         rel=22, due=36,  slot=None, E=8),
    dict(course="CSIE1212", name="Homework 2", type="Homework", weight=4,
         rel=36, due=64,  slot=None, E=8),
    dict(course="CSIE1212", name="Homework 3", type="Homework", weight=4,
         rel=57, due=78,  slot=None, E=8),
    dict(course="CSIE1212", name="Homework 4", type="Homework", weight=4,
         rel=78, due=92,  slot=None, E=8),

    # Mini-homework A–L (12 tasks × ≈1.67 %)
    *[
        dict(course="CSIE1212", name=f"MiniHW {lbl}", type="Homework",
             weight=1.67, rel=rel, due=64, slot=None, E=1.5)
        for lbl, rel in zip("ABCDEF", [8,15,22,29,36,43])
    ] + [
        dict(course="CSIE1212", name=f"MiniHW {lbl}", type="Homework",
             weight=1.67, rel=rel, due=115, slot=None, E=1.5)
        for lbl, rel in zip("GHIJKL", [43,57,71,85,99,92])
    ],

    dict(course="CSIE1212", name="Earth Game",      type="Activity", weight=4,
         rel=57, due=64,  slot=None, E=3),
    dict(course="CSIE1212", name="Software Dev Game", type="Activity", weight=3,
         rel=78, due=85,  slot=None, E=3),
    dict(course="CSIE1212", name="Kahoot Review",  type="Activity", weight=3,
         rel=92, due=99,  slot=None, E=1),

    dict(course="CSIE1212", name="With-Video Quizzes", type="OnlineQuiz",
         weight=0,   rel=1, due=115, slot=None, E=6),   # 0.25 h × 24 weeks

    dict(course="CSIE1212", name="Midterm Exam", type="Exam", weight=25,
         rel=1, due=50,  slot=[(50,8)], E=6),
    dict(course="CSIE1212", name="Final Exam",   type="Exam", weight=25,
         rel=1, due=106, slot=[(106,8)], E=6),
]

# ---------------------------------------------------------------------#
# 2.  Global parameters                                                #
# ---------------------------------------------------------------------#
DAYS      = 115
SHIFTS    = 16
HOURS_CAP = 8            # preferred max study hours per day
BETA      = 0.5          # overtime penalty
PASS_GRADE = 0.6         # 60 % floor for every course
CREDIT     = {           # course “importance” (any scale OK)
    "IM2010"  : 3,
    "MATH4008": 3,
    "MATH4010": 3,
    "CSIE1212": 3,
}

# ---------------------------------------------------------------------#
# 3.  Build JSON structure                                             #
# ---------------------------------------------------------------------#
instance = {
    "K": list(range(1, DAYS + 1)),
    "T": list(range(1, SHIFTS + 1)),
    "I": sorted({t["course"] for t in TASKS}),
    "J": defaultdict(list),
    "S": defaultdict(dict),
    "E": defaultdict(dict),
    "r": defaultdict(dict),
    "d": defaultdict(dict),
    "w": CREDIT,
    "B": {c: PASS_GRADE for c in CREDIT},
    "H*": {str(k): HOURS_CAP for k in range(1, DAYS + 1)},
    "beta": BETA,
    "P": defaultdict(lambda: defaultdict(dict)),   # filled below
}

# helper for three-letter ellipsis in names
def short(name, n=32):
    return (name[:n] + "…") if len(name) > n else name

# fill task-level sets and parameters
for t in TASKS:
    i, j = t["course"], short(t["name"])
    instance["J"][i].append(j)
    instance["S"][i][j] = round(t["weight"] / 100, 4)   # convert % → 0-1
    instance["E"][i][j] = t["E"]

    # release & due stored as simple day numbers
    instance["r"][i][j] = [t["rel"], 1]      # earliest shift = 1
    instance["d"][i][j] = [t["due"], SHIFTS]
    # -----------------------------------------------------------------
    # productivity: 1.0 if (k,t) within [rel, due] OR in fixed slot
    # -----------------------------------------------------------------
    if t["slot"]:            # fixed slot(s) must be available
        for k_t in t["slot"]:
            instance["P"][i][j][str(k_t)] = 1.0

    for k in range(t["rel"], t["due"] + 1):
        for s in range(1, SHIFTS + 1):
            # leave out hours 1 (midnight) & 16 (late night) for realism
            if 2 <= s <= 15:
                instance["P"][i][j][str((k, s))] = 1.0

#  defaultdicts → normal dicts for JSON
instance["J"] = dict(instance["J"])
instance["S"] = dict(instance["S"])
instance["E"] = dict(instance["E"])
instance["r"] = dict(instance["r"])
instance["d"] = dict(instance["d"])
instance["P"] = {i: {j: v for j, v in jj.items()} for i, jj in instance["P"].items()}

# ---------------------------------------------------------------------#
# 4.  Write to file                                                    #
# ---------------------------------------------------------------------#
with open("semester_115d.json", "w", encoding="utf-8") as f:
    json.dump(instance, f, indent=2, ensure_ascii=False)

print("✅  Instance file written: semester_115d.json  (",
      len(TASKS), "tasks)")
