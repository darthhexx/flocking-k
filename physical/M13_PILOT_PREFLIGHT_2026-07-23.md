# M13.2 physical pilot preflight

Date: 23 July 2026  
Status: **BLOCKED — EXTERNAL RIG NOT CONNECTED**

## Verified ready

- M13.1 decision is `M13.1-HIL-PILOT-READY`.
- The 320-run, four-arm randomized pilot schedule exists.
- The evidence template declares six operational MCAP recorders, an
  independent truth MCAP, and a packet capture.
- Canonical operational, transport, safety, and truth ledgers are defined.
- Bundle sealing, independent scoring, pilot power calculation, protocol
  freezing, and held-out exclusion are implemented.
- `tcpdump` is installed on this host.

## Missing from this host/workspace

- ROS 2 executable and environment;
- `colcon` build tooling;
- connected observer-robot or camera devices;
- target-robot controller;
- four observer ROS/DDS endpoints;
- planner and safety-supervisor endpoints;
- independent motion-capture or overhead-camera truth endpoint;
- MCAP, ROS bag, or packet-capture pilot evidence;
- real site, layout, path, lighting, and trial-date identifiers.

No physical trial was started, and no synthetic evidence was substituted.
Every row in `m13_pilot_plan/trial_schedule.csv` remains `planned`.

## Required handoff

Provide either:

1. access to the configured ROS 2 robot network and independent truth system,
   including endpoint/host names and the ROS setup script; or
2. completed raw pilot bundles containing the per-host MCAP files, independent
   truth MCAP, packet capture, and exported hash-chained ledgers.

Physical operation also requires an on-site operator able to engage the
hardware emergency stop. Once the rig is available, begin with one stable-arm
block as a commissioning run, audit and score it, then proceed through the
randomized schedule only if clock, recorder, truth-isolation, and safety checks
pass.
