#!/usr/bin/env python3
"""
build_course_catalog.py
---------------------------------
Creates courses.json – course-dependent data only.

NEW in this version
-------------------
• Weekly “Lecture Wk n” tasks (weight 0) are automatically
  added for **every course** so that normal contact hours
  count toward the effort budget.
• Keeps the EFFORT_FACTOR scaling and every other feature
  from the previous script.
"""

import json
from collections import defaultdict

# ------------------------------------------------------------------ #
# Global parameters                                                  #
# ------------------------------------------------------------------ #
EFFORT_FACTOR            = 3      # multiply all nominal efforts
EFFORT_FACTOR = {
    "IM2010":   1.99,
    "CSIE1212": 1.93,
    "ECON1023": 4.00,
    "JPNL2018": 3.27,
    "IM3004":   3.93,
    "MGT1002":  3.72,
    "MATH4008": 2.67,
    "MATH4010": 2.67,
}
LECTURE_HOURS_PER_WEEK   = 3        # total in-class hours / course / week
WEEKS                    = 15       # teaching weeks covered by the term
LAST_SHIFT               = 16       # 22–23 h
DEFAULT_EXAM_SHIFT       = 8        # 13:20–14:20  if no slot specified

# ------------------------------------------------------------------ #
# Helpers                                                            #
# ------------------------------------------------------------------ #
def add(course, name, w_pct, rel, due, effort,
        fixed=None, cat="STEM", tlist=None):
    """Generic task entry (effort still un-scaled here)."""
    tlist.append((course, name, w_pct, rel, due, effort, fixed, cat))

def add_exam(course, name, w_pct, due, effort,
             fixed=None, cat="STEM", tlist=None, window=21):
    """Adds a quiz / exam, auto-creates compulsory slot if missing."""
    rel = max(1, due - window)                   # start prep ≤ 3 weeks before
    if fixed is None:
        fixed = [(due, DEFAULT_EXAM_SHIFT)]
    add(course, name, w_pct, rel, due, effort, fixed, cat, tlist)

def add_weekly_lectures(tlist):
    """
    Inject a zero-weight ‘Lecture Wk n’ task for every course *unless* that
    course already has weekly graded attendance/participation entries
    (weight > 0).  This prevents double-counting the same contact hours.

    Lecture parameters if inserted:
      • weight  = 0.0                (no GPA impact)
      • effort  = LECTURE_HOURS_PER_WEEK / WEEKS   (≈ 0.2 h, later × EFFORT_FACTOR)
      • fixed   = None               (optimizer may place freely)
    """
    per_course = {c for c, *_ in tlist}
    weekly_eff = round(LECTURE_HOURS_PER_WEEK / WEEKS, 3)

    for course in per_course:
        # Does this course already have weekly graded participation tasks?
        has_weekly_graded = any(
            c == course and w_pct > 0 and (
                "Participation" in name or "Class Part" in name)
            for c, name, w_pct, *_ in tlist
        )
        if has_weekly_graded:
            continue   # skip lecture placeholders for this course

        # Otherwise, add lecture placeholders for every week
        cat = next(cat for c, _, _, _, _, _, _, cat in tlist if c == course)
        for w in range(1, WEEKS + 1):
            day = 1 + 7 * (w - 1)          # Monday of week w
            name = f"Lecture Wk {w}"
            add(course, name, 0.0, day, day, weekly_eff,
                fixed=None, cat=cat, tlist=tlist)

# ------------------------------------------------------------------ #
# TASK LIST  (unchanged original data)                               #
# ------------------------------------------------------------------ #
TASKS = []

# === 1. IM2010 Operations Research (SOC) ===========================
IM, im_cat = "IM2010", "SOC"
for row in [
    ("HW0",0, 1, 7,2), ("Homework 1",5,22,26,4),
    ("Homework 2",5,29,33,4), ("Homework 3",5,78,82,4),
    ("FPP",0,36,40,3), ("Midterm Project",20,64,82,12),
    ("FP Video",0,85,96,8), ("FP Report",25,85,96,10),
    ("Survey/Admin",5,1,106,1),
]:
    add(IM, *row, None, im_cat, TASKS)

add_exam(IM, "Midterm Exam", 12, 50, 6+3,
         fixed=[(50,2),(50,3),(50,4)], cat=im_cat, tlist=TASKS)
