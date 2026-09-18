#!/usr/bin/env python3
"""Read-only verification of camera transitions in the user's exact ROF2 PE.

Requires pefile and unicorn. No game files are included or modified. The original
camera dispatcher/callbacks execute in Unicorn; graphics methods are recording
stubs. This verifies control flow and ABI, not rendered particles or live startup.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

EXPECTED_SHA256 = '4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'
BASE = 0x400000
SWITCH = 0x48ADF0
FIRST_ENTER = 0x797220
FIRST_LEAVE = 0x7971B0
CAMERAS = 0xDE0D64
MODE = 0xD1FD9C
LOCAL_PLAYER = 0xDD2630
LOCAL_CHARACTER = 0xDD261C
PLAYER_ACTOR = 0x101C
FIRST_VTABLE = 0x9D0F80

# Synthetic memory and recording functions, outside the mapped game image.
HEAP = 0x3000000
PLAYER = HEAP + 0x1000
ACTOR = HEAP + 0x4000
ACTOR_VTABLE = HEAP + 0x5000
CAMERA_BASE = HEAP + 0x6000
SET_PARTICLES = HEAP + 0x8000
SET_PITCH = HEAP + 0x8010
FREE_CAMERA_RESET = HEAP + 0x8020
STOP = HEAP + 0x9000
STACK = HEAP + 0x1F000
LOCK_QUERY = 0x7BED30


class Fixture:
    def __init__(self, image):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(BASE, (len(image) + 0xFFF) & ~0xFFF)
        self.uc.mem_write(BASE, image)
        self.uc.mem_map(HEAP, 0x20000)
        self.events = []
        self.lock_value = 0
        self.write(LOCAL_PLAYER, PLAYER)
        self.write(LOCAL_CHARACTER, 0)
        self.write(0xE67CCC, 0)  # Optional reset path, unrelated to actor callbacks.
        self.write(PLAYER + PLAYER_ACTOR, ACTOR)
        self.write(ACTOR, ACTOR_VTABLE)
        self.write(ACTOR_VTABLE + 0x23C, SET_PARTICLES)
        self.write(ACTOR_VTABLE + 0x98, SET_PITCH)
        vtables = [FIRST_VTABLE, 0x9D10C8, 0x9D1108, 0x9D1148,
                   0x9D1148, 0x9D11C8, 0x9D1188]
        for mode, table in enumerate(vtables):
            camera = CAMERA_BASE + mode * 0x100
            self.write(CAMERAS + mode * 4, camera)
            self.write(camera, table)
        for address in (SET_PARTICLES, SET_PITCH, FREE_CAMERA_RESET):
            self.uc.mem_write(address, b'\xc2\x04\x00')  # Synthetic thiscall ret 4.
        # Only the free-camera numeric reset is stubbed; first-person callbacks
        # and the mode dispatcher execute the original, unmodified instructions.
        self.uc.hook_add(UC_HOOK_CODE, self.record)

    def write(self, address, value):
        self.uc.mem_write(address, struct.pack('<I', value))

    def read(self, address):
        return struct.unpack('<I', self.uc.mem_read(address, 4))[0]

    def record(self, uc, address, size, data):
        if address in (SET_PARTICLES, SET_PITCH):
            self.events.append({
                'method': 'ShowParticlesWhenInvisible' if address == SET_PARTICLES else 'SetPitch',
                'this': hex(uc.reg_read(UC_X86_REG_ECX)),
                'argument_bits': self.read(uc.reg_read(UC_X86_REG_ESP) + 4),
                'mode_during_callback': self.read(MODE),
            })
        elif address == LOCK_QUERY:
            # The dispatcher queries this unrelated character restriction before
            # camera transitions. Supply a controlled result and return normally.
            uc.reg_write(UC_X86_REG_EAX, self.lock_value)
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EIP, self.read(esp))
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
        elif address == 0x5425B0:
            uc.reg_write(UC_X86_REG_EIP, FREE_CAMERA_RESET)

    def call(self, address, this=CAMERA_BASE, arg=0):
        self.write(STACK, STOP)
        self.write(STACK + 4, arg)
        self.uc.reg_write(UC_X86_REG_ESP, STACK)
        self.uc.reg_write(UC_X86_REG_ECX, this)
        preserved = {UC_X86_REG_EBP: 0x456789AB,
                     UC_X86_REG_EBX: 0x12345678, UC_X86_REG_ESI: 0x23456789,
                     UC_X86_REG_EDI: 0x3456789A}
        for register, value in preserved.items():
            self.uc.reg_write(register, value)
        self.uc.emu_start(address, STOP, count=2000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == STOP, 'Unexpected control flow or instruction limit'
        assert self.uc.reg_read(UC_X86_REG_ESP) == STACK + 8, 'Unexpected stack cleanup'
        for register, value in preserved.items():
            assert self.uc.reg_read(register) == value, 'Callee-saved register changed'


def main():
    if not __debug__:
        raise SystemExit('Run without -O: assertions are the verification checks.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    data = args.executable.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit('Unsupported executable SHA256: ' + actual)
    pe = pefile.PE(data=data)
    assert pe.OPTIONAL_HEADER.ImageBase == BASE
    image = pe.get_memory_mapped_image()
    u32 = lambda address: struct.unpack_from('<I', image, address - BASE)[0]
    assert u32(FIRST_VTABLE + 0x38) == FIRST_ENTER
    assert u32(FIRST_VTABLE + 0x3C) == FIRST_LEAVE
    for table in (0x9D10C8, 0x9D1108, 0x9D1148, 0x9D1188, 0x9D11C8):
        assert u32(table + 0x38) == u32(table + 0x3C) == 0x5D7540

    cases = []
    f = Fixture(image)
    f.write(MODE, 1)
    f.write(PLAYER + PLAYER_ACTOR, 0)
    f.call(SWITCH, arg=0)
    assert f.read(MODE) == 0 and not f.events
    cases.append({'case': 'enter_before_actor_exists', 'events': list(f.events), 'mode_after': 0})
    f.write(PLAYER + PLAYER_ACTOR, ACTOR)
    f.call(FIRST_ENTER)
    assert f.events == [{'method': 'ShowParticlesWhenInvisible', 'this': hex(ACTOR),
                         'argument_bits': 1, 'mode_during_callback': 0}]
    cases.append({'case': 'entry_with_actor_present', 'events': list(f.events)})

    f = Fixture(image)
    f.write(MODE, 0)
    f.write(CAMERA_BASE + 0x48, PLAYER)
    f.call(SWITCH, arg=1)
    assert f.read(MODE) == 1 and f.read(CAMERA_BASE + 0x48) == 0
    f.call(SWITCH, arg=0)
    assert f.read(MODE) == 0
    assert [(x['method'], x['argument_bits'], x['mode_during_callback']) for x in f.events] == [
        ('ShowParticlesWhenInvisible', 0, 0), ('SetPitch', 0, 0),
        ('ShowParticlesWhenInvisible', 1, 1)]
    cases.append({'case': 'first_other_first_cycle', 'events': list(f.events), 'mode_after': 0})

    f = Fixture(image)
    f.write(LOCAL_PLAYER, 0)
    f.call(FIRST_ENTER)
    f.call(FIRST_LEAVE)
    assert not f.events
    cases.append({'case': 'null_local_player_callbacks', 'events': []})

    f = Fixture(image)
    f.write(MODE, 1)
    f.call(SWITCH, arg=2)
    assert f.read(MODE) == 2 and not f.events
    cases.append({'case': 'other_camera_to_other_camera', 'events': [], 'mode_after': 2})

    f = Fixture(image)
    f.write(MODE, 0)
    f.write(LOCAL_CHARACTER, HEAP + 0xA000)
    f.lock_value = 70
    f.call(SWITCH, arg=1)
    assert f.read(MODE) == 0 and not f.events
    cases.append({'case': 'original_character_restriction_preserved', 'events': [], 'mode_after': 0})

    print(json.dumps({'executable_sha256': actual, 'verified': True,
                      'scope': 'Original x86 camera control flow; graphics calls are recording stubs, no rendered-game claim',
                      'cases': cases}, indent=2))


if __name__ == '__main__':
    main()
