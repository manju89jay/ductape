#pragma once
#include <cstdint>
#include <vector>
#include <algorithm>

namespace ductape
{

  /* Version info for CommandMessage_t */
  inline std::vector<uint32_t> CommandMessage_t_GetSupportedVersions()
  {
    return { 1, 2, 3 };
  }

  inline uint32_t CommandMessage_t_GetLatestVersion()
  {
    return 3;
  }

  /* Version info for SystemStatus_t */
  inline std::vector<uint32_t> SystemStatus_t_GetSupportedVersions()
  {
    return { 1, 2, 3 };
  }

  inline uint32_t SystemStatus_t_GetLatestVersion()
  {
    return 3;
  }

  /* Version info for TelemetryData_t */
  inline std::vector<uint32_t> TelemetryData_t_GetSupportedVersions()
  {
    return { 1, 2, 3 };
  }

  inline uint32_t TelemetryData_t_GetLatestVersion()
  {
    return 3;
  }

  /* Find best common version between two version sets */
  inline uint32_t NegotiateBestVersion(
    const std::vector<uint32_t>& local_versions,
    const std::vector<uint32_t>& remote_versions)
  {
    uint32_t best = 0;
    for (auto v : local_versions)
    {
      if (std::find(remote_versions.begin(), remote_versions.end(), v) != remote_versions.end())
        if (v > best) best = v;
    }
    return best;
  }

} // namespace ductape