add_exam(IM, "Final Exam",   18,106, 6+3,
         fixed=[(106,2),(106,3),(106,4)], cat=im_cat, tlist=TASKS)

for w,d in enumerate([44,51,58,65,72], start=1):
    add(IM, f"Pre-lecture W{w}", 1, d, d, 1,
        None,           
        im_cat,
        TASKS)

# === 2. MATH4008 Calculus III (STEM) ===============================
M8, cat8 = "MATH4008","STEM"
for nm,w,rel,due,e in [
    ("Worksheet 1",7, 8,22,2), ("Worksheet 2",7,22,36,2),
    ("Worksheet 3",7,36,50,2), ("WeBWorK", 10,1,56,4)
]:
    add(M8, nm, w, rel, due, e, None, cat8, TASKS)
add_exam(M8,"Quiz 1",10,18,3+1,fixed=[(18,11)],cat=cat8,tlist=TASKS)
add_exam(M8,"Quiz 2",10,39,3+1,fixed=[(39,11)],cat=cat8,tlist=TASKS)
add_exam(M8,"Final Exam",50,57,8+3,
         fixed=[(57,7),(57,8),(57,9)],cat=cat8,tlist=TASKS)

# === 3. MATH4010 Calculus IV (STEM) ================================
M10, cat10 = "MATH4010","STEM"
for nm,w,rel,due,e in [
    ("HW1",5,68,82,2), ("HW2",5,82,96,2),
    ("HW3",5,96,109,2), ("WebWork",5,57,109,4)
]:
    add(M10,nm,w,rel,due,e,None,cat10,TASKS)
add_exam(M10,"Quiz 1",15,82,3+1,fixed=[(82,11)],cat=cat10,tlist=TASKS)
add_exam(M10,"Quiz 2",15,96,3+1,fixed=[(96,11)],cat=cat10,tlist=TASKS)
add_exam(M10,"Final Exam",50,111,8+3,
         fixed=[(111,7),(111,8),(111,9)],cat=cat10,tlist=TASKS)

# === 4. CSIE1212 Data Structures (STEM) ============================
CS, ccat = "CSIE1212","STEM"
for i,(rel,due,e) in enumerate([(1,64,6),(22,36,8),(36,64,8),
                                (57,78,8),(78,92,8)]):
    add(CS,f"Homework {i}",4,rel,due,e,None,ccat,TASKS)
for lbl,rel,due in zip("ABCDEF",[8,15,22,29,36,43],[64]*6):
    add(CS,f"Mini HW {lbl}",10/12,rel,due,1.5,None,ccat,TASKS)
for lbl,rel,due in zip("GHIJKL",[43,57,71,85,99,92],[115]*6):
    add(CS,f"Mini HW {lbl}",10/12,rel,due,1.5,None,ccat,TASKS)
for nm,w,rel,due,e in [("Earth Game",4,57,64,3),
                       ("Software Dev Game",3,78,85,3),
                       ("Kahoot Review",3,92,99,1)]:
    add(CS,nm,w,rel,due,e,None,ccat,TASKS)
add_exam(CS,"With-Video Quizzes",0,115,6,cat=ccat,tlist=TASKS)
add_exam(CS,"Midterm Exam",25, 50,6+1,fixed=[(50,8)], cat=ccat,tlist=TASKS)
add_exam(CS,"Final Exam", 25,106,6+1,fixed=[(106,8)], cat=ccat,tlist=TASKS)

# === 5. ECON1023 Macroeconomics (SOC) ==============================
EC, ecat = "ECON1023","SOC"
for q,(rel,due,day) in enumerate(
        [(14,26,26),(23,33,33),(30,40,40),
         (42,54,54),(54,68,68),(61,75,75)], start=1):
    add_exam(EC,f"Quiz {q}",4,due,2,fixed=[(day,4)],cat=ecat,tlist=TASKS)
add_exam(EC,"Midterm Exam",40, 56,6+3,
         fixed=[(56,3),(56,4),(56,5)],cat=ecat,tlist=TASKS)
add_exam(EC,"Final Exam", 40,110,6+3,fixed=[(110,4)],cat=ecat,tlist=TASKS)

# === 6. JPNL2018 Basic Japanese (HUM) ==============================
JP, jcat = "JPNL2018","HUM"
for w,d in enumerate(range(45,109,7),start=1):
    add(JP,f"Class Part W{w}",1,d,d,0.5,
        fixed=None, cat=jcat,tlist=TASKS)
