#pragma once

#include <cstdint>
#include <cstring>

class IVersionInfo {
public:
  virtual ~IVersionInfo() = default;
  virtual uint32_t GetVersion() const = 0;
};

class AdapterConverterBase {
public:
  virtual ~AdapterConverterBase() = default;
  virtual const char* GetTypeName() const = 0;
  virtual long ConvertData(
      uint32_t src_type_tag, unsigned long src_size,
      const IVersionInfo& src_version,
      uint32_t dst_type_tag, unsigned long dst_size,
      const IVersionInfo* dst_version,
      void* dst_data,
      void** out_data, unsigned long& out_size) = 0;
  virtual long GetDefaultValue(
      uint32_t type_tag, unsigned long size,
      const IVersionInfo& version,
      void** default_data, unsigned long& default_size) = 0;
  virtual bool AreVersionsCompatible(
      uint32_t src_type_tag, unsigned long src_size,
      const IVersionInfo& src_version,
      uint32_t dst_type_tag, unsigned long dst_size,
      const IVersionInfo& dst_version) = 0;
};
