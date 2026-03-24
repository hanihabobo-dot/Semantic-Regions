# Supervisor Meeting Summary — 2026-03-22

**Participants:**
- **Speaker 1 (Till)** — Supervisor 1
- **Speaker 2 (Daniel)** — Supervisor 2
- **Speaker 3 (Hani)** — Student

**Topic:** Pick-and-place design, boxel merging/splitting after actions, free-space reasoning, grasping.

---

## 1. Pick-and-Place Replaces Push (00:00:49)

Hani opens by demonstrating the updated system. The main change since the last meeting: **push actions are replaced by pick-and-place**.

- The previous push approach was abandoned because the push destination was effectively hardcoded.
  > *"The somewhere is hardcoded and the problem was the solution was almost modeled in the PDDL actions, which is something we didn't want."*

- With pick-and-place, the **target boxel is an explicit action parameter**, so the planner genuinely decides where to move the object.
  > **Till:** *"The target box is now a parameter of the action, I guess."*
  > *"That was the main issue I had with the previous version. So now you can actually learn because you move the box to a different place."*

- **Grasping is still hardcoded**: the object gets attached to the end-effector via `p.createConstraint`, causing it to be "sucked in" rather than smoothly grasped. Hani acknowledges this is a simplification for now.

- **Side note on push**: Both supervisors agree that push could still be used as the *physical motion primitive* — what matters semantically is that the destination is an explicit parameter, not whether push or pick-and-place is used internally.
  > **Till:** *"How you actually implement the action, it's a different sort."*
  > **Daniel:** *"Semantically it's the same — pushing and picking and placing."*

- **Current placement logic**: the place action picks the first free boxel it finds (random), with no size fitness check and no adjacency preference.
  > *"It picks a random free voxel so far and just puts it there so it doesn't check whether it would fit and whether it makes sense."*

---

## 2. Sensing While Holding an Object (00:04:16)

Till raises an open question about sensing during pick-and-place.

> **Till:** *"Do you assume you don't see anything while you're holding the object? Because otherwise you could just pick up the object, look, and then put it back."*

Hani explains the current behaviour: raycasting is done to the shadow region, and if it intersects the robot arm, the arm is moved back home before retrying.

> **Till:** *"After picking up a box, you could already see and then just put it back. Is that something you allow, or do you assume you can't make any sensing while you're holding a box?"*

Hani: if the view is still blocked after picking, a replan occurs; if it is not blocked, the robot can sense.

> **Till:** *"Is it blocked by the arm?"*
> **Hani:** *"If it's still blocked — if it's not blocked, it will... yeah, I see."*

**This question was left unresolved.** No explicit decision was made on whether pick-observe-replace is an intended behaviour or an accidental side effect. Needs documentation.

---

## 3. Place Target Fitness and Adjacency Preference (00:06:29)

Daniel asks how placement works in practice and confirms it is currently purely random with no fitness guarantee.

> **Daniel:** *"There's no guarantee about the target boxel, right? It's just any box."*

Hani confirms and states the intent to add a certifier that checks the destination boxel is large enough to contain the placed object.

> **Daniel:** *"Ideally we want some adjacency — just pick the first adjacent voxel that's big enough."*

Hani then raises a related but distinct problem: after merging, corner regions may still have small residual boxels that are individually too small but collectively form a valid placement area.

> **Hani:** *"I might also have a bunch of small voxels that combined can actually be a free space. And I also need to reason about that. Because I can have, after the merger, I can still at some corners have small boxes."*

---

## 4. Re-Splitting / Re-Evaluation After Environment Change (00:09:49)

Hani identifies the stale partition problem:

> **Hani:** *"Once the environment changes, I keep working on the assumption that I still have these exact same splittings — free and not free — but maybe some of the boxes that were labelled as not free are now free, and vice versa."*

He distinguishes this from the placement problem:
- The placement problem: wanting to place an object spanning multiple free adjacent boxels.
- The re-evaluation problem: the entire free/occupied/shadow partition is stale after any scene-changing action.

