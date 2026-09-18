#!/usr/bin/env python3
"""Verify particle visibility with the exact private ROF2 executable and DLL.

Requires pefile and unicorn. Reads both inputs without modifying them. Executes
original actor construction, setters/getters, camera callbacks, actor assignment,
and a bounded particle visibility branch. This is not a full rendered-game test.
"""

import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import pefile
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

spec = importlib.util.spec_from_file_location('view', Path(__file__).with_name('verify-client-view.py'))
view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(view)

GRAPHICS_SHA256 = '164fc072547aab752567ba88bf6936d0e328c44a16a1480f340d27aef0ba6290'
GRAPHICS_BASE = 0x10000000
ACTOR_CTOR = 0x1003AB80
PARTICLE_SETTER = 0x1003B1A0
PARTICLE_GETTER = 0x1003B190
INVISIBLE_SETTER = 0x10046F10
INVISIBLE_GETTER = 0x10046F20
HIERARCHICAL_VTABLE = 0x10137074
VISIBILITY_BRANCH = 0x100726E4
VISIBILITY_END = 0x10072802
EFFECT = view.HEAP + 0xB000
REPLACEMENT_ACTOR = view.HEAP + 0xC000


def load_image(path, expected_hash, expected_base):
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_hash:
        raise SystemExit(f'Unsupported input SHA256 ({path.name}): {actual}')
    pe = pefile.PE(data=data)
    assert pe.FILE_HEADER.Machine == 0x14C
    assert pe.OPTIONAL_HEADER.ImageBase == expected_base
    return pe.get_memory_mapped_image()


