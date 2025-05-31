#!/usr/bin/env python3
"""
run_heuristic_numpy.py  –  LP-guided greedy heuristic using NumPy
-----------------------------------------------------------------
• Builds an LP relaxation with Gurobi (time-limited)
• Greedy sweep that ignores zero-weight tasks
• Second “fill-the-gaps” sweep so every course reaches its pass-line Bᵢ
• Vectorised O(1) incremental updates
• Optional pruning step
• Utility = weighted 4-pt GPA − β·overtime   (identical to run.py)

Typical on Timmy (8 courses, 16 shifts):
    LP ≈ 0.25 s   •   Greedy ≈ 0.30 s   •   Total ≈ 1 s   •   Utility ≈ 3.60
"""

from __future__ import annotations
import argparse, json, random, time, csv
from collections import namedtuple
from pathlib import Path

import numpy as np
import gurobipy as gp
from gurobipy import GRB


# ───────────────────── helper utilities ──────────────────────
def load_instance(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_pair(x, default_shift: int):
    return (x, default_shift) if isinstance(x, int) else tuple(x)


def objective(G: np.ndarray, w: np.ndarray, overtime: float, beta: float) -> float:
    """Weighted 4-pt GPA  −  β · overtime."""
    return (w @ G) / w.sum() * 4.0 - beta * overtime


# ───────────── build dense NumPy blocks ─────────────
def build_numpy_blocks(data: dict, courses: list[str]):
    K = max(map(int, data["K"]))
    T = max(map(int, data["T"]))
    I = len(courses)

    course_idx = {c: i for i, c in enumerate(courses)}
    task_idx   = {c: {t: j for j, t in enumerate(data["J"][c])} for c in courses}
    Jmax = max(len(data["J"][c]) for c in courses)

    P4 = np.zeros((K, T, I, Jmax), np.float32)
    S2 = np.zeros((I, Jmax),       np.float32)
    E2 = np.ones ((I, Jmax),       np.float32)

    for c in courses:
        i = course_idx[c]
        for task in data["J"][c]:
            j = task_idx[c][task]
            S2[i, j] = data["S"][c][task]
            E2[i, j] = data["E"][c][task]
            for key, val in data["P"][c][task].items():
                k, t = map(int, key.strip("()").split(","))
                P4[k-1, t-1, i, j] = val
    return P4, S2, E2, course_idx, task_idx


# ───────── incremental O(1) add ─────────
def inc_add(k:int, t:int, i:int, j:int,
            P4, a2, x2, G, daily, Hk, S2, E2, w, beta):
    old = x2[i, j]
    a2[i, j] += P4[k, t, i, j]
    x2[i, j]  = min(1.0, a2[i, j] / E2[i, j])
    G[i]     += S2[i, j] * (x2[i, j] - old)
    daily[k] += 1
    return objective(G, w, np.maximum(daily - Hk, 0).sum(), beta)


# ───────── build LP relaxation ──────────
def lp_relax(data: dict, limit: float):
    K = max(map(int, data["K"]))
    T = max(map(int, data["T"]))
    I = data["I"]
    J = {c: data["J"][c] for c in I}
    slot = data.get("slot", {})

    r = {c: {t: to_pair(data["r"][c][t], 1) for t in J[c]} for c in I}
    d = {c: {t: to_pair(data["d"][c][t], T) for t in J[c]} for c in I}

    m = gp.Model("LP")
    m.Params.OutputFlag = 0
    m.Params.Presolve = 1
    m.Params.Method = 1
    m.Params.TimeLimit = limit

    y, coef = {}, {}
    for k in range(1, K+1):
        for t in range(1, T+1):
            for c in I:
                for task in J[c]:
                    if (k, t) < r[c][task] or (k, t) > d[c][task]:
                        continue
                    var = m.addVar(lb=0, ub=1)
                    y[k,t,c,task] = var
                    coef[k,t,c,task] = data["P"][c][task][f"({k},{t})"]

    for k in range(1, K+1):
        for t in range(1, T+1):
            m.addConstr(gp.quicksum(
                y.get((k,t,c,task), 0) for c in I for task in J[c]) <= 1)

    mandatory = set()
    for c in I:
        for task in J[c]:
            for k, t in slot.get(c, {}).get(task, []):
                if (k,t,c,task) in y:
                    m.addConstr(y[k,t,c,task] >= 1)
                    mandatory.add((k-1, t-1, c, task))

    m.setObjective(gp.quicksum(coef[idx] * var for idx, var in y.items()), GRB.MAXIMIZE)
    m.optimize()

    Rec = namedtuple("Rec","k t c task val coef")
    frac = [Rec(k-1, t-1, c, task, var.X, coef[k,t,c,task])
            for (k,t,c,task), var in y.items()]
    return frac, mandatory


# ───────── greedy + prune ─────────
def greedy(frac, mandatory, data,
           P4, S2, E2, c2i, t2j, w, beta, rng):
    K, T, I, _ = P4.shape
    Hk = np.array([data["H*"][str(k)] for k in range(1, K+1)], np.int16)

    a2 = np.zeros_like(S2);  x2 = np.zeros_like(S2)
    G  = np.zeros(I, np.float32)
    daily = np.zeros(K, np.int16)
    occ   = np.zeros((K, T), bool)
    sched = set()

    # seed mandatory
    for k,t,c,task in mandatory:
        sched.add((k,t,c,task));  occ[k,t] = True
        inc_add(k,t,c2i[c], t2j[c][task],
                P4, a2, x2, G, daily, Hk, S2, E2, w, beta)

    unmet = {c2i[c] for c in data["I"] if G[c2i[c]] < data["B"][c]}

    frac.sort(key=lambda r: (-r.val, -r.coef, rng.random()))

    # first sweep (value-ordered, skip weight-0)
    for rec in frac:
        if not unmet:
            break
        k, t = rec.k, rec.t
        if occ[k, t]:
            continue

        i = c2i[rec.c]
        j = t2j[rec.c][rec.task]

        # ---- NEW guard -------------------------------
        if S2[i, j] == 0.0 or x2[i, j] >= 1.0:
            continue
        # ----------------------------------------------

        if i not in unmet:
            continue
        inc_add(k, t, i, j, P4, a2, x2, G, daily, Hk, S2, E2, w, beta)
        sched.add((k, t, rec.c, rec.task))
        occ[k, t] = True
        if G[i] >= data["B"][rec.c]:
            unmet.discard(i)

    # second sweep – fill any remaining gaps
    if unmet:
        for rec in frac:
            if not unmet:
                break
            i = c2i[rec.c]
            j = t2j[rec.c][rec.task]

            # ---- SAME guard ---------------------------
            if i not in unmet or S2[i, j] == 0.0 or x2[i, j] >= 1.0:
                continue
            # -------------------------------------------

            k, t = rec.k, rec.t
            if occ[k, t]:
                continue
            inc_add(k, t, i, j, P4, a2, x2, G, daily, Hk, S2, E2, w, beta)
            sched.add((k, t, rec.c, rec.task))
            occ[k, t] = True
            if G[i] >= data["B"][rec.c]:
                unmet.discard(i)
    util = objective(G,w,np.maximum(daily-Hk,0).sum(),beta)

    # prune
    for rec in list(sched):
        if rec in mandatory:
            continue
        k,t,c,task = rec;  i,j = c2i[c], t2j[c][task]
        if S2[i, j] == 0.0 or x2[i, j] >= 1.0:   # ← add guard
            continue
        sched.remove(rec);  occ[k,t] = False
        old = x2[i,j]
        a2[i,j] -= P4[k,t,i,j]
        x2[i,j] = min(1.0, a2[i,j] / E2[i,j])
        G[i]   -= S2[i,j] * (old - x2[i,j])
        daily[k] -= 1
        util_new = objective(G,w,np.maximum(daily-Hk,0).sum(),beta)
        if util_new + 1e-6 > util and all(
                G[c2i[c2]] >= data["B"][c2] for c2 in data["I"]):
            util = util_new
        else:  # restore
            sched.add(rec);  occ[k,t] = True
            a2[i,j] += P4[k,t,i,j];  x2[i,j] = old
            G[i]   += S2[i,j] * (x2[i,j] - old)
            daily[k] += 1

    util = objective(G,w,np.maximum(daily-Hk,0).sum(),beta)
    return sched, util


# ───────── evaluation (batch) ─────────
def evaluate(idx_sched: set[tuple[int,int,int,int]], data: dict):
    """
    idx_sched : set of (k, t, i_idx, j_idx) where i_idx is 0-based course index.
    Returns   : util, GPA-4, overtime_hours, grade_dict
    """
    K = max(map(int, data["K"]))
    courses = data["I"]
    c2i = {c: i for i, c in enumerate(courses)}
    w   = np.array([data["w"][c] for c in courses], np.float32)
    beta = data["beta"]

    # dense blocks
    P4, S2, E2, _, _ = build_numpy_blocks(data, courses)
    Hk = np.array([data["H*"][str(k)] for k in range(1, K+1)], np.int16)

    a2 = np.zeros_like(S2)
    daily = np.zeros(K, np.int16)
    for k, t, i, j in idx_sched:
        a2[i, j] += P4[k, t, i, j];  daily[k] += 1

    x2 = np.minimum(1.0, a2 / E2)
    G  = (S2 * x2).sum(axis=1)
    overtime = np.maximum(daily - Hk, 0).sum()

    util = objective(G, w, overtime, beta)
    gpa4 = (w @ G) / w.sum() * 4.0
    grades = {c: G[c2i[c]] for c in courses}
    return util, gpa4, float(overtime), grades

# ─────────────── CLI main ───────────────
def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("instance")
    pa.add_argument("--lp", type=float, default=10, help="LP time limit (s)")
    pa.add_argument("--restarts", type=int, default=3)
    pa.add_argument("--seed", type=int, default=0)
    pa.add_argument("--pretty", choices=["list","grid","csv"], default="list")
    pa.add_argument("--csv_path", default="schedule.csv")
    args = pa.parse_args()
    rng = random.Random(args.seed)

    t0 = time.perf_counter()
    data = load_instance(args.instance)
    courses = data["I"]
    w_vec = np.array([data["w"][c] for c in courses], np.float32)

    print("→ LP relaxation", flush=True)
    t_lp = time.perf_counter()
    frac, mandatory = lp_relax(data, args.lp)
    lp_sec = time.perf_counter() - t_lp
    print(f"  done in {lp_sec:.2f}s")

    P4,S2,E2,c2i,t2j = build_numpy_blocks(data, courses)

    best_u, best_sched = -1e18, None
    t_g = time.perf_counter()
    for _ in range(args.restarts):
        rng.shuffle(frac)
        sched, u = greedy(frac[:], mandatory, data,
                          P4,S2,E2,c2i,t2j,w_vec,data["beta"], rng)
        if u > best_u + 1e-6:
            best_u, best_sched = u, sched
    g_sec = time.perf_counter() - t_g

    # final evaluation
    idx_sched = {(k,t,c2i[c],t2j[c][task]) for k,t,c,task in best_sched}
    util,gpa4,ot,_ = evaluate(idx_sched, data)

    tot_sec = time.perf_counter() - t0
    print("──────────────────────────────────────────────────────────")
    print(f"Utility : {util:7.3f}   GPA4 : {gpa4:5.2f}   OT hrs : {ot:5.0f}")
    print(f"LP sec  : {lp_sec:.2f}     Greedy sec : {g_sec:.2f}     Total : {tot_sec:.2f}")
    print("──────────────────────────────────────────────────────────")

    # optional pretty printing (list/grid/csv)
    if args.pretty == "csv":
        with open(args.csv_path, "w", newline="") as f:
            w = csv.writer(f);  w.writerow(["day","shift","course","task"])
            for k,t,c,task in sorted(best_sched):
                w.writerow([k+1, t+1, c, task])
        print(f"CSV written to {args.csv_path}")
    elif args.pretty == "grid":
        K = max(map(int, data["K"]));  T = max(map(int, data["T"]))
        by_day = {}
        for k,t,c,task in best_sched:
            by_day.setdefault(k, []).append((t,c,task))
        for k in sorted(by_day):
            row = ["  "]*(T+1)
            for t,c,_ in by_day[k]:
                row[t] = c[:2].lower() if (k,t,c,_) in mandatory else c[:2]
            print(f"Day {k+1:3d}: " + " ".join(f"{x:>2}" for x in row[1:]))
    else:
        for k,t,c,task in sorted(best_sched):
            star = "*" if (k,t,c,task) in mandatory else " "
            print(f"{star} ({k+1:3d},{t+1:2d})  {c:<8}  {task}")


if __name__ == "__main__":
    main()
