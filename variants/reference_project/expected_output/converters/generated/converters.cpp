#include <vector>
#include <string>
#include <functional>
#include "Converter_CommandMessage_t.h"
#include "Converter_SystemStatus_t.h"
#include "Converter_TelemetryData_t.h"

struct ConverterRegistration
{
  std::string type_name;
  std::function<AdapterConverterBase*()> factory;
};

std::vector<ConverterRegistration> GetGeneratedAdapters()
{
  return {
    { Converter_CommandMessage_t::GetConverterTypeName(),
      Converter_CommandMessage_t::Create },
    { Converter_SystemStatus_t::GetConverterTypeName(),
      Converter_SystemStatus_t::Create },
    { Converter_TelemetryData_t::GetConverterTypeName(),
      Converter_TelemetryData_t::Create }
  };
}
