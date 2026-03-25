#pragma once
#include "platform_types.h"

#ifdef TELEMETRY_DATA_VERSION
static_assert(TELEMETRY_DATA_VERSION != 9999,
  "Version 9999 is reserved as the generic adapter hub version");
#endif

namespace TelemetryData_t_V_1
{
  static const uint32_t VERSION = 1;

  typedef struct
  {
    uint32 timestamp;
    float32 speed;
    float32 altitude;
    float32 heading;
    float32 latitude;
    float32 longitude;
    uint8 status;
    uint8 payload[32];
  } TelemetryData_t;
} // namespace TelemetryData_t_V_1

namespace TelemetryData_t_V_2
{
  static const uint32_t VERSION = 2;

  typedef struct
  {
    float32 voltage;
    float32 current;
    uint8 charge_percent;
  } BatteryInfo_t;

  typedef struct
  {
    uint32 timestamp;
    float32 speed;
    float32 altitude;
    float32 heading;
    float32 latitude;
    float32 longitude;
    float32 vertical_speed;
    uint8 status;
    uint8 signal_quality;
    uint8 payload[64];
    BatteryInfo_t battery;
  } TelemetryData_t;
} // namespace TelemetryData_t_V_2

namespace TelemetryData_t_V_3
{
  static const uint32_t VERSION = 3;

  typedef struct
  {
    float32 voltage;
    float32 current;
    uint8 charge_percent;
  } BatteryInfo_t;

  typedef struct
  {
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
    uint8 payload[64];
    BatteryInfo_t battery;
  } TelemetryData_t;
} // namespace TelemetryData_t_V_3

namespace TelemetryData_t_V_Gen
{
  static const uint32_t VERSION = 9999;

  typedef struct
  {
    float32 voltage;
    float32 current;
    uint8 charge_percent;
  } BatteryInfo_t;

  typedef struct
  {
    uint32 timestamp;
    float32 ground_speed;
    float32 altitude_msl;
    float32 heading;
    float32 latitude;
    float32 longitude;
    uint8 op_status;
    uint8 payload[64];
    float32 vertical_speed;
    uint8 signal_quality;
    BatteryInfo_t battery;
    float32 airspeed;
    uint8 satellite_count;
    uint8 mission_phase;
    uint32 sequence_number;
  } TelemetryData_t;
} // namespace TelemetryData_t_V_Gen

