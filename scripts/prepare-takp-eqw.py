#!/usr/bin/env python3
"""Apply the Wine-only raw mouse-look repair to exact upstream EQW 1.0.2."""
import argparse
import hashlib
from pathlib import Path
import subprocess

COMMIT = '3b4d43562c9dacc89349185684bb0bf0b01f9d06'
INPUT_SHA = '52b450f9667530db3741a2b4ea481cc3b4bfe8b692e8c1fbb79f825863bab5f2'
SOURCE_SHA = {
    'game_input.cpp': INPUT_SHA,
    'game_input.h': '8de968691c4c4e687df6edab004669201c3a64ee0b4da48e235e0ec5cb6f2dd0',
    'eq_game.cpp': 'c853ba205558997d8c95623c2c406ad1e25b2f98193adc1f898d3ee794ada33f',
    'dinput_manager.cpp': 'f7504811532c7e8832a093c1acbbc41961a1503920fe2a784cd1219056c419de',
}

CLIP_SUPPORT = '''// Wine 10's clipped path supplies true XI2 relative input. Keep the clip
// state synchronized because EQW's game-input and window threads differ.
static SRWLOCK camera_clip_lock = SRWLOCK_INIT;
static trasc_takp_camera::LookClip camera_clip;
bool IsWine() {
  static const bool wine = ::GetProcAddress(::GetModuleHandleW(L"ntdll.dll"), "wine_get_version") != nullptr;
  return wine;
}
bool GetCameraClip(trasc_takp_camera::Rect& value) {
  RECT rect;
  if (!::GetClipCursor(&rect)) return false;
  value = {rect.left, rect.top, rect.right, rect.bottom};
  return true;
}
bool SetCameraClip(const trasc_takp_camera::Rect& value) {
  RECT rect = {value.left, value.top, value.right, value.bottom};
  return ::ClipCursor(&rect) != 0;
}
void ReleaseCameraClip() {
  if (!IsWine()) return;
  ::AcquireSRWLockExclusive(&camera_clip_lock);
  const bool owned = camera_clip.held();
  const bool released = camera_clip.release(GetCameraClip, SetCameraClip);
  ::ReleaseSRWLockExclusive(&camera_clip_lock);
  if (owned) trasc_takp_trace::write("clip_release ok=%d", released);
}
bool HoldCameraClip(int x, int y) {
  if (!IsWine()) return false;
  ::AcquireSRWLockShared(&camera_clip_lock);
  const unsigned long generation = camera_clip.generation();
  ::ReleaseSRWLockShared(&camera_clip_lock);
  // The game look flag can remain stale while dead/stunned/zoning. Do not
  // reacquire after release. Wine's input query can pump window messages, so
  // it must remain outside the clip lock; generation rejects an overtaken query.
  const bool physical_down = (::GetAsyncKeyState(swap_mouse_buttons_ ? VK_LBUTTON : VK_RBUTTON) & 0x8000) != 0;
  const trasc_takp_camera::Rect bounds = {game_rect_.left, game_rect_.top, game_rect_.right, game_rect_.bottom};
  ::AcquireSRWLockExclusive(&camera_clip_lock);
  const bool foreground = ::GetForegroundWindow() == hwnd_;
  const bool iconic = ::IsIconic(hwnd_) != 0;
  const bool visible = ::IsWindowVisible(hwnd_) != 0;
  const bool active = physical_down && foreground && !iconic && visible;
  const bool held = active && camera_clip.hold_since(generation, x, y, bounds, GetCameraClip, SetCameraClip);
  if (!active) camera_clip.release(GetCameraClip, SetCameraClip);
  const unsigned long current_generation = camera_clip.generation();
  ::ReleaseSRWLockExclusive(&camera_clip_lock);
  static LONG prior_gate = -1;
  const LONG gate = held | (physical_down << 1) | (foreground << 2) | (iconic << 3) | (visible << 4);
  const bool changed = ::InterlockedExchange(&prior_gate, gate) != gate;
  if (trasc_takp_trace::sample(3, true, changed)) {
    trasc_takp_camera::Rect current_clip = {};
    POINT cursor = {};
    const bool got_clip = GetCameraClip(current_clip);
    const bool got_cursor = ::GetCursorPos(&cursor) != 0;
    trasc_takp_trace::write("clip_hold held=%d physical=%d foreground=%d iconic=%d visible=%d generation=%lu/%lu center=%d,%d bounds=%d,%d,%d,%d win_clip_ok=%d win_clip=%d,%d,%d,%d win_cursor_ok=%d win_cursor=%ld,%ld",
      held, physical_down, foreground, iconic, visible, generation, current_generation, x, y,
      bounds.left, bounds.top, bounds.right, bounds.bottom, got_clip, current_clip.left, current_clip.top, current_clip.right, current_clip.bottom,
      got_cursor, cursor.x, cursor.y);
  }
  static bool announced = false;
  if (held && !announced) { Logger::Info("%s", trasc_takp_camera::marker); announced = true; }
  return held;
}

'''

