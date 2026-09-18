// Goal: promote only a verified, healthy release. A new evidence_round event
// causes reconsideration whenever workflow or telemetry beliefs may have changed.
+evidence_round(_)
    <- !decide_promotion.

+!decide_promotion
    : workflow_state(failed)
    <- .print("BDI_GATE_RESULT=block");
       .stopMAS(0,1).

+!decide_promotion
    : telemetry_state(block)
    <- .print("BDI_GATE_RESULT=block");
       .stopMAS(0,1).

+!decide_promotion
    : promotion_goal(Target)
      & workflow_state(passed)
      & telemetry_state(allow)
    <- .print("BDI_GATE_TARGET=", Target);
       .print("BDI_GATE_RESULT=allow");
       .stopMAS(0,0).

+!decide_promotion
    <- .print("BDI_GATE_WAIT=insufficient_evidence").
