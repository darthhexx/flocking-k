# M13.1 independent HIL screening

Verdict: **M13.1-HIL-PILOT-READY**

The suite ran 6000 trials across 10 scenarios, 150 paired seeds, and 4 arms.

This verdict only controls entry to the physical pilot. It cannot validate physical performance and never authorizes deployment.

## Gates

- PASS — `truth_isolation_and_replay`
- PASS — `zero_collisions_and_emergency_stops`
- PASS — `safety_intervention_rate_below_1pct`
- PASS — `ownership_and_message_bounds`
- PASS — `decentralized_integrated_loss_lcb`
- PASS — `attack_decision_loss`
- PASS — `wrong_action_rate`
- PASS — `calibration`
- PASS — `attack_alert_rate`
- PASS — `false_alert_rate`
- PASS — `attack_recovery`
- PASS — `transport_topology_runtime`
