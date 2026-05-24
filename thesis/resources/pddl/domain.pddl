;; =============================================================================
;; Semantic Boxel TAMP Domain - PDDLStream Compatible (Untyped)
;; =============================================================================
;; 
;; Models the robot's CAPABILITIES (sense, move, pick, place, stack) rather
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
    (is_object ?b)           ; Physical object (can be picked, placed, stacked)
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
    (boxel_fits ?o ?b)            ; Boxel ?b is large enough to contain ?o (place dest or sense region)
    (on_surface ?b)               ; Boxel ?b rests on a support surface (table)
    
    ;; --- Stacking ---
    ;; (on ?o ?support) means ?o sits directly on top of ?support.
    ;; (on_table ?o) is the explicit "?o rests on the table" counterpart.
    ;; (clear ?o) means nothing is stacked on ?o.
    (on ?o1 ?o2)
    (on_table ?o)                 ; ?o sits directly on the table
    (clear ?o)
    (is_tray ?o)                  ; ?o is the fixed-base tray support
    (stack_kin ?o ?on_obj ?g ?q)  ; IK config ?q to place ?o on top of ?on_obj
  )

  ;; =========================================================================
  ;; ACTION COSTS: bias planner toward place over stack
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
  ;; Optimistic effect: assume the target is found.  If execution reveals
  ;; otherwise, the outer loop marks the shadow empty and replans, which
  ;; avoids contingent planning that PDDLStream and FastDownward do not
  ;; support.
  (:action sense
    :parameters (?o ?region)
    :precondition (and
      (Obj ?o)
      (Boxel ?region)
      (view_clear ?region)
      (boxel_fits ?o ?region)              ; ?o physically fits inside ?region
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
  ;; Must KNOW object is there (KIF=true AND at=true).
  (:action pick
    :parameters (?o ?b ?g ?q)
    :precondition (and
      (Obj ?o)
      (Boxel ?b)
      (Grasp ?g)
      (Config ?q)
      (handempty)
      (at_config ?q)
      (clear ?o)                      ; can't pick an object with something stacked on top
      (obj_at_boxel_KIF ?o ?b)        ; Must know
      (obj_at_boxel ?o ?b)            ; Must be there
      (kin_solution ?o ?b ?g ?q)
    )
    :effect (and
      (holding ?o)
      (not (handempty))
      (not (obj_at_boxel ?o ?b))
      (not (on_table ?o))         ; picking lifts ?o off the table
                                  ; (idempotent if ?o was on a stack instead)
      ;; If ?o was stacked on ?x, picking ?o makes ?x clear again.  For
      ;; holding-goal runs (no (on ...) facts) this grounds to a no-op.
      (forall (?x)
        (when (on ?o ?x)
          (and (not (on ?o ?x)) (clear ?x))))
      (increase (total-cost) 1)
    )
  )

  ;; =========================================================================
  ;; PLACE: Place an object in a boxel
  ;; =========================================================================
  ;; Destination must be free space.
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
      (on_table ?o)               ; place lands ?o on the table
      (not (holding ?o))
      (not (is_free_space ?b))
      (increase (total-cost) 1)
    )
  )

  ;; =========================================================================
  ;; STACK: Place the held object on top of another object
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
      (obj_at_boxel ?o ?o)        ; OBJECT boxel ID equals object name (a stacked object's boxel is itself)
      (obj_at_boxel_KIF ?o ?o)
      (not (holding ?o))
      (not (clear ?on_obj))
      (increase (total-cost) 2)
    )
  )
)
