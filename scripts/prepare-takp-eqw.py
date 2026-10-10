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
  camera_clip.release(GetCameraClip, SetCameraClip);
  ::ReleaseSRWLockExclusive(&camera_clip_lock);
}
bool HoldCameraClip(int x, int y) {
  if (!IsWine()) return false;
  const trasc_takp_camera::Rect bounds = {game_rect_.left, game_rect_.top, game_rect_.right, game_rect_.bottom};
  ::AcquireSRWLockExclusive(&camera_clip_lock);
  const bool held = camera_clip.hold(x, y, bounds, GetCameraClip, SetCameraClip);
  ::ReleaseSRWLockExclusive(&camera_clip_lock);
  static bool announced = false;
  if (held && !announced) { Logger::Info("%s", trasc_takp_camera::marker); announced = true; }
  return held;
}

'''


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
            ('#include "game_input.h"', '#include "game_input.h"\n#include "trasc_camera_recenter.h"'),
            ('// Synchronizes the win32 cursor to the internal cursor position.', CLIP_SUPPORT + '// Synchronizes the win32 cursor to the internal cursor position.'),
            ('void SetWin32CursorToClientPosition(POINT pt) {', 'void SetWin32CursorToClientPosition(POINT pt, bool camera_center = false) {'),
            ('  ::SetCursorPos(pt.x, pt.y);', '  if (!camera_center || !HoldCameraClip(pt.x, pt.y)) ::SetCursorPos(pt.x, pt.y);'),
            ('  SetWin32CursorToClientPosition(center);', '  SetWin32CursorToClientPosition(center, true);'),
            ('  if (!internal_mode) {', '  if (!internal_mode) {\n    ReleaseCameraClip();'),
            ('  } else {\n    SyncToWin32Cursor();', '  } else {\n    ReleaseCameraClip();\n    SyncToWin32Cursor();'),
            ('  if (mouse_look_active && !*g_mouse_rmb_down_mouse_look) SetBothCursorsToClientPosition(saved_rmouse_pt_);',
             '  if (mouse_look_active && !*g_mouse_rmb_down_mouse_look) {\n    ReleaseCameraClip();\n    SetBothCursorsToClientPosition(saved_rmouse_pt_);\n  }'),
            ('void GameInput::HandleLossOfFocus() {', 'void GameInput::ReleaseCameraCursor() { GameInputInt::ReleaseCameraClip(); }\n\nvoid GameInput::HandleLossOfFocus() {\n  GameInputInt::ReleaseCameraClip();'),
        ],
        'game_input.h': [('void HandleLossOfFocus();', 'void ReleaseCameraCursor();  // Wine-only look clipping; release even if game input is paused.\nvoid HandleLossOfFocus();')],
        'eq_game.cpp': [
            ('  bool execute_eqgame_wndproc = false;', '''  // The game input hook can be skipped while dead/stunned/zoning. Release
  // the Wine-only camera clip at physical release and window lifecycle events.
  if (msg == WM_RBUTTONUP || msg == WM_KILLFOCUS ||
      (msg == WM_ACTIVATEAPP && !wParam) || (msg == WM_SIZE && wParam == SIZE_MINIMIZED) ||
      msg == WM_CLOSE || msg == WM_DESTROY) GameInput::ReleaseCameraCursor();
  bool execute_eqgame_wndproc = false;'''),
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
    print('PASS: exact EQW source patched; Wine-only raw look, original RMB/focus gates, prior clip/cursor restore and native Windows behavior retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    prepare(args.source, args.root)