> **Hani:** *"What I want is to put it in a place where it's not just fully contained within one voxel. If it's also fully contained in another nearby voxel, but it doesn't intersect an unfree voxel, then I should also want to put it there."*

---

## 5. Correct Merge Condition (00:10:50)

Till articulates the core design principle for merging:

> **Till:** *"One thing that we want to do is to constrain the motion plan as little as possible while still keeping a consistent logical state, which means you should merge all the boxes that have the same properties, meaning they block the same other boxes. What you don't want is to merge two boxes where one box blocks the view to some object where the other one doesn't. This should be separate because then you can decide whether you want to block the view or not. But if they have the same properties, and they are adjacent, they should just be merged into one."*

Hani mentions his existing convexity condition (only merge if the result is convex). Till acknowledges this:
> **Till:** *"Yes, okay. That probably makes sense too."*

Daniel notes the consequence:
> **Daniel:** *"I think it's important to know that the implication of that is that the boxes will generally just stay rather small, probably."*

On minimum size:
> **Daniel:** *"A reasonable minimal size is like the size of the smallest objects that you realistically deal with. If we imply that boxes should be merged whenever the logical properties in the symbolic domain are the same, then we will naturally not have very big connected voxels, which is fine."*

Hani asks whether it's better to keep boxes separated but annotate adjacency rather than merging. Daniel and Till both say the merge operation is still desired:
> **Daniel:** *"The idea was that we want to have this merge/unmerge property to not always deal with a tiny voxel grid that's hard to model and reason about. So I think we still want the merge operation."*

---

## 6. The Merge Trade-Off — Two Constructed Examples (00:15:37)

Till acknowledges the tension and constructs two concrete examples.

### Example A — Aggressive merging causes planner failure

> **Till:** *"You have a box in the middle. Free space in front of it. Behind the box there's some box where you don't know whether the target is. The correct solution is to pick up the block in the middle and move it to the free space on the right-hand side. But currently, if you model free space as one large box, your plan will tell you: if you move that box to that free space, it will still block the view to the box in the very back. So that's not actually a solution, and there's no other solution. Because our discretization is too coarse."*
> *"That's kind of an argument against merging free space no matter the properties."*

### Example B — Fine-grained discretisation prevents placement

> **Till:** *"Suppose you have a large box and you need to move it to see behind. But there's no other box that's large enough to actually take this box. Then there's no way to move it."*

### Resolution: Multi-Variant Place Actions

Hani: the certifier for the place action should verify the object fits in one or more boxels.

> **Till:** *"What you can do is you can have multiple variants of the place action. The first one would occupy one boxel and the second... occupy two."*
> **Hani:** *"OK, nice. OK, that's good."*
> **Till:** *"If you do that, then you can always keep the finest discretisation that keeps the logical state. You can still move objects because it will just occupy multiple boxes which will then be merged into one."*

**Agreed approach:** have `place-in-1-boxel`, `place-in-2-boxels`, etc., each with an adjacency precondition and a PDDLStream certifier that verifies the object's bounding box fits in the union of the target boxels.

---

## 7. Two Architectural Approaches for Merging/Splitting (00:20:02)

The conversation converges on two distinct approaches for handling boxel management in the planning framework.

### Approach 1 — Opaque re-boxelisation (chosen)

- Boxelisation is a Python-side operation, completely invisible to PDDL.
- After each action that changes the scene: re-boxelise → replan.
- Only use the first action(s) from each plan, then re-boxelise and replan.

> **Till:** *"We just do basically voxelisation, not in the planning domain at all. It's just an opaque operation that changes the state space and we replan. So we plan and then after doing one action we re-boxelise or whatever you want to call it and then replan."*

**Risks:**
- Must always replan after scene-changing actions (forced replanning).
- Need to be careful to avoid loops.
  > **Daniel:** *"You need to be really careful to avoid loops. If you always do like replan and do one action, that could be a problem."*
