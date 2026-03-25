#pragma once

#include "adapter_base.h"
#include "version_info.h"
#include "data_types/SystemStatus_t.h"

class Converter_SystemStatus_t : public AdapterConverterBase
{
  public:
    static const char* GetConverterTypeName() { return "SystemStatus_t"; }
    static AdapterConverterBase* Create() { return new Converter_SystemStatus_t(); }

    const char* GetTypeName() const override { return "SystemStatus_t"; }

    long ConvertData(
      uint32_t src_type_tag, unsigned long src_size,
      const IVersionInfo& src_version,
      uint32_t dst_type_tag, unsigned long dst_size,
      const IVersionInfo* dst_version,
      void* dst_data,
      void** out_data, unsigned long& out_size) override;

    long GetDefaultValue(
      uint32_t type_tag, unsigned long size,
      const IVersionInfo& version,
      void** default_data, unsigned long& default_size) override;

    bool AreVersionsCompatible(
      uint32_t src_type_tag, unsigned long src_size,
      const IVersionInfo& src_version,
      uint32_t dst_type_tag, unsigned long dst_size,
      const IVersionInfo& dst_version) override;

  private:
    void convert_V1_to_Generic(
      SystemStatus_t_V_Gen::SystemStatus_t& dest,
      const SystemStatus_t_V_1::SystemStatus_t& source);
    void convert_V2_to_Generic(
      SystemStatus_t_V_Gen::SystemStatus_t& dest,
      const SystemStatus_t_V_2::SystemStatus_t& source);
};
