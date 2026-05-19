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
| `--scene default\|mixed\|scalability\|stack\|random-pairs` | Scene preset |
| `--goal holding\|stack\|find-and-tray-stack` | Goal mode |
| `--n-occluders N` / `--n-targets N` / `--n-hidden N` | Scalability/random-pairs scene size (counts) |
| `--n-extra-distractors N` | Visible distractor targets added on top of the hidden targets (`random-pairs` scene) |
| `--n-objects N` / `--stack-height N` | Stack scene size / tower height |
| `--seed N` | RNG seed (scalability/mixed/stack/random-pairs scenes) |
| `--seed-retry` | Let the placement-retry layer re-roll an explicit `--seed` on infeasible geometry (default: strict pinning) |
| `--baseline semantic\|uniform` | Free-space discretization (semantic = octree+merge, uniform = static grid) |
| `--uniform-cell-size F` | Uniform cell edge length in metres (default 0.05; floored at largest-object AABB + 1 cm so `place` can fit) |
| `--min-boxel-size F` | Minimum free-space octree leaf size for the semantic baseline (default: audit-#67 auto-cell floor; explicit value enables the anytime resolution sweep) |
| `--max-plan-time F` | Per-call PDDLStream budget in seconds (default 1800) |
| `--unit-costs` | Override domain action costs (stack=2, others=1) with all-cost-1 |

## Documentation

**[Project wiki (home)](https://git.rwth-aachen.de/hani.alassiri.alhabboub/pybullet/-/wikis/home)** — or open the **Wiki** tab in the repository.

Detailed documentation lives there, including:

| Page | What it covers |
|------|---------------|
| Architecture Overview | Module dependencies, data flow diagrams, file structure |
| Scene Environment | PyBullet setup, camera model, scene presets, object detection |
| Spatial Reasoning | Shadow calculation, free-space octree, cell merging, uniform-grid baseline |
| Planning System | PDDLStream integration, problem construction, replanning |
| Robot Control and Streams | IK, RRT-Connect motion planning, grasp sampling |
| Execution Pipeline | End-to-end walkthrough, action handlers, concrete scenario |
| Core Data Structures | All types, dataclasses, and enums |
| PDDL Domain Reference | Predicates, actions, streams, PDDL/Python alignment |
| Evaluation Framework | `eval_runner.py` matrix sweeps, `eval_plotter.py` PNG output, reproducing Results plots |
| Design Decisions | Rationale for key choices and proposal deviations |
| Known Issues and Roadmap | Audit status, open issues, future work |

## License

MIT
