from pathlib import Path
import random
import re
import subprocess
import os
import csv
import time

# ============================================================
# CONFIG
# ============================================================

BASE = Path(r"D:\Personal\Code\Tools\rocsat\bench")
BASE = next(BASE.rglob("bmc-ibm-12.cnf"))
OUT_DIR = Path(r"D:\Personal\Code\Tools\minisat\benchmarks\experiment_bmc12")
SOLVER = Path(r"D:\Personal\Code\Tools\minisat\minisat_runner.exe")

N_SWAPS = 100
TIMEOUT = 30

SEED = 1337

SOLVER_ENV = os.environ.copy()
SOLVER_ENV["PATH"] = (
    r"D:\Personal\Code\Tools\Msys\ucrt64\bin"
    + os.pathsep
    + SOLVER_ENV["PATH"]
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# READ CNF
# ============================================================

text = BASE.read_text(encoding="utf-8")

# Read declared variable count.
header = re.search(r"^p cnf\s+(\d+)\s+(\d+)", text, re.MULTILINE)

if not header:
    raise RuntimeError("Could not find DIMACS header.")

NUM_VARS = int(header.group(1))

print("=" * 80)
print("SINGLE-VARIABLE TRANSPOSITION EXPERIMENT")
print("=" * 80)
print(f"Base formula : {BASE}")
print(f"Variables    : {NUM_VARS}")
print(f"Swaps        : {N_SWAPS}")
print()

# ============================================================
# VARIABLE SWAP
# ============================================================

def swap_variables(text, a, b):
    """
    Swap DIMACS variable identities a and b.

    Positive literal:
        a -> b
        b -> a

    Negative literal:
        -a -> -b
        -b -> -a

    Everything else remains unchanged.
    """

    def replace_literal(match):
        token = match.group(0)

        if token == "0":
            return token

        sign = ""
        number = token

        if token.startswith("-"):
            sign = "-"
            number = token[1:]

        value = int(number)

        if value == a:
            value = b
        elif value == b:
            value = a

        return sign + str(value)

    # Replace integer tokens only.
    return re.sub(r"-?\d+", replace_literal, text)


# ============================================================
# GENERATE SWAPS
# ============================================================

random.seed(SEED)

pairs = set()

while len(pairs) < N_SWAPS:
    a = random.randint(1, NUM_VARS)
    b = random.randint(1, NUM_VARS)

    if a == b:
        continue

    pair = tuple(sorted((a, b)))
    pairs.add(pair)

pairs = sorted(pairs)

print("Generating permutations...")

original_path = OUT_DIR / "baseline.cnf"
original_path.write_text(text, encoding="utf-8")

swap_files = []

for index, (a, b) in enumerate(pairs, 1):

    swapped = swap_variables(text, a, b)

    output = OUT_DIR / f"swap_{a}_{b}.cnf"
    output.write_text(swapped, encoding="utf-8")

    swap_files.append((index, a, b, output))

print(f"Generated {len(swap_files)} swapped instances.")
print()

# ============================================================
# RUN SOLVER
# ============================================================

def run_solver(path):

    start = time.perf_counter()

    try:
        result = subprocess.run(
            [str(SOLVER), str(path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=SOLVER_ENV
        )

        wall = time.perf_counter() - start

    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "wall_seconds": TIMEOUT,
            "solver_seconds": TIMEOUT,
            "decisions": None,
            "conflicts": None,
            "propagations": None,
        }

    output = result.stdout.strip()

    parts = output.split(",")

    if len(parts) < 6:
        return {
            "status": "ERROR",
            "wall_seconds": wall,
            "solver_seconds": None,
            "decisions": None,
            "conflicts": None,
            "propagations": None,
        }

    return {
        "status": parts[1],
        "wall_seconds": wall,
        "solver_seconds": float(parts[5]) / 1000.0,
        "decisions": int(parts[2]),
        "conflicts": int(parts[3]),
        "propagations": int(parts[4]),
    }


# ============================================================
# BASELINE
# ============================================================

print("Running baseline...")

baseline = run_solver(original_path)

print(
    f"BASELINE | "
    f"{baseline['solver_seconds']:.3f}s | "
    f"D={baseline['decisions']} | "
    f"C={baseline['conflicts']} | "
    f"P={baseline['propagations']}"
)

# ============================================================
# SWAPS
# ============================================================

results = []

for index, a, b, path in swap_files:

    result = run_solver(path)

    record = {
        "index": index,
        "a": a,
        "b": b,
        "file": str(path),
        **result
    }

    results.append(record)

    print(
        f"[{index:3d}/{N_SWAPS}] "
        f"swap({a},{b}) | "
        f"{result['solver_seconds'] if result['solver_seconds'] is not None else 'TIMEOUT'}s | "
        f"D={result['decisions']} | "
        f"C={result['conflicts']} | "
        f"P={result['propagations']}"
    )

# ============================================================
# SAVE
# ============================================================

csv_path = OUT_DIR / "results.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "index",
            "a",
            "b",
            "file",
            "status",
            "wall_seconds",
            "solver_seconds",
            "decisions",
            "conflicts",
            "propagations",
        ]
    )

    writer.writeheader()
    writer.writerows(results)

# ============================================================
# RANK
# ============================================================

valid = [
    r for r in results
    if r["status"] in ("SAT", "UNSAT")
    and r["decisions"] is not None
]

valid.sort(
    key=lambda r: r["decisions"],
    reverse=True
)

print()
print("=" * 80)
print("TOP 20 BY DECISIONS")
print("=" * 80)

for i, r in enumerate(valid[:20], 1):

    print(
        f"{i:2d}. "
        f"swap({r['a']:3d},{r['b']:3d}) | "
        f"D={r['decisions']:9d} | "
        f"C={r['conflicts']:8d} | "
        f"P={r['propagations']:10d} | "
        f"{r['solver_seconds']:.3f}s"
    )

print()
print(f"Results saved to:")
print(csv_path)