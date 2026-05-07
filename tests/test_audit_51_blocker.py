"""
Regression test for audit #51.

compute_shadow_blockers must NOT list a creator/occluder as a blocker
when its CURRENT body geometry has either:
  (A) been relocated entirely past the shadow (out of camera→shadow
      corridor), or
  (B) migrated INTO the shadow's stale AABB on the far side ("the
      intersection on the other side" — the actual GUI failure user
      observed 2026-05-07; sense rays would hit the relocated body
      INSIDE the shadow region and loop on still_blocked).

Case C is the regression guard for the parent-relationship fallback's
original geometry-skew motivation (yellow ↔ shadow_of_yellow_object,
shared-face skew).  It must keep listing the creator as a blocker.

Pre-fix expectations:
  Case A: FAIL — fallback fires unconditionally, adds the relocated body.
  Case B: FAIL — primary 5x5 ray batch hits the body inside the shadow
                 and lists it as a blocker.
  Case C: PASS — creator still in corridor, primary ray batch hits it.

Post-fix expectations: all three pass.
"""
import numpy as np

from execution import compute_shadow_blockers


CAMERA_POS = np.array([0.1, -0.8, 0.7])


def test_relocated_creator_out_of_corridor_is_not_a_blocker(
    make_box_body, shadow_boxel, object_boxel, fake_env_and_registry,
):
    """Case A — orange body moved well past the shadow (y=+0.4)."""
    body = make_box_body([0.025, 0.025, 0.025], [0.0, 0.4, 0.5])
    shadow = shadow_boxel(
        "shadow_of_orange",
        min_corner=[-0.05, -0.18, 0.45],
        max_corner=[0.05, 0.0, 0.55],
        parent="orange_object",
    )
    obj = object_boxel("orange_object", "orange_object")
    env, reg = fake_env_and_registry({"orange_object": body}, [shadow, obj])

    blockers = compute_shadow_blockers(
        CAMERA_POS, reg, ["shadow_of_orange"], ["orange_object"], env,
    )

    assert blockers["shadow_of_orange"] == [], (
        "orange body has been relocated past the shadow; expected an "
        f"empty blocker list, got {blockers['shadow_of_orange']!r}"
    )


def test_creator_inside_stale_shadow_aabb_is_not_a_blocker(
    make_box_body, shadow_boxel, object_boxel, fake_env_and_registry,
):
    """
    Case B — orange body relocated INTO shadow_of_orange's stale AABB
    on its far side.  This is the user-observed scenario: shadow
    appears visible from the camera but compute_shadow_blockers still
    lists orange as a blocker, so sense reads the rays hitting orange
    inside the shadow as 'still_blocked' and loops.
    """
    body = make_box_body([0.025, 0.025, 0.025], [0.0, -0.05, 0.5])
    shadow = shadow_boxel(
        "shadow_of_orange",
        min_corner=[-0.05, -0.18, 0.45],
        max_corner=[0.05, 0.0, 0.55],
        parent="orange_object",
    )
    obj = object_boxel("orange_object", "orange_object")
    env, reg = fake_env_and_registry({"orange_object": body}, [shadow, obj])

    blockers = compute_shadow_blockers(
        CAMERA_POS, reg, ["shadow_of_orange"], ["orange_object"], env,
    )

    assert blockers["shadow_of_orange"] == [], (
        "orange body has migrated INTO the shadow's stale AABB; "
        "expected an empty blocker list (sense will discover the "
        "body via contains_nontarget rather than as a corridor "
        f"obstruction), got {blockers['shadow_of_orange']!r}"
    )


def test_creator_still_in_corridor_remains_a_blocker(
    make_box_body, shadow_boxel, object_boxel, fake_env_and_registry,
):
    """
    Case C — regression guard for the parent-relationship fallback's
    original geometry-skew motivation.  yellow has NOT been moved; its
    AABB sits between camera and shadow_of_yellow_object, sharing the
    shadow's near face.  The fix must keep listing yellow as a blocker.
    """
    body = make_box_body([0.025, 0.025, 0.025], [0.0, -0.15, 0.5])
    shadow = shadow_boxel(
        "shadow_of_yellow",
        min_corner=[-0.05, -0.125, 0.45],
        max_corner=[0.05, 0.025, 0.55],
        parent="yellow_object",
    )
    obj = object_boxel("yellow_object", "yellow_object")
    env, reg = fake_env_and_registry({"yellow_object": body}, [shadow, obj])

    blockers = compute_shadow_blockers(
        CAMERA_POS, reg, ["shadow_of_yellow"], ["yellow_object"], env,
    )

    assert blockers["shadow_of_yellow"] == ["yellow_object"], (
        "yellow body has not moved; expected ['yellow_object'] as the "
        f"blocker (regression guard), got {blockers['shadow_of_yellow']!r}"
    )