DINPUT_TRACE = '''// Observation only: preserve the client's exact DirectInput contract.
HRESULT WINAPI DeviceSetDataFormatHook(LPDIRECTINPUTDEVICE8W device, LPCDIDATAFORMAT format) {
  HRESULT result = DIERR_NOTINITIALIZED;
  if (device == keyboard_)
    result = hook_key_SetDataFormat_.original(DeviceSetDataFormatHook)(device, format);
  else if (device == mouse_)
    result = hook_mouse_SetDataFormat_.original(DeviceSetDataFormatHook)(device, format);
  if (device == mouse_) trasc_takp_observation::format_result(result, format);
  return result;
}
HRESULT WINAPI DeviceSetPropertyHook(LPDIRECTINPUTDEVICE8W device, REFGUID property, LPCDIPROPHEADER header) {
  HRESULT result = DIERR_NOTINITIALIZED;
  if (device == keyboard_)
    result = hook_key_SetProperty_.original(DeviceSetPropertyHook)(device, property, header);
  else if (device == mouse_)
    result = hook_mouse_SetProperty_.original(DeviceSetPropertyHook)(device, property, header);
  if (device == mouse_) trasc_takp_observation::property_result(result, property, header);
  return result;
}

'''

STATE_TRACE = '''  if (device == keyboard_)
    return hook_key_GetDeviceState_.original(DeviceGetDeviceStateHook)(device, buffer_size, data);
  if (device != mouse_) return DIERR_NOTINITIALIZED;
  const HRESULT result = hook_mouse_GetDeviceState_.original(DeviceGetDeviceStateHook)(device, buffer_size, data);
  trasc_takp_observation::state_result(result, static_cast<DWORD>(buffer_size), data);
  return result;'''

BUFFER_TRACE = '''  if (device == mouse_)
    trasc_takp_observation::data_result(result, static_cast<DWORD>(buffer_size), data, requested, event_count_max,
      static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(unk)));
'''

CONSUMER_BEFORE = '''  const bool trace_look = *g_mouse_rmb_down_mouse_look != 0;
  trasc_takp_trace::frame(trace_look);
  const long before_state_x = *g_mouse_x_abs_from_dinput_state, before_state_y = *g_mouse_y_abs_from_dinput_state;
  const long before_accum_x = *g_mouse_x_abs_from_dinput, before_accum_y = *g_mouse_y_abs_from_dinput;
  const short before_delta_x = *g_mouse_x_delta_from_dinput, before_delta_y = *g_mouse_y_delta_from_dinput;
  unsigned int result = hook_get_mouse_data_rel_.original(GetMouseDataRelHook)();
  const long after_state_x = *g_mouse_x_abs_from_dinput_state, after_state_y = *g_mouse_y_abs_from_dinput_state;
  const long after_accum_x = *g_mouse_x_abs_from_dinput, after_accum_y = *g_mouse_y_abs_from_dinput;
  const short delta_x = *g_mouse_x_delta_from_dinput, delta_y = *g_mouse_y_delta_from_dinput;
'''

CONSUMER_AFTER = '''  static LONG prior_delta_signs = 0;
  const LONG signs = (delta_x > 0 ? 1 : delta_x < 0 ? 2 : 0) | (delta_y > 0 ? 4 : delta_y < 0 ? 8 : 0);
  const bool changed = signs && ::InterlockedExchange(&prior_delta_signs, signs) != signs;
  if (trasc_takp_trace::sample(2, trace_look || *g_mouse_rmb_down_mouse_look, changed))
    trasc_takp_trace::write("consumer result=%u look=%d/%d focus=%d over=%d state_before=%ld,%ld state_after=%ld,%ld accum_before=%ld,%ld accum_after=%ld,%ld delta_before=%d,%d delta_after=%d,%d reset_state=%ld,%ld reset_accum=%ld,%ld saved=%ld,%ld",
      result, trace_look, *g_mouse_rmb_down_mouse_look != 0, has_focus, over_client,
      before_state_x, before_state_y, after_state_x, after_state_y, before_accum_x, before_accum_y,
      after_accum_x, after_accum_y, before_delta_x, before_delta_y, delta_x, delta_y, *g_mouse_x_abs_from_dinput_state, *g_mouse_y_abs_from_dinput_state,
      *g_mouse_x_abs_from_dinput, *g_mouse_y_abs_from_dinput, saved_rmouse_pt_.x, saved_rmouse_pt_.y);
  return result;
}

void __fastcall RightMouseUpHook'''


