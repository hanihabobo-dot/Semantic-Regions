"""Audit #96 Care(3): scan every no_summary cell for evidence of the numpy
crash (or any other env-level interpreter failure)."""
import json
from pathlib import Path

cells_dir = Path("eval_results/sweep_anytime/cells")
total = 0
numpy_crashes = []
modulenotfound_other = []
other_short = []
real_runs = []

for cell_dir in sorted(cells_dir.iterdir()):
    if not cell_dir.is_dir():
        continue
    ts = cell_dir / "timing_summary.json"
    if not ts.exists():
        continue
    try:
        j = json.loads(ts.read_text())
    except Exception:
        continue
    if (j.get("exit_reason") or "").lower() != "no_summary":
        continue
    total += 1
    stdout_path = cell_dir / "stdout.log"
    if not stdout_path.exists():
        other_short.append((cell_dir.name, "no stdout.log"))
        continue
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    n_bytes = len(text)
    if "No module named 'numpy'" in text:
        numpy_crashes.append((cell_dir.name, n_bytes))
    elif "ModuleNotFoundError" in text:
        modulenotfound_other.append((cell_dir.name, n_bytes))
    elif n_bytes < 1000:
        # Short stdout could indicate early interpreter failure
        other_short.append((cell_dir.name, n_bytes))
    else:
        real_runs.append((cell_dir.name, n_bytes))

print(f"Total no_summary cells: {total}")
print(f"  numpy ModuleNotFoundError: {len(numpy_crashes)}")
for name, n in numpy_crashes:
    print(f"    {name} ({n} B)")
print(f"  other ModuleNotFoundError: {len(modulenotfound_other)}")
for name, n in modulenotfound_other:
    print(f"    {name} ({n} B)")
print(f"  short stdout (<1000 B, no MNFE): {len(other_short)}")
for name, n in other_short[:10]:
    print(f"    {name} ({n} B)")
print(f"  long-running cells that just didn't produce a summary: "
      f"{len(real_runs)}")
for name, n in real_runs[:5]:
    print(f"    {name} ({n} B) — sample")
