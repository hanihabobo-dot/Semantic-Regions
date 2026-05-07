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
      unknown  ─── sense ───► not_here  (target absent → eliminate)
                         └──► found     (target present → goal reached)

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
