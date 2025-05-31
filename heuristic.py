#!/usr/bin/env python3
import json
import argparse
import csv
import gurobipy as gp
from gurobipy import GRB
from pathlib import Path
import math

SHIFTS_PER_HOUR = 1

def _to_csv(schedule, path="schedule.csv"):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "shift", "course", "task"])
        for k, t, i, j in schedule:
            w.writerow([k, t, i, j])
    print(f"CSV written to {path!s}")

def load_instance(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def to_pair(x, default):
    return (x, default) if isinstance(x, int) else tuple(x)

# We keep P global so our helpers can see it
P = {}

def check_hard_constraints(y_sel, K, T):
    """
    Hard rules:
      1) At most one assignment per (k,t)
      2) No more than 4 worked shifts in any sliding 6-shift window on the same day
    """
    used = set()
    for (k, t, i, j), v in y_sel.items():
        if v:
            if (k, t) in used:
                return False
            used.add((k, t))

    # Break-rule check
    for k in K:
        shifts = sorted(t for (kk, t, _, _), v in y_sel.items() if v and kk == k)
        for t in shifts:
            # any window [start, start+5] containing t
            for start in range(max(1, t - 5), t + 1):
                if sum(1 for s in shifts if start <= s < start + 6) > 4:
                    return False
    return True

def check_minimum_grades(y_sel, I, J, S, E, B):
    """
    Grade rule:
      G_i = sum_j S[i][j] * min(a_ij/E_ij, 1)
      require G_i >= B[i] for all i
    """
    # Compute a_ij = sum_{k,t} P[i][j][(k,t)] * y_sel
    a_loc = { (i, j): 0.0 for i in I for j in J[i] }
    for (k, t, i, j), v in y_sel.items():
        if v:
            a_loc[i, j] += P[i][j].get((k, t), 0.0)

    # Compute x_ij = min(a_ij/E_ij, 1)
    x_loc = { (i, j): min(a_loc[i, j] / E[i][j], 1.0)
              for i in I for j in J[i] }

    # Check G_i = sum_j S_ij * x_ij
    for i in I:
        G_i = sum(S[i][j] * x_loc[i, j] for j in J[i])
        if G_i + 1e-9 < B[i]:
            return False
    return True

def compute_objective(y_sel, I, J, S, E, w, beta, Hstar):
    """
    Objective = sum_i w[i] * G_i  -  beta * sum_k overtime_k,
    where overtime_k = max(0, #shifts_on_k - Hstar[k]).
    """
    # Recompute a_ij
    a_loc = { (i, j): 0.0 for i in I for j in J[i] }
    for (k, t, i, j), v in y_sel.items():
        if v:
            a_loc[i, j] += P[i][j].get((k, t), 0.0)

    # x_ij
    x_loc = { (i, j): min(a_loc[i, j] / E[i][j], 1.0)
              for i in I for j in J[i] }

    # GPA part
    gpa = (sum(w[i] * sum(S[i][j] * x_loc[i, j] for j in J[i]) for i in I) / sum(w.values())) * 4
    # gpa = sum(w[i] * sum(S[i][j] * x_loc[i, j] for j in J[i]) for i in I)

    # Overtime
    shifts_per_day = { k: 0 for k in Hstar }
    for (k, _, i, j), v in y_sel.items():
        if v:
            shifts_per_day[k] += 1
    overtime = sum(max(0, shifts_per_day[k] - Hstar[k]) for k in Hstar)

    return gpa - beta * overtime

def main():
    p = argparse.ArgumentParser(
        description="LP‐relax, sort fractional y's, then greedy rounding"
    )
    p.add_argument("instance", help="Path to JSON instance file")
    args = p.parse_args()

    if not Path(args.instance).exists():
        raise SystemExit(f"{args.instance} not found")
    data = load_instance(args.instance)

    # --- unpack data ---
    K = list(map(int, data["K"]))
    T = list(map(int, data["T"]))
    I = data["I"]
    J = {i: data["J"][i] for i in I}
    w = data["w"]
    B = data["B"]
    beta = data["beta"]
    H_star = {int(k): v for k, v in data["H*"].items()}
    slot   = data.get("slot", {})

    r = {i:{j: to_pair(data["r"][i][j], 1)      for j in J[i]} for i in I}
    d = {i:{j: to_pair(data["d"][i][j], max(T)) for j in J[i]} for i in I}

    S = {i:{j: data["S"][i][j] for j in J[i]} for i in I}
    E = {i:{j: data["E"][i][j] for j in J[i]} for i in I}

    # build P globally
    global P
    P = {
        i: {
            j: {
                tuple(map(int, k.strip("()").split(","))): v
                for k, v in data["P"][i][j].items()
            }
            for j in J[i]
        }
        for i in I
    }

        # ----------------- build model ------------------------------------------
    m = gp.Model("LP_Relax")
    m.Params.OutputFlag = 0
    m.Params.TimeLimit = 60

    # y_{k,t,i,j} ------------------------------------------------------------
    y = {}
    for k in K:
        for t in T:
            for i in I:
                for j in J[i]:
                    if (k, t) < r[i][j] or (k, t) > d[i][j]:
                        continue
                    y[k, t, i, j] = m.addVar(
                            lb=0, ub=1, vtype=GRB.CONTINUOUS,
                            name=f"y_{k}_{t}_{i}_{j}"
                        )

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

    # upper bound on slots per task
    for i in I:
        for j in J[i]:
            max_slots = math.ceil(E[i][j] / SHIFTS_PER_HOUR)
            m.addConstr(
                gp.quicksum(y.get((k, t, i, j), 0) for k in K for t in T)
                <= max_slots
            )

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
    m.setObjective(((gp.quicksum(w[i] * G[i] for i in I) / sum(w.values())) * 4)
                   - beta * gp.quicksum(z[k] for k in K),
                   GRB.MAXIMIZE)
    m.optimize()
    if m.status not in (GRB.OPTIMAL, GRB.TIME_LIMIT):
        print("LP relaxation failed")
        return

    # --- extract & sort all fractional y's ---
    y_vals = [
        (var.X, var.VarName)
        for var in m.getVars()
        if var.VarName.startswith("y_") and var.X > 1e-8
    ]
    parsed = []
    for val, name in y_vals:
        _, k, t, i, j = name.split("_", 4)
        parsed.append((val, int(k), int(t), i, j))
    parsed.sort(reverse=True, key=lambda x: x[0])

    # --- greedy rounding over all candidates ---
    binary_y = { (k,t,i,j): 0 for (_,k,t,i,j) in parsed }
    best_obj  = -1e99

    for (_val, k, t, i, j) in parsed:
        key = (k, t, i, j)
        # 1) tentatively include
        binary_y[key] = 1

        # 2) hard‐constraint check
        if not check_hard_constraints(binary_y, K, T):
            binary_y[key] = 0
            continue

        # 3) compute new objective
        obj = compute_objective(binary_y, I, J, S, E, w, beta, H_star)

        # 4) if we already have a solution and it got worse
        #    *and* minimum grades are now met, undo + stop
        if best_obj > -1e90 and obj < best_obj \
           and check_minimum_grades(binary_y, I, J, S, E, B):
            binary_y[key] = 0
            break

        # 5) otherwise accept
        best_obj = obj

    # --- final output ---
    print(f"\nFinal objective = {best_obj:.4f}")

    schedule = sorted(
        (k, t, i, j)
        for (k, t, i, j), val in binary_y.items()
        if val == 1
    )

    _to_csv(schedule, path="schedule.csv")

def run_heuristic_objective(json_path):
    import sys
    sys.argv = ["heuristic.py", json_path]
    from io import StringIO
    import contextlib

    f = StringIO()
    with contextlib.redirect_stdout(f):
        main()  # runs the existing logic
    output = f.getvalue()

    # extract final objective
    for line in output.splitlines():
        if "Final objective" in line:
            return float(line.strip().split()[-1])
    raise RuntimeError("Could not parse heuristic objective")

if __name__ == "__main__":
    main()
