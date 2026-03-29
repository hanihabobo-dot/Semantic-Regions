# Semantic Boxels for Task and Motion Planning

A PyBullet-based system for generating **semantic boxels** -- task-relevant 3D regions used for belief representation in Task and Motion Planning (TAMP) under partial observability. A Franka Panda robot searches for hidden objects by relocating occluders, sensing shadow regions, and retrieving targets, all planned via PDDLStream.

## Quick Start

```bash
pip install pybullet numpy
python3 -u test_full_pipeline.py
```

| Flag | Description |
|------|-------------|
| `--no-gui` | Headless mode (no PyBullet window) |
| `--log-level verbose` | Full debug output |
| `--scene default\|mixed\|scalability` | Scene preset |

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
