"""Phase 3-C: bridge-side writes into TAMPURA's SceneBelief so its abstract()
(find_dice/env.py:306) emits the atoms their reward checks (holding(die) AND
at-home == 1.0), WITHOUT editing their env.  Path B: our faithful execution
drives their Panda; these helpers register the symbolic result in the belief
the rollout carries forward (mutate-in-place; the no-op deepcopy preserves it).

  holding(?o)   <- belief.grasp is not None and belief.grasp_body == ?o
  is-target(?o) <- category "dice"  (automatic)
  at-home       <- belief.current_conf ~= DEFAULT_ARM_POS
  known-pose(?o)<- ?o in belief.object_poses
  moved(?o)     <- ?o in belief.moved
"""
from tampura_environments.panda_utils.robot import DEFAULT_ARM_POS

DIE_CATEGORY = "dice"
BRIDGE_GRASP = "g_bridge_die"   # sentinel; reward checks holding, not the grasp value


def die_alias(belief):
    """The die's 'physical' alias in the belief's world (seed-generic)."""
    for o, c in zip(belief.world.objects, belief.world.categories):
        if c == DIE_CATEGORY:
            return o
    raise ValueError("no die ('dice' category) in belief.world")


def cup_aliases(belief):
    """The non-die ('cup') aliases in the belief's world."""
    return [o for o, c in zip(belief.world.objects, belief.world.categories)
            if c != DIE_CATEGORY]


def mark_moved(belief, obj_alias):
    """Record that obj_alias was relocated (their 'moved' fact)."""
    belief.moved = sorted(set(list(belief.moved) + [obj_alias]))


def mark_known(belief, obj_alias, pose):
    """Record obj_alias's pose as known (their 'known-pose' fact) — sensing the
    die supplies its observed pose (a pbu.Pose)."""
    belief.object_poses[obj_alias] = pose


def mark_holding(belief, obj_alias):
    """Record obj_alias as grasped (their 'holding' fact)."""
    belief.grasp = BRIDGE_GRASP
    belief.grasp_body = obj_alias


def mark_away(belief):
    """Arm no longer at the home config (their 'at-home' becomes false while the
    robot is manipulating).  current_conf=None reads as not-at-home in abstract()."""
    belief.current_conf = None


def mark_at_home(belief):
    """Record the arm back at the home config (their 'at-home' fact)."""
    belief.current_conf = list(DEFAULT_ARM_POS)
