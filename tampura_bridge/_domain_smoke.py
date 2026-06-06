#!/usr/bin/env python3
"""Phase 3-B ITEM 10 dry test: confirm the find_dice domain variant PARSES and a
relaxed PICK GROUNDS from known-pose facts WITHOUT any IK/grasp streams.

Streamless classical plan (stream_pddl=None) over pddl/domain_find_dice.pddl:
goal (holding cup) from an init asserting the cup's known pose -> plan = [pick].

RUN (no GUI):
  wsl -d Ubuntu -e bash -lc 'source /root/tampura-work/.venv/bin/activate && \
    PYTHONPATH=/mnt/c/.../Semantic_Boxels:/mnt/c/.../pddlstream_lib \
    python /mnt/c/.../Semantic_Boxels/tampura_bridge/_domain_smoke.py'
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from pddlstream.algorithms.meta import solve
from pddlstream.language.constants import PDDLProblem


def _read(name):
    with open(os.path.join(_REPO, "pddl", name)) as f:
        return f.read()


def main():
    domain = _read("domain_find_dice.pddl")
    cup, b = "cup_0", "boxel_cup_0"
    init = [
        ("Obj", cup), ("Boxel", b),
        ("handempty",), ("clear", cup),
        ("obj_at_boxel_KIF", cup, b), ("obj_at_boxel", cup, b),
        ("at_sense_config",),
    ]
    goal = ("holding", cup)
    problem = PDDLProblem(domain, {}, None, {}, init, goal)
    try:
        solution = solve(problem, unit_costs=True)
    except TypeError:
        solution = solve(problem)
    plan = solution[0]
    names = None if plan is None else [a.name for a in plan]
    print("plan:", names)
    ok = bool(names) and any(n == "pick" for n in names)
    print("RESULT:", "PASS (pick grounded)" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
