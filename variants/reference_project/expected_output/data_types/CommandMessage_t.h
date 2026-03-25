#pragma once
#include "platform_types.h"

#ifdef COMMAND_MSG_VERSION
static_assert(COMMAND_MSG_VERSION != 9999,
  "Version 9999 is reserved as the generic adapter hub version");
#endif

namespace CommandMessage_t_V_1
{
  static const uint32_t VERSION = 1;

  typedef struct
  {
    uint32 command_id;
    uint32 timestamp;
    uint8 priority;
    float32 params[4];
  } CommandMessage_t;
} // namespace CommandMessage_t_V_1

namespace CommandMessage_t_V_2
{
  static const uint32_t VERSION = 2;

  typedef struct
  {
    uint32 command_id;
    uint32 timestamp;
    uint8 priority;
    uint8 source_id;
    float32 params[4];
  } CommandMessage_t;
} // namespace CommandMessage_t_V_2

namespace CommandMessage_t_V_3
{
  static const uint32_t VERSION = 3;

  typedef struct
  {
    uint32 command_id;
    uint32 timestamp;
    uint8 priority;
    uint8 source_id;
    uint32 checksum;
    float32 params[8];
  } CommandMessage_t;
} // namespace CommandMessage_t_V_3

namespace CommandMessage_t_V_Gen
{
  static const uint32_t VERSION = 9999;

  typedef struct
  {
    uint32 command_id;
    uint32 timestamp;
    uint8 priority;
    float32 params[8];
    uint8 source_id;
    uint32 checksum;
  } CommandMessage_t;
} // namespace CommandMessage_t_V_Gen

