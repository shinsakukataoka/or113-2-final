#!/usr/bin/env python3
# run.py  – solve one JSON instance and pretty-print the timetable
# ---------------------------------------------------------------------

import json, argparse, csv, textwrap
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict
from pathlib import Path

# ------------------------------------------------------------------ #
# Helpers                                                            #
# ------------------------------------------------------------------ #
def load_instance(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def to_pair(x, default_shift):
    """Return (day, shift) for either bare int or [d,s] list."""
    return (x, default_shift) if isinstance(x, int) else tuple(x)

# ── timetable rendering ──────────────────────────────────────────── #
def _grid(schedule, shifts, mand):
    """
    Compact ASCII timetable.
      • Each row  = one calendar day
      • Each cell = first 2 letters of the course
      • Mandatory seat-times (lectures/exams) are *lower-case*
    """
    by_day = defaultdict(list)
    for k, t, i, j in schedule:
        by_day[k].append((t, i, j))

    width = max(shifts)
    for k in sorted(by_day):
        cells = ["  "] * (width + 1)               # index 0 unused
        for t, i, j in by_day[k]:
            tag = i[:2]                            # course label
            if (k, t, i, j) in mand:
                tag = tag.lower()                  # mark lecture / exam
            cells[t] = tag
        print(f"Day {k:3d}: " + " ".join(f"{c:>2}" for c in cells[1:]))

def _to_csv(schedule, path="schedule.csv"):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "shift", "course", "task"])
        for k, t, i, j in schedule:
            w.writerow([k, t, i, j])
    print(f"CSV written to {path!s}")

# ------------------------------------------------------------------ #
# Main                                                               #
# ------------------------------------------------------------------ #
def main():
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""
        Solve a single scheduling instance.

        --pretty list   (default)  plain list of (day,shift,course,task)
        --pretty grid               ASCII calendar (mandatory seats in lower-case)
        --pretty csv                write schedule.csv
        """)
    )
    p.add_argument("instance", help="Path to JSON instance file")
    p.add_argument("--time_limit", type=int, default=300)
    p.add_argument("--pretty", choices=["grid", "csv", "list"],
                   default="list")
    p.add_argument("--csv_path", default="schedule.csv")
    args = p.parse_args()

    if not Path(args.instance).exists():
        raise SystemExit(f"{args.instance} not found")

    data = load_instance(args.instance)

    # ----------------- unpack sets ------------------------------------------
    K = list(map(int, data["K"]));           DAYS = max(K)
    T = list(map(int, data["T"]));           SHIFTS = max(T)
    I = data["I"];                           J = {i: data["J"][i] for i in I}

    # ----------------- parameters -------------------------------------------
    S = data["S"];   E = data["E"];   w = data["w"];   B = data["B"]
    H_star = {int(k): v for k, v in data["H*"].items()}
    beta   = data["beta"]
    slot   = data.get("slot", {})

    r = {i: {j: to_pair(data["r"][i][j], 1)        for j in J[i]} for i in I}
    d = {i: {j: to_pair(data["d"][i][j], SHIFTS)   for j in J[i]} for i in I}

    # sparse productivity ----------------------------------------------------
    P = {}
    for i in I:
        P[i] = {}
        for j in J[i]:
            P[i][j] = {tuple(map(int, k.strip("()").split(","))): v
                       for k, v in data["P"][i][j].items()}

    # ----------------- build model ------------------------------------------
    m = gp.Model("StudentScheduler")
    m.Params.TimeLimit  = args.time_limit
    m.Params.OutputFlag = 1

    # y_{k,t,i,j} ------------------------------------------------------------
    y = {}
    for k in K:
        for t in T:
            for i in I:
                for j in J[i]:
                    if (k, t) < r[i][j] or (k, t) > d[i][j]:
                        continue
                    y[k, t, i, j] = m.addVar(vtype=GRB.BINARY)

    # a, x, z ----------------------------------------------------------------
    a = m.addVars(((i, j) for i in I for j in J[i]), lb=0)
    x = m.addVars(((i, j) for i in I for j in J[i]), lb=0, ub=1)
    z = m.addVars(K, lb=0)

    # mandatory seat-times ---------------------------------------------------
    mandatory = set()
    for i in I:
        for j in J[i]:
            for day, sh in slot.get(i, {}).get(j, []):
                if (day, sh, i, j) in y:
                    m.addConstr(y[day, sh, i, j] == 1)
                    mandatory.add((day, sh, i, j))   # remember for grid

    # constraints ------------------------------------------------------------
    for i in I:
        for j in J[i]:
            m.addConstr(a[i, j] == gp.quicksum(
                P[i][j].get((k, t), 0) * y.get((k, t, i, j), 0)
                for k in K for t in T))
            m.addConstr(E[i][j] * x[i, j] <= a[i, j])

    # one task per shift
    for k in K:
        for t in T:
            m.addConstr(gp.quicksum(y.get((k, t, i, j), 0)
                                    for i in I for j in J[i]) <= 1)

    # break rule: ≤4 shifts worked in any 6-shift window
    for k in K:
        for t0 in range(1, SHIFTS - 5):
            m.addConstr(gp.quicksum(
                y.get((k, t, i, j), 0)
                for t in range(t0, t0 + 6)
                for i in I for j in J[i]) <= 4)

    # overtime
    for k in K:
        m.addConstr(z[k] >= gp.quicksum(
            y.get((k, t, i, j), 0)
            for t in T for i in I for j in J[i]) - H_star[k])

    # course grades & minima
    G = {}
    for i in I:
        G[i] = m.addVar(lb=0, ub=1)
        m.addConstr(G[i] == gp.quicksum(S[i][j] * x[i, j] for j in J[i]))
        m.addConstr(G[i] >= B[i])

    # objective --------------------------------------------------------------
    m.setObjective(gp.quicksum(w[i] * G[i] for i in I)
                   - beta * gp.quicksum(z[k] for k in K),
                   GRB.MAXIMIZE)

    # ----------------- solve -------------------------------------------------
    m.optimize()
    if m.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT):
        print(f"Model finished with status {m.Status}")
        return

    # ----------------- results ----------------------------------------------
    # schedule list
    schedule = sorted((k, t, i, j)
                      for (k, t, i, j), var in y.items() if var.X > 0.5)

    # utility breakdown
    gpa_part   = sum(w[i] * G[i].X for i in I)
    ot_hours   = sum(z[k].X for k in K)
    penalty    = beta * ot_hours

    # summary banner
    print(textwrap.dedent(f"""
        ══════════════════════════════════════════════════════════
        Instance       : {Path(args.instance).name}
        Courses chosen : {', '.join(I)}
        β (overtime wt): {beta:.3f}
        Daily H* (base): {min(H_star.values())} … {max(H_star.values())} hours
        ----------------------------------------------------------
        Weighted GPA   : {gpa_part:7.4f}
        Overtime hours : {ot_hours:7.2f}
        Penalty β·∑z   : {penalty:7.4f}
        ----------------------------------------------------------
        Total utility  : {m.ObjVal:7.4f}
        ══════════════════════════════════════════════════════════
    """).strip())

    # pretty print ------------------------------------------------------------
    if args.pretty == "grid":
        _grid(schedule, T, mandatory)
    elif args.pretty == "csv":
        _to_csv(schedule, args.csv_path)
    else:   # classic list
        for k, t, i, j in schedule:
            flag = "*" if (k, t, i, j) in mandatory else " "
            print(f"{flag} ({k:3d}, {t:2d})  {i:<8}  {j}")

# ------------------------------------------------------------------ #
if __name__ == "__main__":
    main()
