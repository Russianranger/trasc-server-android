// Bounded private camera telemetry. It never changes input values or settings.
#pragma once
#include <windows.h>

namespace trasc_takp_trace {
void write(const char* format, ...);
void frame(bool look);
bool looking();
bool sample(unsigned kind, bool interesting, bool transition = false);
}

#ifdef TRASC_TAKP_TRACE_IMPLEMENTATION
#include <cstdarg>
#include <cstdio>
#include <cstring>
namespace trasc_takp_trace {
namespace {
SRWLOCK trace_lock = SRWLOCK_INIT;
HANDLE trace_file = INVALID_HANDLE_VALUE;
bool attempted = false;
DWORD written = 0;
volatile LONG look_frame = 0;
volatile LONG samples[4] = {};
const char trace_marker[] = "TRASC_TAKP_CAMERA_TRACE_V1\n";
const DWORD trace_limit = 128 * 1024;

void open_trace() {
  attempted = true;
  if (!::GetProcAddress(::GetModuleHandleW(L"ntdll.dll"), "wine_get_version")) return;
  char path[MAX_PATH];
  DWORD count = ::GetModuleFileNameA(nullptr, path, MAX_PATH);
  if (!count || count >= MAX_PATH) return;
  char* slash = std::strrchr(path, '\\');
  const char name[] = "eqw-camera-diagnostics.log";
  if (!slash || static_cast<size_t>(slash + 1 - path) + sizeof(name) > sizeof(path)) return;
  std::memcpy(slash + 1, name, sizeof(name));
  HANDLE file = ::CreateFileA(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                             OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
  if (file == INVALID_HANDLE_VALUE) return;
  BY_HANDLE_FILE_INFORMATION info;
  LARGE_INTEGER size, zero = {};
  bool ordinary = ::GetFileInformationByHandle(file, &info) &&
                  !(info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY));
  bool owned = ordinary && ::GetFileSizeEx(file, &size);
  if (owned && size.QuadPart) {
    char marker[sizeof(trace_marker) - 1]; DWORD read = 0;
    owned = ::ReadFile(file, marker, sizeof(marker), &read, nullptr) && read == sizeof(marker) &&
            !std::memcmp(marker, trace_marker, sizeof(marker));
  }
  if (!owned || !::SetFilePointerEx(file, zero, nullptr, FILE_BEGIN) || !::SetEndOfFile(file)) {
    ::CloseHandle(file); return;
  }
  DWORD bytes = 0;
  if (!::WriteFile(file, trace_marker, sizeof(trace_marker) - 1, &bytes, nullptr) || bytes != sizeof(trace_marker) - 1) {
    ::CloseHandle(file); return;
  }
  trace_file = file; written = bytes;
}
}

void frame(bool look) { ::InterlockedExchange(&look_frame, look ? 1 : 0); }
bool looking() { return ::InterlockedCompareExchange(&look_frame, 0, 0) != 0; }
bool sample(unsigned kind, bool interesting, bool transition) {
  if (!interesting || kind >= 4) return false;
  LONG count = ::InterlockedIncrement(samples + kind);
  return transition || count <= 24 || count % 30 == 0;
}
void write(const char* format, ...) {
  ::AcquireSRWLockExclusive(&trace_lock);
  if (!attempted) open_trace();
  if (trace_file != INVALID_HANDLE_VALUE && written < trace_limit) {
    char line[1024];
    int head = std::snprintf(line, sizeof(line), "t=%lu thread=%lu ",
                             static_cast<unsigned long>(::GetTickCount()),
                             static_cast<unsigned long>(::GetCurrentThreadId()));
    va_list args; va_start(args, format);
    int tail = head > 0 && static_cast<size_t>(head) < sizeof(line) - 2 ?
      std::vsnprintf(line + head, sizeof(line) - head - 2, format, args) : -1;
    va_end(args);
    if (head > 0 && tail >= 0) {
      size_t length = static_cast<size_t>(head + tail);
      if (length > sizeof(line) - 2) length = sizeof(line) - 2;
      line[length++] = '\n';
      DWORD bytes = 0;
      if (written + length <= trace_limit && ::WriteFile(trace_file, line, static_cast<DWORD>(length), &bytes, nullptr))
        written += bytes;
    }
  }
  ::ReleaseSRWLockExclusive(&trace_lock);
}
}
#endif
