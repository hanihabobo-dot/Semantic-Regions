;; =============================================================================
;; Semantic Boxel TAMP Domain - FIND_DICE STREAMFUL (Untyped)
;; =============================================================================
;;
;; audit #120: run OUR planner -- as we wrote it -- on TAMPURA's find_dice env.
;; This is domain_pddlstream.pddl's STREAMFUL pick/place/move/stack (every
;; manipulation grounds through the geometric streams: sample-grasp ->
;; compute-kin -> plan-motion), with the find_dice-specific additions kept from
;; domain_find_dice.pddl:
;;   * SENSE is empty-handed (handempty): the occluding cup must be RELOCATED
;;     (placed aside), not merely lifted, before the fixed external camera's view
;;     of the region is genuinely cleared.
;;   * GO-HOME + (at_home): the find_dice goal is (and (holding die) (at_home));
;;     pick/place clear (at_home) so the planner schedules go-home last.
;;
;; The ONLY difference from domain_pddlstream.pddl's pick/place is the extra
;; (not (at_home)) effect (so go-home lands last) and the find_dice sense/go-home
;; actions; the streamful preconditions (Grasp/Config/at_config/kin_solution/
;; boxel_fits) are IDENTICAL to our shared domain.  No relaxation.

(define (domain boxel-tamp-find-dice-streamful)
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
    (at_home)                     ; arm is at the home config (find_dice reward atom)
    (handempty)
    (holding ?o)
    (obj_pose_known ?o)

    ;; --- Stream certified facts ---
    (valid_grasp ?o ?g)           ; Grasp ?g valid for object ?o
    (motion ?q1 ?q2 ?t)           ; Trajectory ?t from ?q1 to ?q2
    (kin_solution ?o ?b ?g ?q)    ; Config ?q for picking ?o from ?b with ?g
    (config_for_boxel ?q ?b)      ; Config ?q targets boxel ?b (EE inside ?b)
    (boxel_fits ?o ?b)            ; Boxel ?b is large enough to contain ?o (place dest or sense region; audit #62)
    (on_surface ?b)               ; Boxel ?b rests on a support surface (table)

    ;; --- Stacking (audit #30, #41) ---
    (on ?o1 ?o2)
    (on_table ?o)                 ; ?o sits directly on the table  (audit #41)
    (clear ?o)
    (is_tray ?o)                  ; ?o is the fixed-base tray support  (audit #49)
    (stack_kin ?o ?on_obj ?g ?q)  ; IK config ?q to place ?o on top of ?on_obj
  )

  (:functions (total-cost))

  ;; =========================================================================
  ;; DERIVED PREDICATES: Visibility from object positions (unchanged)
  ;; =========================================================================
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
  ;; SENSE: empty-handed observation of a region (find_dice variant)
  ;; =========================================================================
  ;; Optimistic single-outcome sensing with reactive replanning (#61): the
  ;; effect assumes the target is found; the execution loop re-segments and, if
  ;; the target is NOT revealed, marks the region empty and replans.  Empty-
  ;; handed because the occluding cup must be placed aside (not just lifted) for
  ;; the fixed external camera's view of the region to be genuinely cleared.
  (:action sense
    :parameters (?o ?region)
    :precondition (and
      (Obj ?o)
      (Boxel ?region)
      (handempty)
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
  ;; MOVE: collision-free trajectory between configs (streamful; unchanged)
  ;; =========================================================================
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
  ;; PICK: streamful (== domain_pddlstream.pddl pick) + find_dice (not at_home)
  ;; =========================================================================
  (:action pick
    :parameters (?o ?b ?g ?q)
    :precondition (and
      (Obj ?o)
      (Boxel ?b)
      (Grasp ?g)
      (Config ?q)
      (handempty)
      (at_config ?q)
      (clear ?o)
      (obj_at_boxel_KIF ?o ?b)
      (obj_at_boxel ?o ?b)
      (kin_solution ?o ?b ?g ?q)
    )
    :effect (and
      (holding ?o)
      (not (handempty))
      (not (obj_at_boxel ?o ?b))
      (not (on_table ?o))
      (forall (?x)
        (when (on ?o ?x)
          (and (not (on ?o ?x)) (clear ?x))))
      (not (at_home))
      (increase (total-cost) 1)
    )
  )

  ;; =========================================================================
  ;; PLACE: streamful (== domain_pddlstream.pddl place) + find_dice (not at_home)
  ;; =========================================================================
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
      (on_table ?o)
      (not (holding ?o))
      (not (is_free_space ?b))
      (not (at_home))
      (increase (total-cost) 1)
    )
  )

  ;; =========================================================================
  ;; STACK: streamful (== domain_pddlstream.pddl stack) -- kept for parity
  ;; =========================================================================
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
      (obj_at_boxel ?o ?o)
      (obj_at_boxel_KIF ?o ?o)
      (not (holding ?o))
      (not (clear ?on_obj))
      (not (at_home))
      (increase (total-cost) 2)
    )
  )

  ;; =========================================================================
  ;; GO-HOME: return the arm to the home config (find_dice)
  ;; =========================================================================
  ;; Legal only while holding something; restores (at_home).  pick/place clear
  ;; (at_home), so the planner places go-home as the final step.
  (:action go_home
    :parameters (?o)
    :precondition (and
      (Obj ?o)
      (holding ?o)
      (not (at_home))
    )
    :effect (and
      (at_home)
      (increase (total-cost) 1)
    )
  )
)
