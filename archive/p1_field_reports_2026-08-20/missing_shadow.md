# missing_shadow.md — shadow_of_red_object label with no wireframe box

Repo: C:\Users\HaniAlassiriAlhabbou\git\Semantic_Boxels  (branch p1-real-grasp-perception)
Scene: `--scene random-pairs --goal holding --seed 0`
Matching run log used as evidence: `logs\run_2026-08-15_22-07-53\` (scene=random-pairs,
n_occluders=3, seed=0, goal=holding — confirmed via run header, lines 9-16 of
run_2026-08-15_22-07-53.log). Six other seed=0 random-pairs/holding runs exist from the
same day (18-31-19, 18-29-47, 18-28-00, 18-03-01, 17-06-45, 16-45-39); scene geometry is
seed-deterministic so all of them reproduce the same numbers.

## TL;DR

**Root cause = degenerate geometry, not a render-path divergence.** The single-AABB
shadow-construction path in `shadow_calculator.py` picks the **wrong dominant axis (Z
instead of a lateral X/Y axis)** for occluders that are tall+narrow AND close to the
camera (steep look-down angle) — exactly what the P1 scene change created for
`red_object`. That miscalculation collapses `shadow_of_red_object` into an
**inverted, ~17-micron-thick sliver sitting exactly under the red block's own
footprint** (`min_corner.z=0.325 > max_corner.z=0.324998...`, `extent.z = -8.7e-6`,
`volume = -5.4e-8`). `visualization.py` draws the box and the label from the *same*
`BoxelData.center`/`.extent` in one function — there is no separate label-vs-box code
path — but a box with an 8.7-micron half-height is invisible at GUI scale while the
text label (a single point + string, no size dependency) renders fine. This also
silently defeats `streams.test_boxel_fits`, so the planner can never treat this region
as capable of hiding anything, even though the code still emits `blocks_view_at`
facts claiming it blocks visibility.

## Evidence: boxel_data.json (logs/run_2026-08-15_22-07-53/boxel_data.json)

`red_object` (the occluder, OBJECT boxel):
```
min_corner: [0.014872487616926930, -0.275485803053388930, 0.324982550314447900]
max_corner: [0.070367623153191240, -0.219973507291713080, 0.460750203399037940]
center:     [0.042620055385059086, -0.247729655172551020, 0.392866376856742900]
extent:     [0.027747567768132156,  0.027756147880837925, 0.067883826542295020]
```

`shadow_of_red_object` (SHADOW boxel, created_by_object="red_object"):
```
min_corner: [0.014872487616926930, -0.275485803053388930, 0.325]
max_corner: [0.070367623153191240, -0.219973507291713100, 0.324982550314447900]
center:     [0.042620055385059086, -0.247729655172551020, 0.324991275157223900]
extent:     [0.027747567768132156,  0.027756147880837910, -8.724842776058894e-06]
volume:     -5.375658977478784e-08
```

Compare with the healthy shadows in the same file:
```
shadow_of_green_object:      extent = [0.1338, 0.1362, 0.0636]   volume = 0.00927
shadow_of_orange_object__00: extent = [0.0271, 0.0972, 0.0661]   volume = 0.00140
shadow_of_orange_object__01: extent = [0.0290, 0.0972, 0.0661]   volume = 0.00149
```

Two things jump out for the red shadow, both diagnostic:

1. **X/Y are byte-for-byte identical to `red_object`'s own X/Y min/max** — the shadow's
   lateral footprint never extended past the occluder's own base at all. A real shadow
   (like green's or orange's) is *larger* than the occluder footprint in the
   lateral/away-from-camera direction; red's is exactly the same rectangle.
2. **Z is inverted**: `min_corner.z = 0.325` (the nominal `table_surface_height`
   passed into `ShadowCalculator`) is *greater* than `max_corner.z = 0.32498255...`
   (red_object's own actual resting min-z, which sits ~17.4 µm below the nominal table
   height — ordinary PyBullet contact/AABB settling noise). `extent.z` and `volume`
   are consequently negative.

This is a "shadow" that is really just the occluder's own footprint flattened to
(less than) zero height. It is not a lateral clipping artifact and it does not sit
off-table — X/Y match the occluder exactly, well inside table bounds.

## Root-cause trace through shadow_calculator.py

`ShadowCalculator.calculate_shadow_boxel` (shadow_calculator.py:41-270):

1. **Back-corner selection is 3-D and single-direction** (lines 81-110). It computes
   one direction vector `cam_to_obj_norm = normalize(obj_center - cam_pos)` and keeps
   any of the object's 8 corners whose offset from center has positive dot product
   with that *one* vector (line 102-104). For a squat, wide occluder this reliably
   splits the box into "4 corners facing the camera" / "4 corners facing away" along a
   lateral axis. For `red_object` — a **tall, narrow** occluder (Z half-extent 0.0679 m
   vs X/Y half-extents ~0.0277 m, i.e. Z is ~2.4x XY) sitting **close to the camera**
   (camera=[0.1,-0.8,0.7], red center y=-0.248, so only ~0.55 m of Y separation vs.
   ~0.7 m of camera height above the table) — the direction from camera to object is
   dominated by the *downward* component, not the lateral one. Working the dot
   products through with the actual numbers above: **all 4 bottom-face corners** (the
   object's own base, already resting on the table) qualify as "back corners," and
   **none of the top-face corners do**. (For comparison, doing the same arithmetic for
   `green_object`, which is ~1.0 m of Y away from the camera instead of ~0.55 m, the Y
   term dominates the Z term and the normal lateral split happens — which is why
   green's shadow looks correct.)

2. **Ray casting from those (already-on-the-table) back corners** (lines 112-127) then
   fires rays whose direction has a large negative-Z component starting from points
   that are already sitting at table height. The rays immediately "hit" the table at
   essentially their own starting position (t≈0, with float epsilon), so `hit_points`
   end up equal to the object's own base corners, not a point projected further away
   across the table (lines 129-161). Note the asymmetric clamp here: line 139 floors
   *every* hit point's z up to `table_z` on the raw per-ray-hit path, but the no-hit
   fallback path (142-159) and the batch aggregation only floor `h_min[2]`
   (line 166: `h_min[2] = max(h_min[2], table_z)`) — there is no equivalent ceiling
   applied to `h_max[2]`, so a hit point with a tiny negative epsilon below `table_z`
   survives into `h_max`.

3. **AABB union with the object's own bounds** (lines 168-182): because the hit points
   already equal the object's own base corners in X/Y, `full_min`/`full_max` end up
   equal to the occluder's own `o_min`/`o_max` in X and Y, and Z is dominated by the
   object's own top face via the "Enforce Height Overestimate" step (line 182). At
   this point the shadow AABB is (up to float noise) *identical* to the occluder's own
   AABB — not yet degenerate, but geometrically wrong (a "shadow" that exactly
   coincides with the object cannot yet be flattened out).

4. **"Subtract object from shadow"** (lines 184-194) is where it breaks. `shadow_dir =
   mean(hit_points) - obj_center`. Since the 4 back-corner hit points are symmetric in
   X and Y around the object's own center (all 4 XY sign combinations were selected as
   back corners — see step 1), the X and Y components of `shadow_dir` cancel to ~0,
   leaving Z (`table_z - obj_center.z ≈ -0.068`) as the only sizeable component.
   `dom_axis = argmax(abs(shadow_dir))` (line 186) therefore picks **axis 2 (Z)**
   instead of a lateral axis. With `shadow_dir[2] < 0`, line 194 executes:
   `s_max[2] = min(s_max[2], o_min[2])`, i.e. the shadow's *upper* Z bound gets pulled
   down to the occluder's own base (`o_min[2] = 0.32498255...`), while `s_min[2]`
   stays at the table-clamped `full_min[2] = 0.325` (from the line-166/177 floor).
   Because `o_min[2]` (0.32498255...) is a hair below the nominal `table_z` (0.325)
   due to ordinary contact settling, **`s_max[2]` ends up strictly less than
   `s_min[2]`** — the exact inverted sliver recorded in boxel_data.json.

5. **No degenerate-extent guard on this path.** `_overhang_overlaps_obstacle`
   (lines 277-300) returns False for the isolated red occluder (nothing else sits near
   its lateral overhang), so execution takes the **`else` branch at lines 248-255**
   ("No overhang collision → one big shadow AABB"), which appends the shadow
   unconditionally — no size/ordering check. Compare this to the two-slab carve branch
   just above it (line 240: `if np.any(slab_max - slab_min <= 1e-6): continue`) and to
   `_create_boxel_from_bounds` (lines 365-379, used only by `_subtract_aabb`
   fragments), which both explicitly reject degenerate (`extent <= 0` or
   `< MIN_EXTENT = 0.001`) boxes. The single-AABB branch that red's shadow actually
   goes through has no equivalent check, so the inverted box is registered as-is.

6. `boxel_data.py`'s `BoxelData.extent`/`.center`/`.volume` (lines 51-62) and
   `BoxelRegistry.add_boxel` (lines 127-143) never validate `min_corner < max_corner`
   anywhere, so the inverted box round-trips untouched into the registry and into
   `boxel_data.json`.

## Why the label shows but the box doesn't (visualization.py)

There is **no separate label-vs-box code path** — this rules out hypothesis (2) from
the brief as originally framed ("registry labels vs per-boxel box draws"). Both
`draw_registry` and `draw_boxel_data` ultimately call the same
`BoxelVisualizer._draw_one_boxel` (visualization.py:116-159) for every boxel,
including `shadow_of_red_object`, and that one function draws the wireframe lines
*and* the label from the *same* `c = bd.center` / `e = bd.extent` (lines 120-121):

- Wireframe: `corners, edges = wireframe_corners_and_edges(c, e)` (line 130), then 12
  `addUserDebugLine` calls (131-140). With `e[2] = -8.7e-6`, every corner is offset
  from `c` by at most 8.7 micrometers in Z — the "box" is real and does get 12 debug
  lines drawn, but it is roughly 1/6000th of a millimeter tall, physically
  indistinguishable from a point at GUI/viewport scale, and its X/Y footprint sits
  exactly under the visible red occluder's own base and just below the table surface
  it's resting on. It is not culled or skipped by any guard in the code — it is simply
  too small to see, doubly so because it is spatially coincident with the opaque red
  block and the table mesh.
- Label: `label_pos = [c[0], c[1], c[2] + e[2] + 0.01]` (line 148) — since `e[2]≈0`,
  this places the text ~1 cm above the table surface, right at red_object's own X/Y
  position, and `addUserDebugText` (149-155) has no size/visibility guard tied to the
  box extent — a point+string always renders regardless of how degenerate the boxel
  geometry is.

So the "label but no box" symptom is a direct, mechanical consequence of the geometry
bug: same function, same inputs, but a wireframe made of near-zero-length edges is
invisible while a text label anchored to a point is not.

## Ruled out: "drawn but occluded from this viewpoint"

The brief's alternative hypothesis (present-but-hidden-behind-the-block-or-under-the-table)
does not hold: the box's Z half-extent is 8.7 **micrometers**, not merely
small — it would be invisible from *any* camera angle at this scale, not just the
current one. This is a true degenerate/inverted-AABB bug, not an occlusion-of-the-debug-draw
issue.

## Ruled out: "shadow lands off-table and gets clipped to nothing"

The table-bounds clamp (shadow_calculator.py:174-179) never engages here — the
collapsed "hit points" already coincide with the occluder's own on-table footprint
(X∈[0.0149,0.0704], Y∈[-0.2755,-0.2200]), which is well inside the table's X/Y range
(table X/Y bounds recoverable from the FREE_SPACE boxels in the same file, e.g.
`free_000` spans X∈[-0.1,0.3], Y∈[-0.4,0.4]). Nothing here got clamped away at an
edge; it collapsed because the wrong axis was chosen for subtraction, as detailed
above.

## Planner-facing consequence (paper-relevant, not just cosmetic)

Checked `logs\run_2026-08-15_22-07-53\problem_initial.pddl` and `streams.py`:

- `shadow_of_red_object` **is** emitted into the PDDL problem: `(Boxel
  shadow_of_red_object)` (line 48), `(is_shadow shadow_of_red_object)` (line 165), and
  multiple `(blocks_view_at <obj> free_006 shadow_of_red_object)` facts (lines 65, 81,
  99, 104) — i.e. the planner is told this region blocks the camera's view of
  green_object, orange_object, and red_object itself.
- But grepping the same file for any `(boxel_fits <obj> shadow_of_red_object)` fact
  returns **zero matches** — none exists for any object.
- `streams.py:379-418` `test_boxel_fits` explains why:
  `dest_extents = dest_boxel.max_corner - dest_boxel.min_corner` (line 417) is
  negative on the Z axis for this boxel, and `return bool(np.all(dest_extents >=
  obj_extents))` (line 418) is unconditionally False whenever any axis of
  `dest_extents` is negative, regardless of which object is being tested.

**Net effect:** the planner is told this region *blocks visibility* (so it counts
against "the scene is fully sensed") but is *never* considered large enough to
contain/hide anything (`boxel_fits` never holds), and — per the `sense` action's
documented precondition contract in `streams.py:420-435`
(`test_target_can_hide_in_shadow`, gated by `test_boxel_fits`) — a `sense` action
targeting this shadow can never be generated. In this particular run the hidden
target (`blue_object`) happens to be hidden behind `green_object`/`orange_object`
instead (log line 55-58: `shadow_of_green_object`/`shadow_of_orange_object` list
blockers, not `shadow_of_red_object`), so this specific run's plan is unaffected. But
the bug is structural: **any occluder that is tall, narrow, and close to the fixed
overhead camera (i.e., roughly the front-left region of the table, matching exactly
where the P1 scalability scene generator places occluders and where the user saw
this) will get this same collapsed, negative-volume shadow.** If a target were
genuinely hidden there, the boxel occlusion model would represent that hidden volume
as capable of blocking view (for scoring "is the scene sensed") while being
structurally unable to ever match a `sense`/hide precondition for an actual object —
a silent gap in the occlusion model, not merely a GUI rendering glitch. This is worth
flagging as a planner-correctness issue for the paper, not just a visualization
cosmetic one.

## Why this is new on this branch (P1 scene change)

Before the P1 scalability change, `random-pairs` occluders were 0.06-0.09 m cubes
(comparable X/Y/Z extents). The bug requires the object's Z half-extent to dominate
its lateral half-extents by enough that, combined with the camera's fixed elevation
angle to a near-camera object, *all 4* corners on one face (here, the bottom face)
pass the back-corner test while *none* on the opposite face do. Tall/narrow occluders
(Z half-extent 0.050-0.075 m vs XY half-extent 0.025-0.030 m, i.e. up to ~3x) sitting
close to the camera are exactly the new failure-inducing shape/placement combination;
cubes of the old size did not tip the dot-product balance this way for the same
camera/table geometry (verified: the same math applied to `green_object`, which is
further from the camera in Y, correctly keeps the split on the Y axis and produces a
normal, non-degenerate shadow).

## Minimal fix proposal (no code changes made — investigation only)

1. **Primary fix — constrain the shadow direction/back-corner test to the horizontal
   (table) plane.** The whole ray-hit model already only ever resolves shadow extent
   onto the table surface (`hit_pt[2]` is always clamped/forced to `table_z`, lines
   139 and 152-159; the shadow's Z range is always the "height overestimate" from line
   182, never derived from ray hits). So the *direction* used both for back-corner
   selection (line 84's `cam_to_obj_norm`) and for the dominant-subtraction-axis
   (line 185-186's `shadow_dir`) should be computed from the **X/Y components only**
   (zero out or drop the Z component before normalizing / before `argmax`). This keeps
   `dom_axis` always in `{0, 1}`, matching the model's actual 2.5-D intent, and
   prevents the "subtract down to the object's own base" collapse for any tall/narrow,
   camera-adjacent occluder.
2. **Defensive fix — guard the single-AABB branch.** Add the same degenerate-extent
   check used at line 240 (`np.any(slab_max - slab_min <= 1e-6)`) and in
   `_create_boxel_from_bounds` (lines 370-372) to the `else` branch at lines 248-255,
   so a computation error can never again silently emit an inverted/negative-volume
   SHADOW boxel. Given the `blocks_view_at`-vs-`boxel_fits` mismatch above, on trip
   this should probably raise/log loudly rather than silently drop the shadow, since a
   real occluder should essentially always cast *some* non-degenerate shadow once (1)
   is fixed — a defensive check that fires afterward is a signal something is still
   wrong, not an expected/normal path.
3. **Optional hardening — validate ordering in `BoxelData`.** `boxel_data.py`'s
   `extent`/`volume` properties (lines 51-62) and `BoxelRegistry.add_boxel`
   (127-143) never assert `min_corner <= max_corner`. A cheap invariant check (e.g. in
   `add_boxel`, or as a `BoxelData.__post_init__`) would have caught this class of bug
   immediately at registration time instead of it silently reaching the GUI and the
   JSON artifact.

Fix (1) is the one that actually restores correct shadow geometry (a real, non-zero
lateral shadow region behind `red_object`); (2) and (3) are safety nets that turn any
future recurrence into a loud failure instead of a silently-missing occlusion region.