for w,(rel,due) in enumerate(zip(range(45,108,7),range(52,116,7)),start=1):
    add(JP,f"Post-HW W{w}",1,rel,due,1,None,jcat,TASKS)
for w,d in enumerate(range(45,109,7),start=1):
    add(JP,f"Reading W{w}",1,d,d,0.5,None,jcat,TASKS)
for w,d in enumerate(range(45,109,7),start=1):
    add_exam(JP,f"In-class Quiz W{w}",1,d,0.5+1,
             fixed=[(d,5)],cat=jcat,tlist=TASKS)
add_exam(JP,"Midterm Exam",30,50,4+3,
         fixed=[(50,5),(50,6)],cat=jcat,tlist=TASKS)
add_exam(JP,"Final Exam",30,113,4+3,
         fixed=[(113,2),(113,3),(113,4)],cat=jcat,tlist=TASKS)

# === 7. IM3004 Organizational Behaviour (SOC) =====================
OB, obcat = "IM3004","SOC"
add(OB,"Case Study Presentation",25,1,92,8+1,None,obcat,TASKS)
add_exam(OB,"Midterm Exam",30,50,6+1,fixed=[(50,7)],cat=obcat,tlist=TASKS)
add_exam(OB,"Final Exam", 30,106,6+1,fixed=[(106,7)],cat=obcat,tlist=TASKS)
for w,d in enumerate(range(42,113,5),start=1):
    sh = 6 if d == 57 else 7
    add(OB,f"Participation W{w}",1,d,d,0.5,
        fixed=None,cat=obcat,tlist=TASKS)

# === 8. MGT1002 Accounting Principles (2) (SOC) ===================
AC, acat = "MGT1002","SOC"
add(AC,"Quiz",   4,15,22,1+1,fixed=[(22,10)],cat=acat,tlist=TASKS)
add(AC,"Project",6,99,103,5+1,fixed=[(103,10)],cat=acat,tlist=TASKS)
add_exam(AC,"Exam 1",27,31,6+1,fixed=[(31,10)],cat=acat,tlist=TASKS)
add_exam(AC,"Exam 2",27,66,6+1,fixed=[(66,10)],cat=acat,tlist=TASKS)
add_exam(AC,"Exam 3",26,109,6+1,fixed=[(109,10)],cat=acat,tlist=TASKS)
for w,d in enumerate(range(45,109,7),start=1):
    sh = 11 if d == 66 else 10
    add(AC,f"TA Session W{w}",1,d,d,0.5,
        fixed=None,cat=acat,tlist=TASKS)

# ------------------------------------------------------------------ #
# >>>  inject weekly lecture tasks  <<<                              #
# ------------------------------------------------------------------ #
add_weekly_lectures(TASKS)

# ------------------------------------------------------------------ #
# JSON assembly + duplicate-slot check                               #
# ------------------------------------------------------------------ #
J,S,E,r,d,slot,category = defaultdict(list),defaultdict(dict),defaultdict(dict),\
                          defaultdict(dict),defaultdict(dict),defaultdict(dict),{}
used = set()

def register(course, task, pairs):
    for day, sh in pairs:
        if (day, sh) in used:
            raise ValueError(f"Duplicate seat-time {(day,sh)} while adding {course}:{task}")
        used.add((day, sh))
    slot[course][task] = [list(p) for p in pairs]

for course, name, w_pct, rel, due, eff, fixed, cat in TASKS:
    J[course].append(name)
    S[course][name] = round(w_pct / 100, 8)
    E[course][name] = eff * EFFORT_FACTOR[course]
    r[course][name] = [rel, 1]
    if fixed:
        register(course, name, fixed)
        d[course][name] = [due, max(s for _, s in fixed)]
    else:
        d[course][name] = [due, LAST_SHIFT]
    category[course] = cat

# Re-normalise weights per course
for course, comp in S.items():
    tot = sum(comp.values())
    if not 0.999 < tot < 1.001:
        for t in comp:
            comp[t] = round(comp[t] / tot, 8)

catalog = dict(I=list(J.keys()), J=J, S=S, E=E, r=r, d=d,
               slot=slot, category=category)
with open("courses.json", "w", encoding="utf-8") as f:
    json.dump(catalog, f, indent=2, ensure_ascii=False)

print("courses.json written with", len(catalog["I"]), "courses and", len(TASKS), "tasks")
