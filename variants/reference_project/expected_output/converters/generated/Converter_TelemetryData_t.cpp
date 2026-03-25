#include "Converter_TelemetryData_t.h"
#include <cstring>

long Converter_TelemetryData_t::ConvertData(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo* dst_version,
  void* dst_data,
  void** out_data, unsigned long& out_size)
{
  uint32_t src_ver = src_version.GetVersion();
  TelemetryData_t_V_Gen::TelemetryData_t generic;

  // Forward: source version -> generic
  switch (src_ver)
  {
    case 1:
      convert_V1_to_Generic(generic, *reinterpret_cast<const TelemetryData_t_V_1::TelemetryData_t*>(dst_data));
      break;
    case 2:
      convert_V2_to_Generic(generic, *reinterpret_cast<const TelemetryData_t_V_2::TelemetryData_t*>(dst_data));
      break;
    case 3:
      convert_V3_to_Generic(generic, *reinterpret_cast<const TelemetryData_t_V_3::TelemetryData_t*>(dst_data));
      break;
    default:
      return -1;
  }

  // Output generic
  out_size = sizeof(TelemetryData_t_V_Gen::TelemetryData_t);
  *out_data = new TelemetryData_t_V_Gen::TelemetryData_t(generic);
  return 0;
}

long Converter_TelemetryData_t::GetDefaultValue(
  uint32_t type_tag, unsigned long size,
  const IVersionInfo& version,
  void** default_data, unsigned long& default_size)
{
  TelemetryData_t_V_Gen::TelemetryData_t def;
  memset(&def, 0, sizeof(def));
  default_size = sizeof(TelemetryData_t_V_Gen::TelemetryData_t);
  *default_data = new TelemetryData_t_V_Gen::TelemetryData_t(def);
  return 0;
}

bool Converter_TelemetryData_t::AreVersionsCompatible(
  uint32_t src_type_tag, unsigned long src_size,
  const IVersionInfo& src_version,
  uint32_t dst_type_tag, unsigned long dst_size,
  const IVersionInfo& dst_version)
{
  return src_version.GetVersion() == dst_version.GetVersion();
}

void Converter_TelemetryData_t::convert_V1_to_Generic(
  TelemetryData_t_V_Gen::TelemetryData_t& dest,
  const TelemetryData_t_V_1::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.ground_speed = source.speed;
  dest.altitude_msl = source.altitude;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.op_status = source.status;
  for (int i = 0; i < (32 < 64 ? 32 : 64); i++)
  {
    dest.payload[i] = source.payload[i];
  }
  dest.vertical_speed = 0.0;
  dest.signal_quality = 0;
  // Field 'battery' not in source, zero-initialized by memset
  dest.airspeed = 0.0;
  dest.satellite_count = 0;
  dest.mission_phase = 0;
  dest.sequence_number = 0;
}

void Converter_TelemetryData_t::convert_V2_to_Generic(
  TelemetryData_t_V_Gen::TelemetryData_t& dest,
  const TelemetryData_t_V_2::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.ground_speed = source.speed;
  dest.altitude_msl = source.altitude;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.op_status = source.status;
  for (int i = 0; i < 64; i++)
  {
    dest.payload[i] = source.payload[i];
  }
  dest.vertical_speed = source.vertical_speed;
  dest.signal_quality = source.signal_quality;
  memcpy(&dest.battery, &source.battery, sizeof(dest.battery));
  dest.airspeed = 0.0;
  dest.satellite_count = 0;
  dest.mission_phase = 0;
  dest.sequence_number = 0;
}

void Converter_TelemetryData_t::convert_V3_to_Generic(
  TelemetryData_t_V_Gen::TelemetryData_t& dest,
  const TelemetryData_t_V_3::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.ground_speed = source.ground_speed;
  dest.altitude_msl = source.altitude_msl;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.op_status = source.op_status;
  for (int i = 0; i < 64; i++)
  {
    dest.payload[i] = source.payload[i];
  }
  dest.vertical_speed = source.vertical_speed;
  dest.signal_quality = source.signal_quality;
  memcpy(&dest.battery, &source.battery, sizeof(dest.battery));
  dest.airspeed = source.airspeed;
  dest.satellite_count = source.satellite_count;
  dest.mission_phase = source.mission_phase;
  dest.sequence_number = source.sequence_number;
}

void Converter_TelemetryData_t::convert_Generic_to_V1(
  TelemetryData_t_V_1::TelemetryData_t& dest,
  const TelemetryData_t_V_Gen::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.speed = source.ground_speed;
  dest.altitude = source.altitude_msl;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.status = source.op_status;
  for (int i = 0; i < (64 < 32 ? 64 : 32); i++)
  {
    dest.payload[i] = source.payload[i];
  }
}

void Converter_TelemetryData_t::convert_Generic_to_V2(
  TelemetryData_t_V_2::TelemetryData_t& dest,
  const TelemetryData_t_V_Gen::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.speed = source.ground_speed;
  dest.altitude = source.altitude_msl;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.vertical_speed = source.vertical_speed;
  dest.status = source.op_status;
  dest.signal_quality = source.signal_quality;
  for (int i = 0; i < 64; i++)
  {
    dest.payload[i] = source.payload[i];
  }
  memcpy(&dest.battery, &source.battery, sizeof(dest.battery));
}

void Converter_TelemetryData_t::convert_Generic_to_V3(
  TelemetryData_t_V_3::TelemetryData_t& dest,
  const TelemetryData_t_V_Gen::TelemetryData_t& source)
{
  memset(&dest, 0, sizeof(dest));
  dest.timestamp = source.timestamp;
  dest.ground_speed = source.ground_speed;
  dest.altitude_msl = source.altitude_msl;
  dest.heading = source.heading;
  dest.latitude = source.latitude;
  dest.longitude = source.longitude;
  dest.vertical_speed = source.vertical_speed;
  dest.airspeed = source.airspeed;
  dest.op_status = source.op_status;
  dest.signal_quality = source.signal_quality;
  dest.satellite_count = source.satellite_count;
  dest.mission_phase = source.mission_phase;
  dest.sequence_number = source.sequence_number;
  for (int i = 0; i < 64; i++)
  {
    dest.payload[i] = source.payload[i];
  }
  memcpy(&dest.battery, &source.battery, sizeof(dest.battery));
}

