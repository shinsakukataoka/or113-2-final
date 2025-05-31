#!/usr/bin/env python3
import json
import argparse
import random
from pathlib import Path

def load_instance(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def to_pair(x, default):
    return (x, default) if isinstance(x, int) else tuple(x)

# Global productivity dictionary
P = {}

def main():
    parser = argparse.ArgumentParser(
        description='Randomized greedy baseline with incremental updates'
    )
    parser.add_argument('instance', help='Path to JSON instance file')
    args = parser.parse_args()

    if not Path(args.instance).exists():
        raise SystemExit(f"{args.instance} not found")
    data = load_instance(args.instance)

    # Unpack data
    K = list(map(int, data['K']))
    T = list(map(int, data['T']))
    I = data['I']
    J = {i: data['J'][i] for i in I}
    w    = data['w']
    B    = data['B']
    beta = data['beta']
    Hstar= {int(k): v for k, v in data['H*'].items()}

    r = {i: {j: to_pair(data['r'][i][j], 1)      for j in J[i]} for i in I}
    d = {i: {j: to_pair(data['d'][i][j], max(T)) for j in J[i]} for i in I}

    S = {i: {j: data['S'][i][j] for j in J[i]} for i in I}
    E = {i: {j: data['E'][i][j] for j in J[i]} for i in I}

    # Build global P
    global P
    P = {
        i: {
            j: {
                tuple(map(int, k.strip('()').split(','))): v
                for k, v in data['P'][i][j].items()
            }
            for j in J[i]
        }
        for i in I
    }

    # Enumerate all feasible assignments
    all_keys = [
        (k, t, i, j)
        for i in I
        for j in J[i]
        for (k, t) in P[i][j]
        if r[i][j] <= (k, t) <= d[i][j]
    ]

    # Randomized order
    random.shuffle(all_keys)

    # Initialize incremental structures
    selected = {key: 0 for key in all_keys}
    used_shifts = set()
    shifts_by_day = {k: [] for k in K}
    a_loc = {(i, j): 0.0 for i in I for j in J[i]}
    shifts_count = {k: 0 for k in K}

    # Compute initial objective components
    def current_objective():
        # GPA
        gpa = 0.0
        for i in I:
            G_i = sum(S[i][j] * min(a_loc[i, j] / E[i][j], 1.0) for j in J[i])
            gpa += w[i] * G_i
        # Overtime
        overtime = sum(max(0, shifts_count[k] - Hstar[k]) for k in K)
        return gpa - beta * overtime

    best_obj = -1e99

    # Greedy rounding with incremental updates
    for key in all_keys:
        k, t, i, j = key
        # Tentatively select
        selected[key] = 1

        # Hard constraint 1: no overlap
        if (k, t) in used_shifts:
            selected[key] = 0
            continue

        # Hard constraint 2: break rule for this day
        day_shifts = shifts_by_day[k] + [t]
        day_shifts.sort()
        bad = any(
            sum(1 for s in day_shifts if start <= s < start + 6) > 4
            for start in range(max(1, t - 5), t + 1)
        )
        if bad:
            selected[key] = 0
            continue

        # Accept shift: update structures
        used_shifts.add((k, t))
        shifts_by_day[k].append(t)
        shifts_count[k] += 1
        a_loc[i, j] += P[i][j][(k, t)]

        # Compute objective
        obj = current_objective()

        # Stop if objective worsened and grades met
        if best_obj > -1e90 and obj < best_obj:
            # check grades
            grades_ok = all(
                sum(S[ii][jj] * min(a_loc[ii, jj] / E[ii][jj], 1.0) for jj in J[ii]) + 1e-9 >= B[ii]
                for ii in I
            )
            if grades_ok:
                # undo last
                selected[key] = 0
                used_shifts.remove((k, t))
                shifts_by_day[k].remove(t)
                shifts_count[k] -= 1
                a_loc[i, j] -= P[i][j][(k, t)]
                break

        best_obj = obj

    # Output
    print(f"\nFinal objective (randomized greedy) = {best_obj:.4f}")
    # print("Selected assignments:")
    # for (k, t, i, j), v in sorted(selected.items()):
    #     if v:
    #         print(f"  y[{k},{t},{i},{j}] = 1")

def run_simple_objective(json_path):
    import sys
    sys.argv = ["other_silly.py", json_path]
    from io import StringIO
    import contextlib

    f = StringIO()
    with contextlib.redirect_stdout(f):
        main()
    output = f.getvalue()

    for line in output.splitlines():
        if "objective" in line.lower():
            try:
                return float(line.strip().split()[-1])
            except:
                raise RuntimeError(f"Failed to parse silly objective from: {line}")
    raise RuntimeError("Could not find objective line in silly heuristic output")


if __name__ == '__main__':
    main()
