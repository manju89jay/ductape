#pragma once

#include "adapter_base.h"

class SimpleVersionInfo : public IVersionInfo {
public:
  explicit SimpleVersionInfo(uint32_t version) : version_(version) {}
  uint32_t GetVersion() const override { return version_; }
private:
  uint32_t version_;
};