- May fail to find a plan if the intermediate state is too restrictive (Example A above).

### Approach 2 — PDDL-level merge/split with active representatives (deferred)

- Maintain a base grid of smallest boxels; mark some "active" as representatives of merged groups.
- Merge and split are explicit PDDL actions, possibly certified by PDDLStream.
- The planner knows the post-action boxel state, so no replanning is needed.

> **Daniel:** *"Only every fourth box on the grid is active, meaning they subsume all the other boxes until they meet another active boxel. That's your level of abstraction. Then you have a fixed number of objects, but it's still more efficient for the planner."*
> **Till:** *"The advantage is we can actually compute one plan that reaches the goal without ever needing to replan. The disadvantage is we need to manage all this voxel management in the domain. It's possibly a lot more actions because you will have these merge/split things, and you probably need to sample a lot more."*

**Decision: start with Approach 1.**

> **Till:** *"Maybe we can keep this as an interesting idea, but for now just stick to the simpler first approach. And ideally at the end we could compare the two, but I wonder whether this is actually achievable."*

When Hani asked to keep the active voxel idea in a limited form:
> **Daniel:** *"No, I don't think so."*
> **Daniel:** *"Don't think about that."*

These were explicit rejections — active voxels are not just deferred, they were actively discouraged for the current scope.

---

## 8. Refined Merge Condition — Observability Requirement (00:49:52)

Till adds a second condition to the merge rule beyond logical property equivalence:

> **Till:** *"I think the rule for merging boxes is that there are two things. For one, the two boxes should either both be visible currently or neither of them is observable. They're completely in the shadow region or not at all. And second, for the other voxels, these voxels should block the same voxels, so meaning the shadow is the same."*

**Merge order:**
> **Till:** *"If you look from the camera, you basically start merging in the back and go forward. And for example when there's an object, then all the boxes in front of that object will not be merged because they have different properties — some of them block the object, some don't."*

**Applies to both initial boxelisation and post-action re-merge:**
> **Till:** *"And that's true both for the initial boxelisation and for the merging rules after doing some action. So actually if we replan anyway, there's no need to do some kind of trickery matching logic. You can just re-boxelise after doing each action."*

---

## 9. Re-Boxelisation Strategy — Phase 1 Naive, Phase 2 Incremental (00:52:18)

> **Daniel:** *"Yeah, I think that's the quickest way of at least testing the approach."*
> **Hani:** *"Should I re-boxelise everything? Should I do it every time?"*
> **Daniel:** *"So for now, I would just do it every time."*

**Critical constraint — observation history must survive re-boxelisation:**
> **Till:** *"The only thing that you need to track is which boxes have you already observed. That information needs to be preserved."*

Hani raises the concern that after re-boxelisation, the boxel IDs and boundaries will be different. Supervisors clarify:
> **Daniel:** *"No, no, no, that shouldn't go wrong. It should still be a merging process. It should not be generated from scratch."*
> **Hani:** *"Oh, it's not. We're just talking about the merging process. Okay."*

> **Till:** *"Logically, if you do just voxelisation from scratch, the result should be the same if you do this multiple times. So basically, the merging logic should give you the same result as if you just voxelised from scratch, except that you need to keep track of the things that are not actually..."*

On naive vs incremental:
> **Till:** *"That would be a kind of naive implementation that should work, but maybe slow because you do a lot of things again and again that are not necessary. So it may be slow — just do some kind of merging and splitting logic [incrementally as the optimisation]."*

**Splitting after actions:**
> **Hani:** *"After doing an action, do I still have splitting?"*
> **Till:** *"If you move an object into another boxel, then you need to split that boxel into the part where the object is and then the part where the object is not."*

---

## 10. Constraint Attachment Fix — Objects Flying Around (00:56:26)

Supervisors observe objects flying around during the pick demonstration and diagnose the cause.

