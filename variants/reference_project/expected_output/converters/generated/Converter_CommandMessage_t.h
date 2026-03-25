#pragma once

#include "adapter_base.h"
#include "version_info.h"
#include "data_types/CommandMessage_t.h"

class Converter_CommandMessage_t : public AdapterConverterBase
{
  public:
    static const char* GetConverterTypeName() { return "CommandMessage_t"; }
    static AdapterConverterBase* Create() { return new Converter_CommandMessage_t(); }

    const char* GetTypeName() const override { return "CommandMessage_t"; }

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
      CommandMessage_t_V_Gen::CommandMessage_t& dest,
      const CommandMessage_t_V_1::CommandMessage_t& source);
    void convert_V2_to_Generic(
      CommandMessage_t_V_Gen::CommandMessage_t& dest,
      const CommandMessage_t_V_2::CommandMessage_t& source);
    void convert_V3_to_Generic(
      CommandMessage_t_V_Gen::CommandMessage_t& dest,
      const CommandMessage_t_V_3::CommandMessage_t& source);
};
