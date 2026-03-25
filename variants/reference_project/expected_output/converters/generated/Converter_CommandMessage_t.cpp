#include "Converter_CommandMessage_t.h"
#include <cstring>

long Converter_CommandMessage_t::ConvertData(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo* dst_version,
  void* dst_data,
  void** out_data, unsigned long& out_size)
{
  uint32_t src_ver = src_version.GetVersion();
  CommandMessage_t_V_Gen::CommandMessage_t generic;

  // Forward: source version -> generic
  switch (src_ver)
  {
    case 1:
      convert_V1_to_Generic(generic, *reinterpret_cast<const CommandMessage_t_V_1::CommandMessage_t*>(dst_data));
      break;
    case 2:
      convert_V2_to_Generic(generic, *reinterpret_cast<const CommandMessage_t_V_2::CommandMessage_t*>(dst_data));
      break;
    case 3:
      convert_V3_to_Generic(generic, *reinterpret_cast<const CommandMessage_t_V_3::CommandMessage_t*>(dst_data));
      break;
    default:
      return -1;
  }

  // Output generic
  out_size = sizeof(CommandMessage_t_V_Gen::CommandMessage_t);
  *out_data = new CommandMessage_t_V_Gen::CommandMessage_t(generic);
  return 0;
}

long Converter_CommandMessage_t::GetDefaultValue(
  uint32_t type_tag, unsigned long size,
  const IVersionInfo& version,
  void** default_data, unsigned long& default_size)
{
  CommandMessage_t_V_Gen::CommandMessage_t def;
  memset(&def, 0, sizeof(def));
  default_size = sizeof(CommandMessage_t_V_Gen::CommandMessage_t);
  *default_data = new CommandMessage_t_V_Gen::CommandMessage_t(def);
  return 0;
}

bool Converter_CommandMessage_t::AreVersionsCompatible(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo& dst_version)
{
  return src_version.GetVersion() == dst_version.GetVersion();
}

void Converter_CommandMessage_t::convert_V1_to_Generic(
  CommandMessage_t_V_Gen::CommandMessage_t& dest,
  const CommandMessage_t_V_1::CommandMessage_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.command_id = source.command_id;
  dest.timestamp = source.timestamp;
  dest.priority = source.priority;
  for (int i = 0; i < (4 < 8 ? 4 : 8); i++)
  {
    dest.params[i] = source.params[i];
  }
  dest.source_id = 0;
  dest.checksum = 0;
}

void Converter_CommandMessage_t::convert_V2_to_Generic(
  CommandMessage_t_V_Gen::CommandMessage_t& dest,
  const CommandMessage_t_V_2::CommandMessage_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.command_id = source.command_id;
  dest.timestamp = source.timestamp;
  dest.priority = source.priority;
  for (int i = 0; i < (4 < 8 ? 4 : 8); i++)
  {
    dest.params[i] = source.params[i];
  }
  dest.source_id = source.source_id;
  dest.checksum = 0;
}

void Converter_CommandMessage_t::convert_V3_to_Generic(
  CommandMessage_t_V_Gen::CommandMessage_t& dest,
  const CommandMessage_t_V_3::CommandMessage_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.command_id = source.command_id;
  dest.timestamp = source.timestamp;
  dest.priority = source.priority;
  for (int i = 0; i < 8; i++)
  {
    dest.params[i] = source.params[i];
  }
  dest.source_id = source.source_id;
  dest.checksum = source.checksum;
}

