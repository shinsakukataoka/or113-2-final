from heuristic import run_heuristic_objective
from run import run_optimal_objective
from simple_heuristic import run_simple_objective
import glob, csv
from pathlib import Path
import time

INSTANCES = glob.glob("instances/Timmy/*.json")

with open("timmy_comparison.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "instance", "optimal", "heuristic", "gap_%", "silly",
        "time_opt", "time_heur", "time_silly"
    ])

    for inst in INSTANCES:
        inst_name = Path(inst).name

        try:
            # --- Time optimal ---
            t0 = time.time()
            opt = run_optimal_objective(inst)
            t1 = time.time()
            time_opt = t1 - t0

            # --- Time heuristic ---
            t0 = time.time()
            heu = run_heuristic_objective(inst)
            t1 = time.time()
            time_heur = t1 - t0

            # --- Time silly ---
            t0 = time.time()
            sil = run_simple_objective(inst)
            t1 = time.time()
            time_silly = t1 - t0

        except Exception as e:
            print(f"[ERROR] Failed on {inst_name}: {e}")
            continue

        gap = (opt - heu) / abs(opt) * 100 if opt != 0 else 0

        writer.writerow([
            inst_name, opt, heu, gap, sil,
            round(time_opt, 4), round(time_heur, 4), round(time_silly, 4)
        ])

        print(
            f"✓ {inst_name:30s}  "
            f"OPT={opt:.4f} ({time_opt:.2f}s)  "
            f"HEUR={heu:.4f} ({time_heur:.2f}s)  "
            f"GAP={gap:.2f}%  "
            f"SIL={sil:.4f} ({time_silly:.2f}s)"
        )

print("✅ Comparison with timing complete. Output saved to comparison.csv")
