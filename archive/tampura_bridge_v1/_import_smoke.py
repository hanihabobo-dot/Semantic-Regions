#!/usr/bin/env python3
"""
ITEM 1 throwaway smoke (Phase 3-B) — prove our pipeline IMPORTS and a trivial
FastDownward plan RUNS inside TAMPURA's .venv (single-process, strategy A).

STRATEGY A (chosen 2026-06-06): run inside THEIR venv (/root/tampura-work/.venv,
py3.11, pybullet 3.2.7) with our repo + vendored pddlstream_lib on PYTHONPATH;
FastDownward is the prebuilt Linux ELF at
pddlstream_lib/downward/builds/release/bin/downward.

VENV INVENTORY (2026-06-06, code-verified):
  THEIR .venv : py3.11.15  pybullet 3.2.7  numpy 1.24.4  scipy 1.15.3
  OUR  wsl_env: py3.10.12  pybullet 3.2.7  numpy 2.2.6
  -> pybullet IDENTICAL (no ABI clash; single default client OK).
  -> deltas under A: py3.10->3.11, numpy 2.2->1.24 (our code must tolerate 1.24).
  -> our whole import chain (boxel_env + 9 modules) needs ONLY numpy + pybullet.

RUN (no GUI — console only):
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    cd /root/tampura-work/tampura_environments && \
    PYTHONPATH=/mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels:/mnt/c/Users/HaniAlassiriAlhabbou/git/pddlstream_lib \
    python /mnt/c/Users/HaniAlassiriAlhabbou/git/Semantic_Boxels/tampura_bridge/_import_smoke.py'
Exit 0 = all imports + a trivial FD plan succeeded.
"""
import os
import sys
import traceback

results = []  # (label, ok, detail)


def step(label, fn):
    try:
        detail = fn() or ""
        results.append((label, True, detail))
        print(f"[ OK ] {label}  {detail}")
    except Exception as e:  # noqa: BLE001 - smoke wants every failure surfaced
        results.append((label, False, repr(e)))
        print(f"[FAIL] {label}: {e!r}")
        traceback.print_exc()


def env_info():
    import importlib.metadata as md

    def v(pkg):
        try:
            return md.version(pkg)
        except Exception:
            return "(absent)"

    return (f"py={sys.version.split()[0]} numpy={v('numpy')} "
            f"pybullet={v('pybullet')} scipy={v('scipy')} | cwd={os.getcwd()}")


def import_theirs():
    import tampura
    import tampura_environments  # noqa: F401
    return f"tampura @ {os.path.dirname(tampura.__file__)}"


def import_ours():
    import boxel_data  # noqa: F401
    import boxel_types  # noqa: F401
    import robot_utils  # noqa: F401
    import shadow_calculator  # noqa: F401
    import free_space  # noqa: F401
    import uniform_grid  # noqa: F401
    import visualization  # noqa: F401
    import streams  # noqa: F401
    import belief  # noqa: F401
    import boxel_env  # noqa: F401
    return "boxel_env + 9 modules imported"


def import_pddlstream():
    import pddlstream
    import pddlstream_planner  # noqa: F401  (our entry; pulls in streams/FD wiring)
    from pddlstream.algorithms.meta import solve  # noqa: F401
    return f"pddlstream @ {os.path.dirname(pddlstream.__file__)}"


def fastdownward_runs():
    from pddlstream.language.constants import PDDLProblem
    from pddlstream.algorithms.meta import solve

    domain = (
        "(define (domain triv)\n"
        " (:requirements :strips)\n"
        " (:predicates (a) (b))\n"
        " (:action go :parameters () :precondition (a) :effect (b)))"
    )
    problem = PDDLProblem(domain, {}, None, {}, [("a",)], ("b",))
    try:
        solution = solve(problem, unit_costs=True)
    except TypeError:
        solution = solve(problem)
    plan = solution[0]
    if plan is None:
        raise RuntimeError("FastDownward returned no plan for a trivial task")
    return f"plan={[a.name if hasattr(a, 'name') else a for a in plan]}"


if __name__ == "__main__":
    print("==== Phase 3-B ITEM 1 import/venv smoke ====")
    step("env", env_info)
    step("import THEIRS (tampura, tampura_environments)", import_theirs)
    step("import OURS (boxel_env + chain)", import_ours)
    step("import PDDLSTREAM entry (+ meta.solve)", import_pddlstream)
    step("FastDownward executes trivial plan", fastdownward_runs)

    print("\n==== SMOKE SUMMARY ====")
    for label, good, detail in results:
        print(f"  {'PASS' if good else 'FAIL'}  {label}  {detail}")
    all_ok = all(r[1] for r in results)
    print(f"\nRESULT: {'ALL PASS' if all_ok else 'FAILURES PRESENT'}")
    sys.exit(0 if all_ok else 1)