class Fixture(view.Fixture):
    def __init__(self, executable, graphics):
        super().__init__(executable)
        self.uc.mem_map(GRAPHICS_BASE, (len(graphics) + 0xFFF) & ~0xFFF)
        self.uc.mem_write(GRAPHICS_BASE, graphics)
        self.construct(view.ACTOR)
        self.write(EFFECT + 0x98, 0xFFFFFFFF)

    def construct(self, actor):
        # The full derived constructor needs the live engine. Execute the actual
        # base constructor, then supply the verified derived vtable and zeroed
        # backing object state for its simple visibility methods.
        self.uc.mem_write(actor, bytes(0x400))
        self.uc.mem_write(actor + 0x5C, b'\xff')
        self.call(ACTOR_CTOR, actor)
        assert self.uc.mem_read(actor + 0x5C, 1) == b'\x00'
        self.write(actor, HIERARCHICAL_VTABLE)

    def call(self, address, this=view.CAMERA_BASE, args=()):
        self.write(view.STACK, view.STOP)
        for index, arg in enumerate(args):
            self.write(view.STACK + 4 + index * 4, arg)
        self.uc.reg_write(UC_X86_REG_ESP, view.STACK)
        self.uc.reg_write(UC_X86_REG_ECX, this)
        preserved = {UC_X86_REG_EBP: 0x456789AB, UC_X86_REG_EBX: 0x12345678,
                     UC_X86_REG_ESI: 0x23456789, UC_X86_REG_EDI: 0x3456789A}
        for register, value in preserved.items():
            self.uc.reg_write(register, value)
        self.uc.emu_start(address, view.STOP, count=3000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == view.STOP
        assert self.uc.reg_read(UC_X86_REG_ESP) == view.STACK + 4 + len(args) * 4
        for register, value in preserved.items():
            assert self.uc.reg_read(register) == value
        return self.uc.reg_read(UC_X86_REG_EAX)

    def flag(self, actor=view.ACTOR):
        return bool(self.call(PARTICLE_GETTER, actor) & 0xFF)

    def invisible(self, actor=view.ACTOR):
        return bool(self.call(INVISIBLE_GETTER, actor) & 0xFF)

    def suppressed(self, actor=view.ACTOR, sentinel=0xFFFFFFFF):
        # Execute the original actor-backed visibility block inside the particle
        # processing routine, stopping at the join point before unrelated maths.
        # Every virtual call made by this block runs the original graphics code.
        self.write(EFFECT + 0x98, sentinel)
        self.uc.mem_write(view.STACK + 0x1B, b'\x00')
        self.uc.reg_write(UC_X86_REG_ESP, view.STACK)
        self.uc.reg_write(UC_X86_REG_ESI, actor)
        self.uc.reg_write(UC_X86_REG_EBP, EFFECT)
        self.uc.emu_start(VISIBILITY_BRANCH, VISIBILITY_END, count=1000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == VISIBILITY_END
        assert self.uc.reg_read(UC_X86_REG_ESP) == view.STACK
        return bool(self.uc.mem_read(view.STACK + 0x1B, 1)[0])


def main():
    if not __debug__:
        raise SystemExit('Run without -O: assertions are the verification checks.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('graphics_dll', type=Path)
    args = parser.parse_args()
    executable = load_image(args.executable, view.EXPECTED_SHA256, view.BASE)
    graphics = load_image(args.graphics_dll, GRAPHICS_SHA256, GRAPHICS_BASE)
    u32 = lambda address: struct.unpack_from('<I', graphics, address - GRAPHICS_BASE)[0]
    for vtable in (0x10136824, HIERARCHICAL_VTABLE, 0x101373B4, 0x1013802C, 0x1013841C):
        assert u32(vtable + 0x23C) == PARTICLE_SETTER
        assert u32(vtable + 0x240) == PARTICLE_GETTER

    results = []
    f = Fixture(executable, graphics)
    assert not f.flag()
    results.append({'case': 'base_constructor_clears_particle_permission', 'passed': True})
    for hidden in (False, True):
        for allowed in (False, True):
            f.call(INVISIBLE_SETTER, view.ACTOR, [int(hidden)])
            f.call(PARTICLE_SETTER, view.ACTOR, [int(allowed)])
            assert f.invisible() == hidden and f.flag() == allowed
            suppressed = f.suppressed()
            assert suppressed == (hidden and not allowed)
            results.append({'case': 'original_visibility_branch', 'hidden': hidden,
                            'permission': allowed, 'suppressed': suppressed})

    f = Fixture(executable, graphics)
    f.write(view.MODE, 1)
    f.write(view.PLAYER + view.PLAYER_ACTOR, 0)
    f.call(view.SWITCH, args=[0])
    assert f.read(view.MODE) == 0 and not f.flag()
    f.call(0x40C000, view.PLAYER + 0xEA4, [view.ACTOR])
    f.call(INVISIBLE_SETTER, view.ACTOR, [1])
    assert f.suppressed()
    f.call(view.SWITCH, args=[1])
    f.call(view.SWITCH, args=[0])
    assert f.flag() and f.invisible() and not f.suppressed()
    results.append({'case': 'late_actor_then_view_only_roundtrip', 'passed': True,
                    'suppressed_before': True, 'suppressed_after': False,
                    'actor_remains_invisible': True})

    f.construct(REPLACEMENT_ACTOR)
    f.write(view.ACTOR + 0x74, 0x12345678)
    f.write(view.ACTOR + 0x78, 5)
    f.call(0x40C000, view.PLAYER + 0xEA4, [REPLACEMENT_ACTOR])
    assert f.read(view.PLAYER + view.PLAYER_ACTOR) == REPLACEMENT_ACTOR
    assert f.read(REPLACEMENT_ACTOR + 0x74) == 0x12345678
    assert f.read(REPLACEMENT_ACTOR + 0x78) == 5
    assert f.read(view.ACTOR + 0x74) == f.read(view.ACTOR + 0x78) == 0
    assert f.flag() and not f.flag(REPLACEMENT_ACTOR)
    f.call(INVISIBLE_SETTER, REPLACEMENT_ACTOR, [1])
    assert f.suppressed(REPLACEMENT_ACTOR)
    f.call(view.FIRST_ENTER, args=[0])
    assert f.flag(REPLACEMENT_ACTOR) and not f.suppressed(REPLACEMENT_ACTOR)
    assert f.read(view.MODE) == 0
    results.append({'case': 'actor_replacement_does_not_transfer_permission', 'passed': True,
                    'entry_reapplication_restores_branch_without_mode_change': True})

    f.call(PARTICLE_SETTER, view.ACTOR, [0])
    f.call(PARTICLE_SETTER, REPLACEMENT_ACTOR, [0])
    actor_before = bytes(f.uc.mem_read(REPLACEMENT_ACTOR, 0x400))
    camera_before = bytes(f.uc.mem_read(view.CAMERA_BASE, 0x700))
    assert f.suppressed(REPLACEMENT_ACTOR)
    f.call(PARTICLE_SETTER, REPLACEMENT_ACTOR, [1])
    actor_after = bytes(f.uc.mem_read(REPLACEMENT_ACTOR, 0x400))
    changed = [i for i, (a, b) in enumerate(zip(actor_before, actor_after)) if a != b]
    assert changed == [0x5C]
    assert camera_before == bytes(f.uc.mem_read(view.CAMERA_BASE, 0x700))
    assert f.read(view.MODE) == 0 and not f.flag(view.ACTOR)
    assert f.invisible(REPLACEMENT_ACTOR) and not f.suppressed(REPLACEMENT_ACTOR)
    results.append({'case': 'single_setter_call_restores_permission_without_camera_change',
                    'passed': True, 'changed_actor_offsets': ['0x5c']})

    f.uc.mem_write(REPLACEMENT_ACTOR + 0xD1, b'\x01')
    assert f.flag(REPLACEMENT_ACTOR) and f.suppressed(REPLACEMENT_ACTOR)
    f.uc.mem_write(REPLACEMENT_ACTOR + 0xD1, b'\x00')
    results.append({'case': 'separate_disabled_actor_gate_remains_effective', 'passed': True})

    f.call(view.FIRST_LEAVE, args=[0])
    assert not f.flag(REPLACEMENT_ACTOR)
    f.call(INVISIBLE_SETTER, REPLACEMENT_ACTOR, [0])
    assert not f.suppressed(REPLACEMENT_ACTOR)
    results.append({'case': 'leaving_first_person_preserves_visible_actor_particles', 'passed': True})

    f.call(INVISIBLE_SETTER, REPLACEMENT_ACTOR, [1])
    assert not f.suppressed(REPLACEMENT_ACTOR, sentinel=0)
    results.append({'case': 'original_effect_sentinel_exception_preserved', 'passed': True})

    print(json.dumps({'verified': True, 'executable_sha256': view.EXPECTED_SHA256,
                      'graphics_sha256': GRAPHICS_SHA256,
                      'scope': 'Original code on synthetic objects; bounded visibility branch, no D3D or live-login claim',
                      'cases': results}, indent=2))


if __name__ == '__main__':
    main()
