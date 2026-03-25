#ifndef TELEMETRY_TYPES_V2_H
#define TELEMETRY_TYPES_V2_H

#include "platform_types.h"

#define TELEMETRY_DATA_VERSION 2
#define COMMAND_MSG_VERSION 2
#define SYSTEM_STATUS_VERSION 2

#define MAX_PAYLOAD_SIZE 64
#define MAX_CMD_PARAMS 4

typedef struct {
  float32 voltage;
  float32 current;
  uint8 charge_percent;
} BatteryInfo_t;

typedef struct {
  uint32 timestamp;
  float32 speed;
  float32 altitude;
  float32 heading;
  float32 latitude;
  float32 longitude;
  float32 vertical_speed;
  uint8 status;
  uint8 signal_quality;
  uint8 payload[MAX_PAYLOAD_SIZE];
  BatteryInfo_t battery;
} TelemetryData_t;

typedef struct {
  uint32 command_id;
  uint32 timestamp;
  uint8 priority;
  uint8 source_id;
  float32 params[MAX_CMD_PARAMS];
} CommandMessage_t;

typedef struct {
  uint32 uptime_seconds;
  uint8 cpu_load;
  uint8 memory_usage;
  uint8 error_count;
  uint16 task_count;
  uint32 free_heap;
} SystemStatus_t;

#endif /* TELEMETRY_TYPES_V2_H */
