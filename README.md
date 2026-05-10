# Semantic Boxels for Task and Motion Planning

A PyBullet-based system for generating **semantic boxels** -- task-relevant 3D regions used for belief representation in Task and Motion Planning (TAMP) under partial observability. A Franka Panda robot searches for hidden objects by relocating occluders, sensing shadow regions, and retrieving targets, all planned via PDDLStream.

## Quick Start

```bash
pip install pybullet numpy matplotlib
python3 -u test_full_pipeline.py
```

| Flag | Description |
|------|-------------|
| `--no-gui` | Headless mode (no PyBullet window) |
| `--no-boxel-viz` / `--show-free` | Skip boxel overlay / include free-space cells in overlay |
| `--log-level smart\|normal\|quiet\|verbose` | Console verbosity (default: `smart`) |
| `--scene default\|mixed\|scalability\|stack` | Scene preset |
| `--goal holding\|stack\|find-and-tray-stack` | Goal mode |
| `--n-occluders N` / `--n-targets N` / `--n-hidden N` | Scalability scene size (counts) |
| `--n-objects N` / `--stack-height N` | Stack scene size / tower height |
| `--seed N` | RNG seed (scalability/mixed/stack scenes) |
| `--baseline semantic\|uniform` | Free-space discretization (semantic = octree+merge, uniform = static grid) |
| `--uniform-cell-size F` | Uniform cell edge length in metres (default 0.05; floored at largest-object AABB + 1 cm so `place` can fit) |
| `--unit-costs` | Override domain action costs (stack=2, others=1) with all-cost-1 |

## Running on this machine (WSL + PowerShell)

This project runs in a WSL Python venv (`wsl_env/`) with a vendored PDDLStream
checkout next to it on disk. Three PowerShell wrapper functions live in
`$PROFILE` (`Microsoft.PowerShell_profile.ps1`) and are how everything is
launched from PowerShell:

| Alias | Translates to (inside WSL) | Script |
|-------|----------------------------|--------|
| `run_boxels` | `cd /mnt/c/.../Semantic_Boxels && source wsl_env/bin/activate && DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 PYTHONPATH=/mnt/c/.../pddlstream_lib python3 test_full_pipeline.py $args` | `test_full_pipeline.py` (single end-to-end run, optional GUI) |
| `run_eval` | `cd /mnt/c/.../Semantic_Boxels && source wsl_env/bin/activate && PYTHONPATH=/mnt/c/.../pddlstream_lib python3 eval_runner.py $args` | `eval_runner.py` (sweep over scene matrix, writes `eval_results/sweep_<ts>_<matrix>/`) |
| `plot_eval` | `cd /mnt/c/.../Semantic_Boxels && source wsl_env/bin/activate && python3 eval_plotter.py $args` | `eval_plotter.py` (consumes `aggregated.csv`, writes 3 PNGs next to it) |

(There is also a `cursor-agent` shim in `$PROFILE` that just forwards to the
WSL `cursor-agent` CLI — it is editor tooling, not part of the boxels
pipeline.)

### One-time WSL venv bootstrap

`wsl_env/` is gitignored. If it doesn't exist or is missing packages, create it
once:

```powershell
wsl bash -lc "cd /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels && python3 -m venv wsl_env && source wsl_env/bin/activate && pip install pybullet numpy matplotlib"
```

`matplotlib` is required by `eval_plotter.py`; without it the plotter falls
back to printing text tables instead of writing PNGs (look for the
`(matplotlib not available)` marker in stdout).

### Run a single scene

```powershell
run_boxels --goal find-and-tray-stack
run_boxels --no-gui --scene scalability --n-occluders 1 --n-targets 1 --n-hidden 1 --seed 0 --log-level quiet
```

### Run the evaluation sweep

```powershell
run_eval --matrix smoke              # 1 cell, ~3s — sanity check the runner
run_eval --matrix scalability --skip-existing   # 90 cells (n_occ 1..6 × n_tgt 1..3 × 5 seeds)
```

Output lands in `eval_results/sweep_<timestamp>_<matrix>/` with one
subdirectory per cell plus `aggregated.csv` and `aggregated.jsonl`.

### Generate the plots

PowerShell mangles backslashes when the path contains escape-like substrings
(`\U`, `\H`, …), so pass the WSL form of the path. Pick the latest sweep
directory and feed its `aggregated.csv` to `plot_eval`:

```powershell
$name = (Get-ChildItem eval_results\sweep_*_scalability | Select-Object -Last 1).Name
plot_eval "/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/eval_results/$name/aggregated.csv"
ii (Get-ChildItem eval_results\sweep_*_scalability | Select-Object -Last 1).FullName
```

The plotter writes three PNGs into the same directory as the CSV:
- `planning_time_vs_n_occluders.png`
- `success_rate_vs_n_occluders.png`
- `plan_count_vs_n_occluders.png`

`ii` (Invoke-Item) on the sweep directory opens it in Explorer so you can
double-click the PNGs.

### Common pitfalls

- **`[plotter] not found: C:Users...` (no backslashes).** PowerShell stripped
  them inside a double-quoted `"$(...)"`. Use the `/mnt/c/...` WSL path or
  build the string with `Join-Path` and pass it as a single argument.
- **`(matplotlib not available)` in plotter output.** `wsl_env/` is missing
  matplotlib — re-run the bootstrap install line above (just the
  `pip install matplotlib` part is enough).
- **`bash: ...conda.sh: No such file or directory`.** The shims activate the
  `wsl_env` venv, not anaconda — install into the venv, not into base.

## Documentation

**[Project wiki (home)](https://git.rwth-aachen.de/hani.alassiri.alhabboub/pybullet/-/wikis/home)** — or open the **Wiki** tab in the repository.

Detailed documentation lives there, including:

| Page | What it covers |
|------|---------------|
| Architecture Overview | Module dependencies, data flow diagrams, file structure |
| Scene Environment | PyBullet setup, camera model, scene presets, object detection |
| Spatial Reasoning | Shadow calculation, free-space octree, cell merging |
| Planning System | PDDLStream integration, problem construction, replanning |
| Robot Control and Streams | IK, RRT-Connect motion planning, grasp sampling |
| Execution Pipeline | End-to-end walkthrough, action handlers, concrete scenario |
| Core Data Structures | All types, dataclasses, and enums |
| PDDL Domain Reference | Predicates, actions, streams, PDDL/Python alignment |
| Design Decisions | Rationale for key choices and proposal deviations |
| Known Issues and Roadmap | Audit status, open issues, future work |

## License

MIT