def prepare(source, root):
    source, root = Path(source), Path(root)
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != COMMIT:
        raise ValueError('TAKP EQW source is not the reviewed 1.0.2 commit')
    texts = {}
    for name, expected in SOURCE_SHA.items():
        original = (source/'eqw_takp'/name).read_bytes()
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError('TAKP EQW source changed before patching: ' + name)
        texts[name] = original.decode('utf-8')
    changes = {
        'game_input.cpp': [
            ('#include "game_input.h"', '#include "game_input.h"\n#include "trasc_camera_recenter.h"\n#define TRASC_TAKP_TRACE_IMPLEMENTATION\n#include "takp_camera_trace.h"'),
            ('// Synchronizes the win32 cursor to the internal cursor position.', CLIP_SUPPORT + '// Synchronizes the win32 cursor to the internal cursor position.'),
            ('void SetWin32CursorToClientPosition(POINT pt) {', 'void SetWin32CursorToClientPosition(POINT pt, bool camera_center = false) {'),
            ('  ::SetCursorPos(pt.x, pt.y);', '  if (!camera_center || !HoldCameraClip(pt.x, pt.y)) ::SetCursorPos(pt.x, pt.y);'),
            ('  SetWin32CursorToClientPosition(center);', '  SetWin32CursorToClientPosition(center, true);'),
            ('  if (!internal_mode) {', '  if (!internal_mode) {\n    ReleaseCameraClip();'),
            ('    mouse_disabled = true;', '    trasc_takp_trace::frame(false);\n    mouse_disabled = true;'),
            ('  unsigned int result = hook_get_mouse_data_rel_.original(GetMouseDataRelHook)();', CONSUMER_BEFORE),
            ('  return result;\n}\n\nvoid __fastcall RightMouseUpHook', CONSUMER_AFTER),
            ('  } else {\n    SyncToWin32Cursor();', '  } else {\n    ReleaseCameraClip();\n    SyncToWin32Cursor();'),
            ('  if (mouse_look_active && !*g_mouse_rmb_down_mouse_look) SetBothCursorsToClientPosition(saved_rmouse_pt_);',
             '  if (mouse_look_active && !*g_mouse_rmb_down_mouse_look) {\n    ReleaseCameraClip();\n    SetBothCursorsToClientPosition(saved_rmouse_pt_);\n  }'),
            ('void GameInput::HandleLossOfFocus() {', '''void GameInput::ReleaseCameraCursor(UINT message) {
  // Respect EQW's existing physical button swap when input hooks are paused.
  if ((message == WM_LBUTTONUP || message == WM_RBUTTONUP) &&
      message != (GameInputInt::swap_mouse_buttons_ ? WM_LBUTTONUP : WM_RBUTTONUP)) return;
  GameInputInt::ReleaseCameraClip();
}

void GameInput::HandleLossOfFocus() {
  GameInputInt::ReleaseCameraClip();'''),
            ('  hwnd_ = hwnd;', '  hwnd_ = hwnd;\n  trasc_takp_trace::write("initialize helper=%s swap_buttons=%d", trasc_takp_camera::marker, swap_mouse_buttons);'),
        ],
        'game_input.h': [('void HandleLossOfFocus();', 'void ReleaseCameraCursor(UINT message);  // Wine-only look clipping; release even if game input is paused.\nvoid HandleLossOfFocus();')],
        'eq_game.cpp': [
            ('      EqMain::Initialize(hmod, hwnd_, ini_path_, eqmain_init_fn_);',
             '      GameInput::ReleaseCameraCursor(0);  // Login takes ownership; game polling/window proc stops.\n      EqMain::Initialize(hmod, hwnd_, ini_path_, eqmain_init_fn_);'),
            ('  bool execute_eqgame_wndproc = false;', '''  // The game input hook can be skipped while dead/stunned/zoning. Release
  // the Wine-only camera clip at physical release and window lifecycle events.
  if (msg == WM_RBUTTONUP || msg == WM_LBUTTONUP || msg == WM_KILLFOCUS ||
      (msg == WM_ACTIVATEAPP && !wParam) || (msg == WM_SIZE && wParam == SIZE_MINIMIZED) ||
      msg == WM_CLOSE || msg == WM_DESTROY) GameInput::ReleaseCameraCursor(msg);
  bool execute_eqgame_wndproc = false;'''),
        ],
        'dinput_manager.cpp': [
            ('#include <dinput.h>', '#include <dinput.h>\n#include "takp_dinput_observation.h"'),
            ('VTableHook hook_key_SetCooperativeLevel_;', 'VTableHook hook_key_SetProperty_;\nVTableHook hook_key_SetDataFormat_;\nVTableHook hook_key_SetCooperativeLevel_;'),
            ('VTableHook hook_mouse_SetCooperativeLevel_;', 'VTableHook hook_mouse_SetProperty_;\nVTableHook hook_mouse_SetDataFormat_;\nVTableHook hook_mouse_SetCooperativeLevel_;'),
            ('// Block any client attempts to release the dinput device resources.', DINPUT_TRACE + '// Block any client attempts to release the dinput device resources.'),
            ('  HRESULT result = DIERR_NOTINITIALIZED;\n  if (device == keyboard_)\n    result = hook_key_GetDeviceData_', '  const DWORD requested = event_count_max ? *event_count_max : 0;\n  HRESULT result = DIERR_NOTINITIALIZED;\n  if (device == keyboard_)\n    result = hook_key_GetDeviceData_'),
            ('  // The game client has a bug', BUFFER_TRACE + '  // The game client has a bug'),
            ('  if (result == DI_OK) {  // Returns DI_OK', '  if (device == mouse_ && result != S_FALSE && trasc_takp_trace::sample(3, true))\n    trasc_takp_trace::write("acquire hr=%08lx flush=%d", static_cast<unsigned long>(result), result == DI_OK);\n  if (result == DI_OK) {  // Returns DI_OK'),
            ('  const char* effect = (result == DI_OK)', '  if (device == mouse_) trasc_takp_trace::write("unacquire hr=%08lx", static_cast<unsigned long>(result));\n  const char* effect = (result == DI_OK)'),
            ('''  if (device == keyboard_)
    return hook_key_GetDeviceState_.original(DeviceGetDeviceStateHook)(device, buffer_size, data);
  else if (device == mouse_)
    return hook_mouse_GetDeviceState_.original(DeviceGetDeviceStateHook)(device, buffer_size, data);
  else
    return DIERR_NOTINITIALIZED;''', STATE_TRACE),
            ('    hook_key_GetDeviceState_ = VTableHook', '    hook_key_SetProperty_ = VTableHook(vtable, 6, DeviceSetPropertyHook);\n    hook_key_SetDataFormat_ = VTableHook(vtable, 11, DeviceSetDataFormatHook);\n    hook_key_GetDeviceState_ = VTableHook'),
            ('    hook_mouse_GetDeviceState_ = VTableHook', '    hook_mouse_SetProperty_ = VTableHook(vtable, 6, DeviceSetPropertyHook);\n    hook_mouse_SetDataFormat_ = VTableHook(vtable, 11, DeviceSetDataFormatHook);\n    hook_mouse_GetDeviceState_ = VTableHook'),
        ],
    }
    for name, replacements in changes.items():
        for old, new in replacements:
            if texts[name].count(old) != 1:
                raise ValueError('TAKP EQW camera patch anchor changed: ' + name)
            texts[name] = texts[name].replace(old, new)
    for name, value in texts.items():
        (source/'eqw_takp'/name).write_bytes(value.encode('utf-8'))
    (source/'eqw_takp/trasc_camera_recenter.h').write_bytes((root/'native/takp_camera_recenter.h').read_bytes())
    (source/'eqw_takp/takp_camera_trace.h').write_bytes((root/'native/takp_camera_trace.h').read_bytes())
    (source/'eqw_takp/takp_dinput_observation.h').write_bytes((root/'native/takp_dinput_observation.h').read_bytes())
    print('PASS: exact EQW source patched; V2 delivery retained, bounded Wine-only format/consumer/capture diagnostics added')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    prepare(args.source, args.root)
