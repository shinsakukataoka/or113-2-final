#!/usr/bin/env python3
"""
Merge course catalog + student profile, pick N random courses,
write instance_final.json ready for the solver.
"""

import json, random, argparse, itertools
from pathlib import Path

def load(fname):
    return json.load(open(fname))

def expand_P(template, tasks, days=115, shifts=16):
    """Turn {"*": coeff} into full sparse map for each course/task."""
    full = {}
    for c in template:
        coeff = template[c]["*"]
        full[c] = {}
        for t in tasks[c]:
            for k in range(1, days+1):
                for s in range(2, shifts):      # study hours 2-15
                    full[c].setdefault(t, {})[str((k,s))] = coeff
    return full

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n_courses", type=int, default=4)
    args = ap.parse_args()
    random.seed(args.seed)

    if not Path("courses.json").exists() or not Path("student_profile.json").exists():
        raise SystemExit("Run the two builders first")

    course_data  = load("courses.json")
    student_data = load("student_profile.json")

    all_courses = course_data["I"]
    choose = random.sample(all_courses, args.n_courses)
    print("Courses chosen:", ", ".join(choose))

    # slice every dict to chosen set
    J = {c: course_data["J"][c] for c in choose}
    extract = lambda d: {c: d[c] for c in choose}
    p_template_chosen = {c: student_data["P_template"][c] for c in choose}
    instance = {
        "K": list(range(1, 116)),
        "T": list(range(1, 17)),
        "I": choose,
        "J": J,
        "S": extract(course_data["S"]),
        "E": extract(course_data["E"]),
        "r": extract(course_data["r"]),
        "d": extract(course_data["d"]),
        "slot": {c: course_data["slot"].get(c, {}) for c in choose},  # safe lookup
        "w":  {c: student_data["w"][c] for c in choose},
        "B":  {c: student_data["B"][c] for c in choose},
        "beta": student_data["beta"],
        "H*": {str(k): student_data["H_star"] for k in range(1, 116)},
        "P": expand_P(p_template_chosen, J),           # <<< use filtered template
    }
    json.dump(instance, open("instance_final.json","w"), indent=2)
    print("✅  instance_final.json ready for solver")

if __name__ == "__main__":
    main()
