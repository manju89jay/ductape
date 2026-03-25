#ifndef TELEMETRY_TYPES_V3_H
#define TELEMETRY_TYPES_V3_H

#include "platform_types.h"

#define TELEMETRY_DATA_VERSION 3
#define COMMAND_MSG_VERSION 3
#define SYSTEM_STATUS_VERSION 3

#define MAX_PAYLOAD_SIZE 64
#define MAX_CMD_PARAMS 8

typedef struct {
  float32 voltage;
  float32 current;
  uint8 charge_percent;
} BatteryInfo_t;

typedef struct {
  uint32 timestamp;
  float32 ground_speed;
  float32 altitude_msl;
  float32 heading;
  float32 latitude;
  float32 longitude;
  float32 vertical_speed;
  float32 airspeed;
  uint8 op_status;
  uint8 signal_quality;
  uint8 satellite_count;
  uint8 mission_phase;
  uint32 sequence_number;
  uint8 payload[MAX_PAYLOAD_SIZE];
  BatteryInfo_t battery;
} TelemetryData_t;

typedef struct {
  uint32 command_id;
  uint32 timestamp;
  uint8 priority;
  uint8 source_id;
  uint32 checksum;
  float32 params[MAX_CMD_PARAMS];
} CommandMessage_t;

typedef struct {
  uint32 uptime_seconds;
  uint8 cpu_load;
  uint8 memory_usage;
  uint8 error_count;
  uint16 task_count;
  uint32 free_heap;
  uint32 boot_count;
} SystemStatus_t;

#endif /* TELEMETRY_TYPES_V3_H */
