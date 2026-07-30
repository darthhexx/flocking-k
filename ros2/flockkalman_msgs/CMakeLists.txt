cmake_minimum_required(VERSION 3.8)
project(flockkalman_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/EstimateEnvelope.msg"
  "msg/PlannerProposal.msg"
  "msg/TrustDiagnostic.msg"
  "msg/VelocityCommand.msg"
  "msg/SafetyEvent.msg"
  "msg/TruthSample.msg"
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
