import json
import argparse
import gurobipy as gp
from gurobipy import GRB

def load_instance(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def to_pair(x, default_shift):
    return (x, default_shift) if isinstance(x, int) else tuple(x)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", help="Path to JSON instance file")
    parser.add_argument("--time_limit", type=int, default=300,
                        help="Time limit in seconds (default 300)")
    args = parser.parse_args()

    data = load_instance(args.instance)

    # --- unpack sets ---------------------------------------------------------
    K = list(map(int, data["K"]))                # days
    T = list(map(int, data["T"]))                # shifts
    SHIFTS = max(T)   
    I = data["I"]                                # courses
    J = {i: data["J"][i] for i in I}             # tasks per course

    # --- parameters ----------------------------------------------------------
    S = data["S"]
    E = data["E"]
    w = data["w"]
    B = data["B"]
    H_star = {int(k): v for k, v in data["H*"].items()}
    beta = data["beta"]

    # release / due dates as (day,shift) tuples
    r = {i: {j: to_pair(data["r"][i][j], 1)   for j in J[i]} for i in I}
    d = {i: {j: to_pair(data["d"][i][j], SHIFTS) for j in J[i]} for i in I}

    # productivity coefficients (sparse)
    P = {}
    for i in I:
        P[i] = {}
        for j in J[i]:
            raw = data["P"][i][j]
            P[i][j] = {tuple(map(int, k.strip("()").split(","))): v
                       for k, v in raw.items()}

    m = gp.Model("StudentScheduler")
    m.Params.TimeLimit = args.time_limit
    m.Params.OutputFlag = 1

    y = {}   # binary: work shift on task
    for k in K:
        for t in T:
            for i in I:
                for j in J[i]:
                    # availability check: zero if outside [r, d]
                    if (k, t) < r[i][j] or (k, t) > d[i][j]:
                        continue
                    y[k, t, i, j] = m.addVar(vtype=GRB.BINARY,
                                             name=f"y_{k}_{t}_{i}_{j}")

    # effective effort
    a = m.addVars(((i, j) for i in I for j in J[i]),
                  vtype=GRB.CONTINUOUS, lb=0, name="a")

    # grade fraction
    x = m.addVars(((i, j) for i in I for j in J[i]),
                  vtype=GRB.CONTINUOUS, lb=0, ub=1, name="x")

    # overtime per day
    z = m.addVars(K, vtype=GRB.CONTINUOUS, lb=0, name="z")

    m.update()

    # --- constraints ---------------------------------------------------------

    # 1. link effort to y
    for i in I:
        for j in J[i]:
            expr = gp.quicksum(P[i][j].get((k, t), 0.0) * y.get((k, t, i, j), 0)
                               for k in K for t in T)
            m.addConstr(a[i, j] == expr, name=f"effort_{i}_{j}")

    # 2. linearised min: E_ij * x_ij <= a_ij
    for i in I:
        for j in J[i]:
            m.addConstr(E[i][j] * x[i, j] <= a[i, j],
                        name=f"grade_link_{i}_{j}")

    # 3. one task per shift
    for k in K:
        for t in T:
            m.addConstr(
                gp.quicksum(y.get((k, t, i, j), 0)
                            for i in I for j in J[i]) <= 1,
                name=f"one_task_{k}_{t}"
            )

    # 4. break rule: max 4 in any 6-shift window
    for k in K:
        for t0 in range(1, max(T) - 5 + 1):
            m.addConstr(
                gp.quicksum(
                    y.get((k, t, i, j), 0)
                    for t in range(t0, t0 + 6)
                    for i in I for j in J[i]
                ) <= 4,
                name=f"break_{k}_{t0}"
            )

    # 5. daily overtime definition
    for k in K:
        daily_hours = gp.quicksum(
            y.get((k, t, i, j), 0)
            for t in T for i in I for j in J[i]
        )
        m.addConstr(z[k] >= daily_hours - H_star[k],
                    name=f"overtime_{k}")

    # 6. minimum course grade
    G = {}
    for i in I:
        G[i] = m.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS,
                        name=f"G_{i}")
        m.addConstr(
            G[i] == gp.quicksum(S[i][j] * x[i, j] for j in J[i]),
            name=f"grade_sum_{i}"
        )
        m.addConstr(G[i] >= B[i], name=f"grade_min_{i}")

    # --- objective -----------------------------------------------------------
    m.setObjective(
        gp.quicksum(w[i] * G[i] for i in I) -
        beta * gp.quicksum(z[k] for k in K),
        GRB.MAXIMIZE
    )

    # --- solve ---------------------------------------------------------------
    m.optimize()

    if m.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT):
        print(f"Model finished with status {m.Status}")
        return

    print(f"\nOptimal utility value: {m.ObjVal:.4f}")

    # Compact display: show each shift that is scheduled
    schedule = [(k, t, i, j)
                for (k, t, i, j), var in y.items() if var.X > 0.5]
    schedule.sort()
    print("\n--- Schedule (day, shift, course, task) ---")
    for k, t, i, j in schedule:
        print(f"({k:2d}, {t:2d})  {i:<8}  {j}")

if __name__ == "__main__":
    main()