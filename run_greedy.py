#!/usr/bin/env python3
from __future__ import annotations
import json, random, argparse, math, textwrap
from pathlib import Path
from collections import defaultdict

SHIFTS_PER_HOUR = 1  # same as run.py

def to_pair(x, default_shift: int):
    return (x, default_shift) if isinstance(x, int) else tuple(x)


def load(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def greedy(instance: dict, seed: int | None = None):
    rng = random.Random(seed)
    K_max = max(map(int, instance["K"]))
    T_max = max(map(int, instance["T"]))

    courses        = instance["I"]
    tasks_per_cour = instance["J"]
    S              = instance["S"]
    E              = instance["E"]
    r              = instance["r"]
    d              = instance["d"]
    P              = instance["P"]
    H_star         = {int(k): v for k, v in instance["H*"].items()}
    slot_info      = instance.get("slot", {})
    w              = instance["w"]
    beta           = instance["beta"]
    B              = instance["B"]

    occupied   = [[False]*(T_max+1) for _ in range(K_max+1)]
    daily_used = [0]*(K_max+1)

    a_ij  = {c: {t: 0.0 for t in tasks_per_cour[c]} for c in courses}
    x_ij  = {c: {t: 0.0 for t in tasks_per_cour[c]} for c in courses}

    schedule = set()

    # ── 1. schedule mandatory seats ───────────────────────
    for c, tasks in slot_info.items():
        for task, lst in tasks.items():
            for k, t in lst:
                if not occupied[k][t]:
                    occupied[k][t] = True
                    daily_used[k] += 1
                schedule.add((k, t, c, task))
                a_ij[c][task] += P[c][task].get(f"({k},{t})", 0.0)

    # initialise completion x
    for c in courses:
        for task in tasks_per_cour[c]:
            if E[c][task] > 0:
                x_ij[c][task] = min(1.0, a_ij[c][task] / E[c][task])
            else:
                x_ij[c][task] = 1.0

    # ── helper lambdas ────────────────────────────────────
    def course_grade(c):
        return sum(S[c][task]*x_ij[c][task] for task in tasks_per_cour[c])

    def remaining_slots_allowed(c, task):
        used = sum(1 for k, t, cc, tt in schedule if cc == c and tt == task)
        return max(0, math.ceil(E[c][task]/SHIFTS_PER_HOUR) - used)

    # ── 2. build sortable candidate list (all non-mandatory slots) ───────────
    candidates = []
    for k in range(1, K_max+1):
        for t in range(1, T_max+1):
            if occupied[k][t]:
                continue
            for c in courses:
                for task in tasks_per_cour[c]:
                    # window
                    r_pair = to_pair(r[c][task], 1)
                    d_pair = to_pair(d[c][task], T_max)
                    if not (r_pair <= (k, t) <= d_pair):
                        continue
                    if remaining_slots_allowed(c, task) == 0:
                        continue
                    pval = P[c][task].get(f"({k},{t})", 0.0)
                    sval = S[c][task]
                    # sort key: higher weight first, then productivity
                    candidates.append(((k, t, c, task), (-sval, -pval, rng.random())))

    candidates.sort(key=lambda x: x[1])  # ascending on negatives = descending

    # ── 3. first pass: greedy by value until all tasks complete 100 % or no slots ──
    for (k, t, c, task), _ in candidates:
        if occupied[k][t]:
            continue
        if x_ij[c][task] >= 1.0:
            continue
        if remaining_slots_allowed(c, task) == 0:
            continue

        # place it
        occupied[k][t] = True
        daily_used[k] += 1
        schedule.add((k, t, c, task))
        a_ij[c][task] += P[c][task].get(f"({k},{t})", 0.0)
        x_ij[c][task] = min(1.0, a_ij[c][task] / E[c][task])

    # ── 4. second pass: bring every course up to Bᵢ ──────────────────────────
    #   iterate until stable or impossible
    unmet_courses = {c for c in courses if course_grade(c) < B[c]}
    if unmet_courses:
        # re-sort candidates by pure productivity for unmet courses
        rem = [c for c in candidates
               if (c[0][2] in unmet_courses) and not occupied[c[0][0]][c[0][1]]]
        rem.sort(key=lambda x: (-x[0][0], -x[0][1], rng.random()))
        for (k, t, c, task), _ in rem:
            if not unmet_courses:
                break
            if occupied[k][t]:
                continue
            if remaining_slots_allowed(c, task) == 0:
                continue
            if x_ij[c][task] >= 1.0:
                continue
            # place
            occupied[k][t] = True
            daily_used[k] += 1
            schedule.add((k, t, c, task))
            a_ij[c][task] += P[c][task].get(f"({k},{t})", 0.0)
            x_ij[c][task] = min(1.0, a_ij[c][task] / E[c][task])
            if course_grade(c) >= B[c]:
                unmet_courses.discard(c)

    # infeasible if some courses still below Bᵢ
    if unmet_courses:
        return schedule, float("-inf"), 0.0, 0.0, {}

    # ── 5. compute metrics identically to run.py ─────────────────────────────
    grades = {c: course_grade(c) for c in courses}
    total_cred = sum(w.values())
    gpa4 = sum(w[c]*grades[c] for c in courses)/total_cred*4.0
    overtime = sum(max(daily_used[k]-H_star[k], 0) for k in range(1, K_max+1))
    utility  = gpa4 - beta * overtime

    return schedule, utility, gpa4, overtime, grades


# ───────────────────── CLI wrapper ──────────────────────
def main():
    pa = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description="Greedy scheduler aligned with run.py metrics."
    )
    pa.add_argument("instance_path", type=Path)
    pa.add_argument("--rng_seed", type=int, default=None)
    args = pa.parse_args()

    if not args.instance_path.exists():
        raise SystemExit(f"{args.instance_path} not found")

    inst = load(args.instance_path)
    sched, util, gpa, ot, grades = greedy(inst, args.rng_seed)

    name = args.instance_path.name
    if util == float("-inf"):
        print(f"{name}: infeasible – could not meet all B_i")
        return

    print(textwrap.dedent(f"""
        ── Greedy-fixed results ──
        Instance         : {name}
        Utility          : {util:7.3f}
        GPA (4-pt scale) : {gpa:7.3f}
        Overtime hours   : {ot:7.1f}
        Scheduled slots  : {len(sched)}
    """).strip())

    # optional pretty list
    for k, t, c, task in sorted(sched):
        print(f"  Day {k:<3} Shift {t:<2}  {c:<10} {task}")


if __name__ == "__main__":
    main()
