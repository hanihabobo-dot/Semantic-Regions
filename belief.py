"""
Belief state for the partial-observability search.

Extracted from test_full_pipeline.py during the audit #26 refactor.
Pure bookkeeping — no PyBullet, no planner, no I/O.  This makes the
class trivially unit-testable and lets the orchestration loop in
test_full_pipeline.py read top-down without scrolling past dataclasses.
"""

from typing import Dict, List, Optional


class BeliefState:
    """
    Epistemic model of the robot's partial observability.

    The robot cannot see through occluders, so it doesn't know which shadow
    hides the target.  This class tracks what has been learned through
    sensing actions, enabling the replanning loop to avoid re-exploring
    already-checked shadows.

    Lifecycle per shadow:
      unknown  ─── sense ───► not_here    (target absent → eliminate)
                         ├──► found       (target present → goal reached)
                         └──► unresolved  (#P1 F15: repeatedly observed to
                              contain SOMETHING the render could not
                              localize.  The planner stops offering it —
                              otherwise the episode loops on it forever —
                              but this is NOT a claim that the target is
                              absent, and the run outcome discloses it.
                              Marking such a fragment 'not_here' was the
                              F15 belief lie: it retired the fragment the
                              target was physically sitting in.)

    ``occluders_moved`` records physical relocations so the planner can
    emit correct ``obj_at_boxel`` facts for objects that are no longer at
    their original positions.
    """

    def __init__(self, shadows: List[str], target: str):
        self.target = target
        self.shadow_status: Dict[str, str] = {s: 'unknown' for s in shadows}
        self.target_found_in: Optional[str] = None
        self.occluders_moved: Dict[str, str] = {}

    def mark_sensed(self, shadow_id: str, found: bool) -> None:
        """Update belief after sensing a shadow."""
        if found:
            self.shadow_status[shadow_id] = 'found'
            self.target_found_in = shadow_id
        else:
            self.shadow_status[shadow_id] = 'not_here'

    def mark_unresolved(self, shadow_id: str) -> None:
        """Park a shadow the robot could observe but never resolve (#P1 F15).

        Distinct from ``mark_sensed(found=False)``: that asserts the
        target is NOT in the region, which a "contains something I could
        not localize" observation does not support.  This records only
        that sensing it repeatedly failed to settle the question, so the
        planner should stop spending actions on it.
        """
        if self.shadow_status.get(shadow_id) == 'found':
            return
        self.shadow_status[shadow_id] = 'unresolved'

    def get_parked_shadows(self) -> List[str]:
        """Shadows parked unresolved — not eliminated, just not plannable."""
        return [s for s, status in self.shadow_status.items()
                if status == 'unresolved']

    def mark_occluder_moved(self, occluder_id: str, destination: str) -> None:
        """
        Mark that an occluder has been moved to a new location.

        Args:
            occluder_id: Boxel ID of the occluder that was moved.
            destination: Symbolic boxel ID for the destination (used by
                the planner to emit obj_at_boxel for the new location).
        """
        self.occluders_moved[occluder_id] = destination

    def get_unknown_shadows(self) -> List[str]:
        """Get list of shadows we haven't checked yet."""
        return [s for s, status in self.shadow_status.items() if status == 'unknown']

    def get_known_empty_shadows(self) -> List[str]:
        """Get list of shadows we've checked and found empty."""
        return [s for s, status in self.shadow_status.items() if status == 'not_here']

    def is_target_found(self) -> bool:
        """Check if we've found the target."""
        return self.target_found_in is not None
