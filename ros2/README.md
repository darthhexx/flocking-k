# M13 ROS 2 integration

`flockkalman_msgs` is an `ament_cmake` interface package for the M13 wire
contract. Build it in a ROS 2 workspace with:

```bash
colcon build --packages-select flockkalman_msgs
```

Operational estimate, proposal, diagnostic, and command topics use reliable,
keep-last QoS with a bounded depth of 10. Camera observations may use
best-effort sensor-data QoS. The safety command topic is reliable and transient
local only for the latest stop state. The truth topic must run under a distinct
ROS domain ID, Unix account, and recorder process; no operational deployment
file may contain its domain ID.

Record every host's operational topics to MCAP and retain the packet capture:

```bash
ros2 bag record --storage mcap -a
```

Export those records through a site-specific bridge into the four hash-chained
JSONL ledgers defined by `M13_PROTOCOL.md`. The canonical evaluator never
accepts hand-written summary metrics. Transport fault commands such as `tc
netem` are generated from the preregistered manifest by the lab harness and
must be logged before application and after restoration. Never apply network
faults to the safety or independent-truth interfaces.

The six message definitions are intentionally data-only. Robot drivers,
camera calibration, MCAP export, and safety I/O are site-specific adapters and
must be qualified during M13.2 before their hashes are frozen.

