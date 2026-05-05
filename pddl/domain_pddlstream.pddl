;; =============================================================================
;; Semantic Boxel TAMP Domain - PDDLStream Compatible (Untyped)
;; =============================================================================
;; 
;; Models the robot's CAPABILITIES (push, sense, move, pick, place) rather
;; than any specific scenario. Scenario-specific spatial relationships
;; (e.g., which objects block which regions) are expressed as problem-level
;; init facts using generic predicates like blocks_view_at.
;;
;; Uses derived predicates for visibility: blocks_view and view_clear are
;; computed automatically from object positions — actions only need to
;; update spatial state (obj_at_boxel), not view predicates.
;;
;; Uses Know-If fluents for partial observability.
;; Object types are encoded as predicates: (Boxel ?x), (Obj ?x), etc.

(define (domain boxel-tamp)
  (:requirements :strips :equality :derived-predicates :conditional-effects :action-costs)
  
  (:predicates
    ;; --- Type predicates ---
    (Boxel ?x)
    (Obj ?x)
    (Config ?x)
    (Trajectory ?x)
    (Grasp ?x)
    
    ;; --- Boxel classification ---
    (is_shadow ?b)           ; Region not directly visible from the camera
    (is_object ?b)           ; Physical object (can be pushed, picked)
    (is_free_space ?b)       ; Known empty space
    
    ;; --- Visibility geometry (static) ---
    (blocks_view_at ?obj ?b ?region) ; When ?obj is at ?b, it blocks view to ?region
    
    ;; --- Visibility state (derived — DO NOT use in action effects) ---
    (blocks_view ?obj ?region) ; ?obj currently blocks view to ?region
    (view_blocked ?region)     ; Some object blocks view to ?region
    (view_clear ?region)       ; No object blocks view to ?region
    
    ;; --- Ground truth (actual world state) ---
    (obj_at_boxel ?o ?b)     ; Object ?o is physically at boxel ?b
    
    ;; --- Know-If fluent (do we know the value?) ---
    (obj_at_boxel_KIF ?o ?b) ; We know whether ?o is at ?b (true or false)
    
    ;; --- Robot state ---
    (at_config ?q)
    (handempty)
    (holding ?o)
    (obj_pose_known ?o)
    
    ;; --- Stream certified facts ---
    (valid_grasp ?o ?g)           ; Grasp ?g valid for object ?o
    (motion ?q1 ?q2 ?t)           ; Trajectory ?t from ?q1 to ?q2
    (kin_solution ?o ?b ?g ?q)    ; Config ?q for picking ?o from ?b with ?g
    (config_for_boxel ?q ?b)      ; Config ?q targets boxel ?b (EE inside ?b)
    (boxel_fits ?o ?b)            ; Free boxel ?b is large enough to contain ?o
    (on_surface ?b)               ; Boxel ?b rests on a support surface (table)
    
    ;; --- Stacking (audit #30, --goal stack) ---
    ;; (on ?o ?support) means ?o sits directly on top of ?support.
    ;; "On the table" is implicit — an object that appears in no
    ;; (on ?o ?x) fact is treated as table-resting.  This keeps the
    ;; predicate space minimal while still expressing stack goals.
    ;;
    ;; (clear ?o) means nothing is stacked on ?o.  Only emitted into
    ;; init when stackable_objects is supplied (i.e. the run is using
    ;; --goal stack); holding-goal runs never see these facts and pay
    ;; no grounding cost (audit #30 implementation note).
    (on ?o1 ?o2)
    (clear ?o)
    (stack_kin ?o ?on_obj ?g ?q)  ; IK config ?q to place ?o on top of ?on_obj
  )

  ;; =========================================================================
  ;; ACTION COSTS: bias planner toward place over stack (audit follow-up)
  ;; =========================================================================
  ;; All actions cost 1 except stack (cost 2).  Without this, the planner
  ;; treated stack and place as equally cheap and chose stack as a "rescue"
  ;; whenever motion planning to a particular free boxel failed, instead of
  ;; trying other free boxels.  Higher stack cost forces the search to
  ;; exhaust place destinations before falling back to stack.
  (:functions (total-cost))

  ;; =========================================================================
  ;; DERIVED PREDICATES: Visibility from object positions
  ;; =========================================================================
  ;; blocks_view_at is a static geometric fact in the init state.
  ;; blocks_view is derived: true when an object is currently at a position
  ;; that geometrically blocks a view corridor.
  ;; view_clear is derived via stratified negation: true when no object
  ;; blocks the view.
  
  (:derived (blocks_view ?obj ?region)
    (exists (?b)
      (and (obj_at_boxel ?obj ?b)
           (blocks_view_at ?obj ?b ?region))))
  
  (:derived (view_blocked ?region)
    (exists (?obj)
      (blocks_view ?obj ?region)))
  
  (:derived (view_clear ?region)
    (and (Boxel ?region)
         (is_shadow ?region)
         (not (view_blocked ?region))))
  
  ;; =========================================================================
  ;; SENSE: Observe a region to check for an object
  ;; =========================================================================
  ;; Requires clear line of sight to the region.
  ;; Uses the fixed scene camera — no robot positioning needed.
  ;;
  ;; DESIGN DECISION — Optimistic sensing with reactive replanning (#61):
  ;;
  ;; The proposal (Section 4.4.2) defines sense with conditional effects:
  ;;   stream_get_sensing_outcome returns found/not_found, and (when ...)
  ;;   clauses set obj_in_Boxel or obj_not_in_Boxel accordingly.  This
  ;;   would let the planner generate multi-step search plans ("sense A;
  ;;   if empty, sense B") within a single plan.
  ;;
  ;; This implementation uses optimistic single-outcome sensing instead:
  ;;   the effect unconditionally assumes the target is found.  When
  ;;   execution reveals it is NOT there, the Python execution loop
  ;;   breaks out, updates the belief state (marks shadow as empty),
  ;;   and replans with updated knowledge.
  ;;
  ;; Justification for this deviation:
  ;;   (a) PDDLStream + FastDownward do not support contingent planning.
  ;;       Conditional effects in PDDL require deterministic outcomes;
  ;;       branching on observation results requires a contingent planner
  ;;       (e.g. POND, CLG), which is outside PDDLStream's architecture.
  ;;   (b) Optimistic planning with replanning on failure is a standard
  ;;       pattern in TAMP under partial observability (Garrett et al.,
  ;;       2020; Kaelbling & Lozano-Pérez, 2013).  PDDLStream's own
  ;;       adaptive algorithm is built around optimistic assumptions.
  ;;   (c) For tabletop scenarios with N shadows, the reactive approach
  ;;       converges in at most N replan cycles (one per empty shadow).
  ;;       The execution loop bounds this: max_replans = 4*N + 1.
  ;;   (d) Belief state propagates correctly across replans: known_empty
  ;;       shadows carry over, so each replan searches strictly fewer
  ;;       candidates.  This is functionally equivalent to the proposal's
  ;;       conditional plan, executed sequentially.
  ;;
  ;; Limitation: the planner cannot reason about search ORDER — it picks
  ;; whichever shadow FastDownward expands first.  A conditional planner
  ;; could optimize search order (e.g. most-likely-first).  For the
  ;; current uniform-prior scenario this does not affect completeness.
  ;;
  ;; See CODEBASE_AUDIT #61, PA-5, PF-1.
  (:action sense
    :parameters (?o ?region)
    :precondition (and
      (Obj ?o)
      (Boxel ?region)
      (view_clear ?region)
      (not (obj_at_boxel_KIF ?o ?region))  ; Only sense if unknown
    )
    :effect (and
      (obj_at_boxel_KIF ?o ?region)        ; Now we know
      (obj_at_boxel ?o ?region)            ; OPTIMISTIC: assume found
      (obj_pose_known ?o)
      (increase (total-cost) 1)
    )
  )
  
  ;; =========================================================================
  ;; MOVE: Move robot from one configuration to another
  ;; =========================================================================
  ;; ?b is the destination boxel — the stream that produced ?q2 certifies
  ;; that the end-effector at ?q2 is within boxel ?b.
  (:action move
    :parameters (?q1 ?q2 ?b ?t)
    :precondition (and
      (Config ?q1)
      (Config ?q2)
      (Boxel ?b)
      (Trajectory ?t)
      (at_config ?q1)
      (config_for_boxel ?q2 ?b)
      (motion ?q1 ?q2 ?t)
    )
    :effect (and
      (at_config ?q2)
      (not (at_config ?q1))
      (increase (total-cost) 1)
    )
  )
  
  ;; =========================================================================
  ;; PICK: Pick up an object from a boxel
  ;; =========================================================================
  ;; Must KNOW object is there (KIF=true AND at=true)
  ;;
  ;; TODO (CODEBASE_AUDIT #1): pick should update at_config in its effects.
  ;; move delivers the arm to ?q (compute-kin config, 10 cm above object).
  ;; pick then lowers to contact, grabs, and at_config should change to
  ;; the lowered config.  The next move's plan_motion lifts naturally.
  (:action pick
    :parameters (?o ?b ?g ?q)
    :precondition (and
      (Obj ?o)
      (Boxel ?b)
      (Grasp ?g)
      (Config ?q)
      (handempty)
      (at_config ?q)
      (clear ?o)                      ; audit #39 — can't pick an object with something stacked on top
      (obj_at_boxel_KIF ?o ?b)        ; Must know
      (obj_at_boxel ?o ?b)            ; Must be there
      (kin_solution ?o ?b ?g ?q)
    )
    :effect (and
      (holding ?o)
      (not (handempty))
      (not (obj_at_boxel ?o ?b))
      ;; Stacking bookkeeping (audit #30): if ?o was sitting on some
      ;; ?x, picking it off makes ?x clear again.  The forall ranges
      ;; over (Obj ?x) but only fires when the (on ?o ?x) fluent is
      ;; true, so for holding-goal runs (which never assert (on ...))
      ;; it grounds to a no-op.
      (forall (?x)
        (when (on ?o ?x)
          (and (not (on ?o ?x)) (clear ?x))))
      (increase (total-cost) 1)
    )
  )
  
  ;; =========================================================================
  ;; PLACE: Place an object in a boxel
  ;; =========================================================================
  ;; Destination must be free space
  ;;
  ;; TODO (CODEBASE_AUDIT #1): mirror of pick — move delivers the arm to
  ;; the compute-kin config (10 cm above destination), place lowers to
  ;; release height, drops the object, and at_config should change to
  ;; the lowered config.
  (:action place
    :parameters (?o ?b ?g ?q)
    :precondition (and
      (Obj ?o)
      (Boxel ?b)
      (Grasp ?g)
      (Config ?q)
      (holding ?o)
      (at_config ?q)
      (is_free_space ?b)
      (on_surface ?b)
      (boxel_fits ?o ?b)
      (kin_solution ?o ?b ?g ?q)
    )
    :effect (and
      (handempty)
      (obj_at_boxel ?o ?b)
      (obj_at_boxel_KIF ?o ?b)
      (not (holding ?o))
      (not (is_free_space ?b))
      (increase (total-cost) 1)
    )
  )

  ;; =========================================================================
  ;; STACK: Place the held object on top of another object  (audit #30)
  ;; =========================================================================
  ;; Mirrors place but the destination is an OBJECT boxel rather than a
  ;; FREE_SPACE boxel.  ``stack_kin`` is certified by compute-stack-kin,
  ;; which derives the EE target from ?on_obj's CURRENT top z + the held
  ;; object's half-height; this is computed each time the planner is
  ;; invoked so multi-step stacks tolerate per-step settling.
  ;;
  ;; (clear ?o) becomes true on the newly-stacked object so it is itself
  ;; available as a support for a subsequent stack action.
  (:action stack
    :parameters (?o ?on_obj ?g ?q)
    :precondition (and
      (Obj ?o)
      (Obj ?on_obj)
      (Grasp ?g)
      (Config ?q)
      (holding ?o)
      (at_config ?q)
      (clear ?on_obj)
      (stack_kin ?o ?on_obj ?g ?q)
    )
    :effect (and
      (handempty)
      (on ?o ?on_obj)
      (clear ?o)
      (obj_at_boxel ?o ?o)        ; OBJECT boxel ID equals object name
      (obj_at_boxel_KIF ?o ?o)
      (not (holding ?o))
      (not (clear ?on_obj))
      (increase (total-cost) 2)
    )
  )
)
