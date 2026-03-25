#ifndef TELEMETRY_TYPES_V1_H
#define TELEMETRY_TYPES_V1_H

#include "platform_types.h"

#define TELEMETRY_DATA_VERSION 1
#define COMMAND_MSG_VERSION 1
#define SYSTEM_STATUS_VERSION 1

#define MAX_PAYLOAD_SIZE 32
#define MAX_CMD_PARAMS 4

typedef struct {
  uint32 timestamp;
  float32 speed;
  float32 altitude;
  float32 heading;
  float32 latitude;
  float32 longitude;
  uint8 status;
  uint8 payload[MAX_PAYLOAD_SIZE];
} TelemetryData_t;

typedef struct {
  uint32 command_id;
  uint32 timestamp;
  uint8 priority;
  float32 params[MAX_CMD_PARAMS];
} CommandMessage_t;

typedef struct {
  uint32 uptime_seconds;
  uint8 cpu_load;
  uint8 memory_usage;
  uint8 error_count;
} SystemStatus_t;

#endif /* TELEMETRY_TYPES_V1_H */
