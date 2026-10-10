#!/usr/bin/env python3
"""Apply the narrow Wine-only camera repair to exact upstream EQW 1.0.2."""
import argparse
import hashlib
from pathlib import Path
import subprocess

COMMIT = '3b4d43562c9dacc89349185684bb0bf0b01f9d06'
INPUT_SHA = '52b450f9667530db3741a2b4ea481cc3b4bfe8b692e8c1fbb79f825863bab5f2'


def prepare(source, root):
    source, root = Path(source), Path(root)
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != COMMIT:
        raise ValueError('TAKP EQW source is not the reviewed 1.0.2 commit')
    target = source / 'eqw_takp/game_input.cpp'
    original = target.read_bytes()
    if hashlib.sha256(original).hexdigest() != INPUT_SHA:
        raise ValueError('TAKP EQW input source changed before patching')
    text = original.decode('utf-8')
    changes = [
        ('#include "game_input.h"', '#include "game_input.h"\n#include "trasc_camera_recenter.h"'),
        ('void SetWin32CursorToClientPosition(POINT pt) {',
         'void SetWin32CursorToClientPosition(POINT pt, bool force_wine_center = false) {'),
        ('  ::SetCursorPos(pt.x, pt.y);', '''  static const bool wine = ::GetProcAddress(::GetModuleHandleW(L"ntdll.dll"), "wine_get_version") != nullptr;
  if (force_wine_center && wine) {
    static bool announced = false;
    if (!announced) { Logger::Info("%s", trasc_takp_camera::marker); announced = true; }
  }
  trasc_takp_camera::center(pt.x, pt.y, game_rect_.left, game_rect_.right,
      force_wine_center && wine, [](int x, int y) { return ::SetCursorPos(x, y); });'''),
        ('  SetWin32CursorToClientPosition(center);', '  SetWin32CursorToClientPosition(center, true);'),
    ]
    for old, new in changes:
        if text.count(old) != 1:
            raise ValueError('TAKP EQW camera patch anchor changed')
        text = text.replace(old, new)
    target.write_bytes(text.encode('utf-8'))
    (source / 'eqw_takp/trasc_camera_recenter.h').write_bytes((root / 'native/takp_camera_recenter.h').read_bytes())
    print('PASS: exact EQW source patched; original RMB/focus gates, cursor restore and native Windows behavior retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    prepare(args.source, args.root)
