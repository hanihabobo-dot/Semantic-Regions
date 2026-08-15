"""Bridge planner (audit #120): OUR PDDLStreamPlanner, run on TAMPURA's env.

This is OUR planner exactly as we wrote it -- pddlstream_planner.PDDLStreamPlanner
-- with two injections so it runs on TAMPURA's find_dice scene:

  (1) self.streams is the BRIDGE's robot-aware streams (streams_boxel.BoxelStreams
      on TAMPURA's Panda: finger joints [12,13], panda_grasptarget EE link 14,
      multi-seed FK-verified IK), NOT the shared streams.BoxelStreams.
  (2) self.domain_pddl is domain_find_dice_streamful.pddl (streamful pick/place/
      move/stack + the find_dice sense/go_home), NOT the shared domain.

EVERY planning method -- _build_init, _get_stream_map, create_problem, plan -- is
INHERITED UNCHANGED.  So the geometric reasoning (sample-grasp -> compute-kin ->
plan-motion, certified into the plan by PDDLStream's adaptive search) and the
classical search are byte-for-byte our pipeline's; only the robot the streams
target and the domain file differ.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from pddlstream_planner import PDDLStreamPlanner, read_pddl_file


class BoxelBridgePlanner(PDDLStreamPlanner):
    """PDDLStreamPlanner with the bridge's streams + streamful find_dice domain
    injected; all planning logic is inherited from PDDLStreamPlanner unchanged
    (see module docstring)."""

    def __init__(self, streams, registry, shadow_occluder_map=None,
                 camera_pos=None):
        # Deliberately DO NOT call super().__init__: it would build a fresh
        # shared-streams.BoxelStreams and load the shared domain.  We set the
        # same attributes by hand, injecting the bridge's streams + the
        # streamful find_dice domain instead -- every other method then runs
        # the inherited PDDLStreamPlanner code against these.
        self.registry = registry
        self.robot_id = streams.robot_id
        self.shadow_occluder_map = shadow_occluder_map or {}
        self.camera_pos = camera_pos
        self.tray_name = None
        self.streams = streams                       # bridge streams (their Panda)
        self.home_config = streams.home_config
        self.domain_pddl = read_pddl_file('domain_find_dice_streamful.pddl')
        self.stream_pddl = read_pddl_file('stream.pddl')
        self.last_init = None
