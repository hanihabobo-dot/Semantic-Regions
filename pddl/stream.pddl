(define (stream boxel-streams)
  
  ;; Sample grasp poses for an object  
  (:stream sample-grasp
    :inputs (?o)
    :domain (Obj ?o)
    :outputs (?g)
    :certified (and (Grasp ?g) (valid_grasp ?o ?g))
  )
  
  ;; Plan motion between configurations
  (:stream plan-motion
    :inputs (?q1 ?q2)
    :domain (and (Config ?q1) (Config ?q2))
    :outputs (?t)
    :certified (and (Trajectory ?t) (motion ?q1 ?q2 ?t))
  )
  
  ;; boxel_fits is NOT a stream — facts are precomputed in init (pddlstream_planner
  ;; _build_init).  A test stream here made adaptive search re-evaluate every
  ;; (object, free_boxel) pair across skeletons/refinements and dominated runtime.
  
  ;; Compute IK solution for picking
  (:stream compute-kin
    :inputs (?o ?b ?g)
    :domain (and (Obj ?o) (Boxel ?b) (valid_grasp ?o ?g))
    :outputs (?q)
    :certified (and (Config ?q) (kin_solution ?o ?b ?g ?q) (config_for_boxel ?q ?b))
  )

  ;; Compute IK for stacking ?o on top of ?on_obj  (audit #30)
  ;; Reads ?on_obj's CURRENT AABB top + held object half-height to derive
  ;; the EE target.  Certifies config_for_boxel against ?on_obj so the
  ;; preceding move action delivers the arm to the support's OBJECT boxel.
  (:stream compute-stack-kin
    :inputs (?o ?on_obj ?g)
    :domain (and (Obj ?o) (Obj ?on_obj) (valid_grasp ?o ?g))
    :outputs (?q)
    :certified (and (Config ?q) (stack_kin ?o ?on_obj ?g ?q) (config_for_boxel ?q ?on_obj))
  )
)
