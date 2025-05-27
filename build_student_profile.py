"""
Create student_profile.json
Only 3*3 patterns
  python build_student_profile.py --style stem   --work normal
  python build_student_profile.py --style hum    --work lazy
  python build_student_profile.py --style soc    --work hard
"""

import json, argparse, random, itertools
from pathlib import Path

STYLE_CHOICES = {"stem": "STEM", "hum": "HUM", "soc": "SOC"}
WORK_LEVELS   = {
    "lazy":   dict(beta=1.0,  H=4),
    "normal": dict(beta=0.5,  H=8),
    "hard":   dict(beta=0.2, H=12),
}

# productivity multipliers
MULTIPLIER = dict(fav=1.2, norm=1.0, weak=0.8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=STYLE_CHOICES, default="stem")
    ap.add_argument("--work",  choices=WORK_LEVELS,   default="normal")
    args = ap.parse_args()

    style_cat = STYLE_CHOICES[args.style]      # favourite category
    work_par  = WORK_LEVELS[args.work]
    if not Path("courses.json").exists():
        raise SystemExit("courses.json not found – run build_course_catalog.py first")
    cat = json.load(open("courses.json"))["category"]

    DAYS, SHIFTS = 115, 16
    P = {}
    for course, category in cat.items():
        group = "fav" if category == style_cat else "weak" if (
                (style_cat == "STEM" and category == "HUM") or
                (style_cat == "HUM" and category == "STEM")
            ) else "norm"
        coeff = MULTIPLIER[group]
        P[course] = {"*": coeff}

    profile = dict(
        P_template=P,
        w={c: 1.0 for c in cat},      # equal course importance (fixed)
        B={c: 0.6 for c in cat},      # 60 % pass line (fixed)
        beta=work_par["beta"],
        H_star=work_par["H"],
    )
    json.dump(profile, open("student_profile.json", "w"), indent=2)
    print("Student_profile.json written")

if __name__ == "__main__":
    main()
