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

  ;; Compute IK for stacking ?o on top of ?on_obj  (audit #30; pose-aware
  ;; refactor in audit #55).  Reads the support's SYMBOLIC pose ?p_on
  ;; (flowing from (at_pose ?on_obj ?p_on)), derives the EE target from
  ;; ?p_on.top_z + held cube half-height, and mints ?p_new for the cube's
  ;; resulting pose (consumed by subsequent stacks via the stack action's
  ;; at_pose effect).  Certifies config_for_boxel against ?on_obj so the
  ;; preceding move action delivers the arm to the support's OBJECT boxel.
  (:stream compute-stack-kin
    :inputs (?o ?on_obj ?p_on ?g)
    :domain (and (Obj ?o) (Obj ?on_obj) (Pose ?p_on) (valid_grasp ?o ?g))
    :outputs (?p_new ?q)
    :certified (and (Pose ?p_new) (Config ?q)
                    (stack_kin ?o ?on_obj ?p_on ?p_new ?g ?q)
                    (config_for_boxel ?q ?on_obj))
  )
)
