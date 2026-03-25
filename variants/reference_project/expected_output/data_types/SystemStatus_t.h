#pragma once
#include "platform_types.h"

#ifdef SYSTEM_STATUS_VERSION
static_assert(SYSTEM_STATUS_VERSION != 9999,
  "Version 9999 is reserved as the generic adapter hub version");
#endif

namespace SystemStatus_t_V_1
{
  static const uint32_t VERSION = 1;

  typedef struct
  {
    uint32 uptime_seconds;
    uint8 cpu_load;
    uint8 memory_usage;
    uint8 error_count;
  } SystemStatus_t;
} // namespace SystemStatus_t_V_1

namespace SystemStatus_t_V_2
{
  static const uint32_t VERSION = 2;

  typedef struct
  {
    uint32 uptime_seconds;
    uint8 cpu_load;
    uint8 memory_usage;
    uint8 error_count;
    uint16 task_count;
    uint32 free_heap;
  } SystemStatus_t;
} // namespace SystemStatus_t_V_2

namespace SystemStatus_t_V_3
{
  static const uint32_t VERSION = 3;

  typedef struct
  {
    uint32 uptime_seconds;
    uint8 cpu_load;
    uint8 memory_usage;
    uint8 error_count;
    uint16 task_count;
    uint32 free_heap;
    uint32 boot_count;
  } SystemStatus_t;
} // namespace SystemStatus_t_V_3

namespace SystemStatus_t_V_Gen
{
  static const uint32_t VERSION = 9999;

  typedef struct
  {
    uint32 uptime_seconds;
    uint8 cpu_load;
    uint8 memory_usage;
    uint8 error_count;
    uint16 task_count;
    uint32 free_heap;
    uint32 boot_count;
  } SystemStatus_t;
} // namespace SystemStatus_t_V_Gen

