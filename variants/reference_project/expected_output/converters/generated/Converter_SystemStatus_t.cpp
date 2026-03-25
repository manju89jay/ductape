#include "Converter_SystemStatus_t.h"
#include <cstring>

long Converter_SystemStatus_t::ConvertData(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo* dst_version,
  void* dst_data,
  void** out_data, unsigned long& out_size)
{
  uint32_t src_ver = src_version.GetVersion();
  SystemStatus_t_V_Gen::SystemStatus_t generic;

  // Forward: source version -> generic
  switch (src_ver)
  {
    case 1:
      convert_V1_to_Generic(generic, *reinterpret_cast<const SystemStatus_t_V_1::SystemStatus_t*>(dst_data));
      break;
    case 2:
      convert_V2_to_Generic(generic, *reinterpret_cast<const SystemStatus_t_V_2::SystemStatus_t*>(dst_data));
      break;
    case 3:
      memcpy(&generic, dst_data, sizeof(generic));
      break;
    default:
      return -1;
  }

  // Output generic
  out_size = sizeof(SystemStatus_t_V_Gen::SystemStatus_t);
  *out_data = new SystemStatus_t_V_Gen::SystemStatus_t(generic);
  return 0;
}

long Converter_SystemStatus_t::GetDefaultValue(
  uint32_t type_tag, unsigned long size,
  const IVersionInfo& version,
  void** default_data, unsigned long& default_size)
{
  SystemStatus_t_V_Gen::SystemStatus_t def;
  memset(&def, 0, sizeof(def));
  default_size = sizeof(SystemStatus_t_V_Gen::SystemStatus_t);
  *default_data = new SystemStatus_t_V_Gen::SystemStatus_t(def);
  return 0;
}

bool Converter_SystemStatus_t::AreVersionsCompatible(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo& dst_version)
{
  return src_version.GetVersion() == dst_version.GetVersion();
}

void Converter_SystemStatus_t::convert_V1_to_Generic(
  SystemStatus_t_V_Gen::SystemStatus_t& dest,
  const SystemStatus_t_V_1::SystemStatus_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.uptime_seconds = source.uptime_seconds;
  dest.cpu_load = source.cpu_load;
  dest.memory_usage = source.memory_usage;
  dest.error_count = source.error_count;
  dest.task_count = 0;
  dest.free_heap = 0;
  dest.boot_count = 0;
}

void Converter_SystemStatus_t::convert_V2_to_Generic(
  SystemStatus_t_V_Gen::SystemStatus_t& dest,
  const SystemStatus_t_V_2::SystemStatus_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.uptime_seconds = source.uptime_seconds;
  dest.cpu_load = source.cpu_load;
  dest.memory_usage = source.memory_usage;
  dest.error_count = source.error_count;
  dest.task_count = source.task_count;
  dest.free_heap = source.free_heap;
  dest.boot_count = 0;
}

