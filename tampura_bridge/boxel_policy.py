"""Phase 3-B bridge policy: our Policy subclass plugged into TAMPURA's rollout.

ITEM 2 = passthrough only. get_action returns no-op so the rollout loop runs
end-to-end on their find_dice env *without our planner yet*, proving the seam.
Later (ITEM 12) this is replaced by our PDDLStream planner.
"""
from typing import Dict, Tuple

from tampura.policies.policy import Policy
from tampura.structs import AliasStore, Belief
from tampura.symbolic import Action


class BoxelPolicy(Policy):
    """Drives TAMPURA's rollout with our (eventually PDDLStream-backed) brain.

    ITEM 2 passthrough: emit no-op every step. rollout() special-cases
    action.name == "no-op" (policy.py:125) by skipping env.step and copying the
    belief, so the loop advances harmlessly for max_steps.
    """

    def get_action(
        self, belief: Belief, store: AliasStore
    ) -> Tuple[Action, Dict, AliasStore]:
        return Action(name="no-op"), {}, store