> **Daniel:** *"This behaviour is very weird. Like this is not how it should be. It should just be: get the gripper close and then add an attachment constraint without moving the object anymore."*

Hani explains: the constraint is currently attached to the surface of the gripper, not at the object's actual current position. Because the object is not at the gripper surface yet, the constraint creates a corrective force that snaps the object toward the gripper, disturbing nearby objects.

> **Daniel:** *"It should not teleport. It should not move. You bring the gripper close, you attach it with a constraint, and then it moves with the gripper."*
> **Till:** *"Then you suddenly have a moving object that also disturbs everything nearby. Yeah."*

**Fix:** compute the actual EE-to-object relative transform at constraint creation time. The object should not move when the constraint is created. *(This was later implemented as audit #98.)*

---

## 11. Grasping Explicitly Deprioritised (00:58:06)

Hani asks whether the constraint-based hardcoded grasping is acceptable for the final thesis.

> **Till:** *"Yeah, because that's not — we don't really care about that."*
> **Daniel:** *"We don't really care about that. Yeah, grasping is a different issue. Like you can make it nice if you have the time, but it's not the focus for now. As long as you do some somewhat reasonable motion plans and somewhat reasonable movements, it's fine. A lot of manipulation papers that don't care about the grasping part — more about general rearrangement — do not care about grasping."*
> **Hani:** *"That's a rearrangement [problem]."*
> **Daniel:** *"Okay."*

This confirms that **#59 (friction grasping) and #77 (object sizing) are Tier 4 deferrable**, explicitly supervisor-confirmed.

---

## 12. Summary and Next Steps from Supervisors (00:58:39)

> **Hani:** *"Basically what we want to do is rethink boxelisation, right?"*
> **Daniel:** *"Yeah."*
> **Till:** *"Some parts of it. I guess most of what you have is actually sound. It's just about the merging and splitting logic that maybe it's a bit different. And especially what do you do after actually performing an action. But the message here is also: you can kind of use most of the logic that you already have. Just need to think about which boxes to merge, which boxes to split."*

> **Daniel (earlier):** *"I think it might make more sense to focus on the things we discussed today. Because the other things — in a sense, things that you can always fix — but right now it's more about trying to figure out whether the idea works."*

---

## Action Items (from this meeting)

| # | Item | Audit Issue |
|---|------|-------------|
| 1 | Add size precondition to place action; prefer adjacent free boxel | **#102** |
| 2 | Implement logical property + observability equivalence check in merge | **#103** |
| 3 | Implement full re-boxelisation after every scene-changing action; preserve observation history | **#104** |
| 4 | Implement multi-variant place actions (place-in-1, place-in-2, etc.) with adjacency precondition and fitness certifier | **#105** |
| 5 | Decide whether mid-pick sensing (pick-observe-replace) is an intended capability | open |
| 6 | Fix constraint attachment: use actual EE-to-object transform at creation time | **#98 (DONE)** |

---

## Key Decisions Summary

| Decision | Detail |
|----------|--------|
| Push → pick-and-place | Target boxel is explicit action parameter; resolves hardcoded-destination problem |
| Merge condition | Merge only if: (a) same blocks-view-at set, (b) same observability (both visible or both in shadow), (c) convexity (existing, may revisit) |
| Merge order | Back-to-front (farthest from camera first) |
| Re-boxelisation strategy | Full re-boxelise after every scene-changing action (Phase 1); incremental optimisation is Phase 2 |
| Observation history | Must survive re-boxelisation; tracked across replans |
| Multi-boxel placement | Multi-variant place actions (place-in-1, place-in-2, …) rather than explicit multi-boxel reasoning |
| Architectural approach | Approach 1 (opaque Python re-boxelisation + replan) chosen; Approach 2 (PDDL-level merge/split) explicitly rejected for current scope |
| Grasping | Constraint-based grasping acceptable for thesis; not the focus |
| Active voxels | Explicitly rejected by supervisors; do not pursue |
