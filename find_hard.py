from pathlib import Path
import subprocess
import os
import csv
import time

# =========================
# CONFIG
# =========================

CORPUS = Path(r"D:\Personal\Code\Tools\rocsat\bench")
SOLVER = Path(r"D:\Personal\Code\Tools\minisat\minisat_runner.exe")

TIMEOUT_SECONDS = 10.0

# We want formulas that are actually computationally interesting,
# but not so hard that every permutation will take forever.
MIN_TIME = 0.10
MAX_TIME = 5.0

OUTPUT_CSV = Path(r"D:\Personal\Code\Tools\minisat\candidate_formulas.csv")

# MSYS2 runtime DLLs
SOLVER_ENV = os.environ.copy()
SOLVER_ENV["PATH"] = (
    r"D:\Personal\Code\Tools\Msys\ucrt64\bin"
    + os.pathsep
    + SOLVER_ENV["PATH"]
)

# =========================
# FIND CNF FILES
# =========================

files = sorted(CORPUS.rglob("*.cnf"))

print("=" * 80)
print("SAT BENCHMARK SCANNER")
print("=" * 80)
print(f"Corpus: {CORPUS}")
print(f"CNF files found: {len(files)}")
print(f"Solver: {SOLVER}")
print()

if not files:
    print("NO CNF FILES FOUND.")
    raise SystemExit(1)

# =========================
# SCAN
# =========================

candidates = []
timeouts = 0
completed = 0

for i, path in enumerate(files, 1):

    try:
        start = time.perf_counter()

        result = subprocess.run(
            [str(SOLVER), str(path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=SOLVER_ENV
        )

        elapsed = time.perf_counter() - start
        completed += 1

        output = result.stdout.strip()

        # Expected:
        # RESULT,SAT,decisions,conflicts,propagations,runtime_ms
        parts = output.split(",")

        if len(parts) >= 6 and parts[0] == "RESULT":

            status = parts[1]
            decisions = int(parts[2])
            conflicts = int(parts[3])
            propagations = int(parts[4])
            solver_ms = float(parts[5])

            solver_seconds = solver_ms / 1000.0

            if MIN_TIME <= solver_seconds <= MAX_TIME:

                candidates.append({
                    "file": str(path),
                    "status": status,
                    "solver_seconds": solver_seconds,
                    "decisions": decisions,
                    "conflicts": conflicts,
                    "propagations": propagations
                })

                print(
                    f"[CANDIDATE] {solver_seconds:8.3f}s | "
                    f"D={decisions:8d} | "
                    f"C={conflicts:8d} | "
                    f"P={propagations:9d} | "
                    f"{path.name}"
                )

    except subprocess.TimeoutExpired:
        timeouts += 1

    except Exception as e:
        print(f"[ERROR] {path}: {e}")

    if i % 100 == 0:
        print(
            f"Progress: {i}/{len(files)} | "
            f"candidates={len(candidates)} | "
            f"timeouts={timeouts}"
        )

# =========================
# SAVE RESULTS
# =========================

candidates.sort(
    key=lambda x: x["solver_seconds"],
    reverse=True
)

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "file",
            "status",
            "solver_seconds",
            "decisions",
            "conflicts",
            "propagations"
        ]
    )

    writer.writeheader()
    writer.writerows(candidates)

# =========================
# SUMMARY
# =========================

print()
print("=" * 80)
print("TOP CANDIDATES")
print("=" * 80)

for i, c in enumerate(candidates[:30], 1):
    print(
        f"{i:2d}. "
        f"{c['solver_seconds']:7.3f}s | "
        f"D={c['decisions']:8d} | "
        f"C={c['conflicts']:8d} | "
        f"P={c['propagations']:9d} | "
        f"{c['file']}"
    )

print()
print(f"Completed:  {completed}")
print(f"Timeouts:   {timeouts}")
print(f"Candidates: {len(candidates)}")
print(f"Saved to:   {OUTPUT_CSV}")