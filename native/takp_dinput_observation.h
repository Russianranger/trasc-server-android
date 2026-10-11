// Observe the application's exact DirectInput contract. No drains, mode changes,
// value conversion, acquisition calls or additional input queries.
#pragma once
#include <windows.h>
#include <dinput.h>
#include <cstring>
#include "takp_camera_trace.h"

namespace trasc_takp_observation {
namespace {
struct Format { LONG x = -1, y = -1, z = -1; DWORD size = 0; LONG axis_mode = -1; };
SRWLOCK format_lock = SRWLOCK_INIT;
Format mouse_format;
volatile LONG prior_state_signs = 0, prior_buffer_signs = 0;
}
inline void format_result(HRESULT result, LPCDIDATAFORMAT value) {
  if (FAILED(result)) { trasc_takp_trace::write("format hr=%08lx rejected=1", static_cast<unsigned long>(result)); return; }
  if (!value || value->dwSize < sizeof(DIDATAFORMAT)) {
    trasc_takp_trace::write("format hr=%08lx no_description=1", static_cast<unsigned long>(result));
    return;
  }
  Format next;
  next.size = value->dwDataSize;
  next.axis_mode = value->dwFlags & DIDF_ABSAXIS ? DIPROPAXISMODE_ABS :
                   value->dwFlags & DIDF_RELAXIS ? DIPROPAXISMODE_REL : -1;
  if (value->rgodf && value->dwObjSize >= sizeof(DIOBJECTDATAFORMAT) && value->dwNumObjs <= 32) {
    for (DWORD i = 0; i < value->dwNumObjs; ++i) {
      const DIOBJECTDATAFORMAT* object = reinterpret_cast<const DIOBJECTDATAFORMAT*>(
        reinterpret_cast<const BYTE*>(value->rgodf) + i * value->dwObjSize);
      if (!object->pguid) continue;
      if (IsEqualGUID(*object->pguid, GUID_XAxis)) next.x = object->dwOfs;
      if (IsEqualGUID(*object->pguid, GUID_YAxis)) next.y = object->dwOfs;
      if (IsEqualGUID(*object->pguid, GUID_ZAxis)) next.z = object->dwOfs;
    }
  }
  if (SUCCEEDED(result)) {
    ::AcquireSRWLockExclusive(&format_lock); mouse_format = next; ::ReleaseSRWLockExclusive(&format_lock);
  }
  trasc_takp_trace::write("format hr=%08lx flags=%08lx data_size=%lu objects=%lu axis_offsets=%ld,%ld,%ld axis_mode=%ld",
    static_cast<unsigned long>(result), value->dwFlags, value->dwDataSize, value->dwNumObjs, next.x, next.y, next.z, next.axis_mode);
}
inline void property_result(HRESULT result, REFGUID property, LPCDIPROPHEADER header) {
  // MAKEDIPROP IDs are integer addresses; dereferencing as GUIDs is invalid.
  const ULONG_PTR id = reinterpret_cast<ULONG_PTR>(&property);
  if (FAILED(result)) { trasc_takp_trace::write("property id=%lu hr=%08lx rejected=1", static_cast<unsigned long>(id), static_cast<unsigned long>(result)); return; }
  if ((id != 1 && id != 2) || !header || header->dwSize < sizeof(DIPROPDWORD) ||
      header->dwHeaderSize != sizeof(DIPROPHEADER)) return;
  const DIPROPDWORD* value = reinterpret_cast<const DIPROPDWORD*>(header);
  if (SUCCEEDED(result) && id == 2 && header->dwHow == DIPH_DEVICE) {
    ::AcquireSRWLockExclusive(&format_lock); mouse_format.axis_mode = value->dwData; ::ReleaseSRWLockExclusive(&format_lock);
  }
  trasc_takp_trace::write("property id=%lu hr=%08lx value=%lu how=%lu object=%lu",
    static_cast<unsigned long>(id), static_cast<unsigned long>(result), value->dwData, header->dwHow, header->dwObj);
}
inline bool axis_value(const void* data, DWORD size, LONG offset, LONG& result) {
  if (!data || offset < 0 || static_cast<DWORD>(offset) > size || size - static_cast<DWORD>(offset) < sizeof(LONG)) return false;
  std::memcpy(&result, static_cast<const BYTE*>(data) + offset, sizeof(result)); return true;
}
inline LONG signs(LONG x, LONG y) { return (x > 0 ? 1 : x < 0 ? 2 : 0) | (y > 0 ? 4 : y < 0 ? 8 : 0); }
inline void state_result(HRESULT result, DWORD size, const void* data) {
  ::AcquireSRWLockShared(&format_lock); const Format format = mouse_format; ::ReleaseSRWLockShared(&format_lock);
  LONG x = 0, y = 0, z = 0;
  const bool known = SUCCEEDED(result) && size == format.size && axis_value(data, size, format.x, x) && axis_value(data, size, format.y, y);
  if (known) axis_value(data, size, format.z, z);
  const LONG direction = signs(x, y);
  const bool changed = direction && ::InterlockedExchange(&prior_state_signs, direction) != direction;
  if (trasc_takp_trace::sample(0, trasc_takp_trace::looking() || direction, changed))
    trasc_takp_trace::write("state hr=%08lx size=%lu look=%d axis_mode=%ld axis_known=%d value=%ld,%ld,%ld",
      static_cast<unsigned long>(result), size, trasc_takp_trace::looking(), format.axis_mode, known, x, y, z);
}
inline void data_result(HRESULT result, DWORD stride, const void* data, DWORD requested, const DWORD* returned, DWORD flags) {
  ::AcquireSRWLockShared(&format_lock); const Format format = mouse_format; ::ReleaseSRWLockShared(&format_lock);
  const bool known = format.x >= 0 && format.y >= 0;
  const DWORD count = SUCCEEDED(result) && returned ? *returned : 0;
  const DWORD bounded = count < requested ? count : requested;
  const DWORD inspect = data && (stride == 16 || stride == sizeof(DIDEVICEOBJECTDATA)) ? (bounded < 32 ? bounded : 32) : 0;
  LONGLONG sum_x = 0, sum_y = 0;
  LONG last_x = 0, last_y = 0;
  DWORD first_time = 0, last_time = 0, first_sequence = 0, last_sequence = 0;
  for (DWORD i = 0; i < inspect; ++i) {
    DWORD event[4]; std::memcpy(event, static_cast<const BYTE*>(data) + i * stride, sizeof(event));
    if (known && event[0] == static_cast<DWORD>(format.x)) { last_x = static_cast<LONG>(event[1]); sum_x += last_x; }
    if (known && event[0] == static_cast<DWORD>(format.y)) { last_y = static_cast<LONG>(event[1]); sum_y += last_y; }
    if (!i) { first_time = event[2]; first_sequence = event[3]; }
    last_time = event[2]; last_sequence = event[3];
  }
  const LONG direction = signs(last_x, last_y);
  const bool changed = direction && ::InterlockedExchange(&prior_buffer_signs, direction) != direction;
  if (trasc_takp_trace::sample(1, trasc_takp_trace::looking() || count, changed))
    trasc_takp_trace::write("buffer hr=%08lx size=%lu requested=%lu count=%lu flags=%lu data=%d look=%d inspected=%lu axis_mode=%ld axis_known=%d sum_values=%lld,%lld last_values=%ld,%ld timestamps=%lu,%lu sequences=%lu,%lu oldest_age_ms=%lu",
      static_cast<unsigned long>(result), stride, requested, count, flags, data != nullptr, trasc_takp_trace::looking(), inspect, format.axis_mode, known,
      sum_x, sum_y, last_x, last_y, first_time, last_time, first_sequence, last_sequence, inspect ? ::GetTickCount() - first_time : 0);
}
}
