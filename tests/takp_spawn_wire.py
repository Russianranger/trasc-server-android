"""Qualify real Mac spawn encoding without a client or an RPC endpoint.

Links the common library already produced by the production server build and
independently decrypts/inflates the encoded payload. Literal client wire offsets
avoid accepting an architecture-dependent C++ layout merely because the same
layout is used by both the encoder and its test decoder.
"""
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import zlib


MASK64 = (1 << 64) - 1


def rotate_right(value, bits):
    return ((value >> bits) | (value << (64 - bits))) & MASK64


def decode_wire(payload, count):
    if not 8 <= len(payload) <= 8192:
        raise RuntimeError('Mac spawn encoder produced an invalid payload size')
    clear = bytearray(payload)
    crypt = 0
    words = len(payload) // 8
    for i in range(words):
        word = struct.unpack_from('<Q', payload, i * 8)[0]
        word = rotate_right((word + crypt) & MASK64, 14)
        word = rotate_right((word - 0x659365e7) & MASK64, 29)
        struct.pack_into('<Q', clear, i * 8, word)
        crypt = (crypt + word - 0x659365e7) & MASK64
    first = clear[:8]
    middle = (words // 2) * 8
    clear[:8] = clear[middle:middle + 8]
    clear[middle:middle + 8] = first
    inflater = zlib.decompressobj()
    decoded = inflater.decompress(clear, count * 224 + 1)
    if (len(decoded) != count * 224 or not inflater.eof or
            inflater.unused_data or inflater.unconsumed_tail):
        raise RuntimeError('Mac spawn payload did not inflate to exact 224-byte client records')
    return decoded


def check_rows(decoded, count, start):
    for i in range(count):
        n = start + i
        row = decoded[i * 224:(i + 1) * 224]
        values = {
            'id': struct.unpack_from('<H', row, 76)[0],
            'bodytype': struct.unpack_from('<h', row, 78)[0],
            'hp': struct.unpack_from('<h', row, 80)[0],
            'race': struct.unpack_from('<H', row, 84)[0],
            'npc': row[86], 'class': row[87], 'gender': row[88],
            'level': row[89], 'invisible': row[90], 'stand': row[93],
            'x': struct.unpack_from('<h', row, 9)[0],
            'y': struct.unpack_from('<h', row, 7)[0],
            'z': struct.unpack_from('<h', row, 11)[0],
            'heading': row[5], 'size': struct.unpack_from('<f', row, 28)[0],
            'walk': struct.unpack_from('<f', row, 32)[0],
            'run': struct.unpack_from('<f', row, 36)[0],
            'name': row[127:191].split(b'\0', 1)[0].decode('ascii'),
        }
        expected = {
            'id': 400 + n, 'bodytype': 1, 'hp': 100,
            'race': 3 if n % 2 else 60, 'npc': 1, 'class': 1,
            'gender': n % 2, 'level': 1 + n % 60, 'invisible': 0,
            'stand': 100, 'x': 500 + n, 'y': 700 + n,
            'z': (-120 + n) * 10, 'heading': n % 256,
            'size': 6.0, 'walk': struct.unpack('<f', struct.pack('<f', .7))[0],
            'run': 1.25, 'name': 'Paineel_fixture_' + str(n),
        }
        if values != expected:
            raise RuntimeError('Mac spawn client fields differ: ' + json.dumps(values))


def ninja_variables(text, target):
    match = re.search(r'^build ' + re.escape(target) + r':[^\n]*\n((?:  [^\n]*\n)*)', text, re.M)
    if not match:
        raise RuntimeError('Production Ninja build lacks ' + target)
    return dict(re.findall(r'^  ([A-Z_]+) = (.*)$', match[1], re.M))


def qualify_spawn_wire(build_dir, source, output):
    build_dir, source, output = map(lambda path: Path(path).resolve(),
                                    (build_dir, source, output))
    output.mkdir(parents=True, exist_ok=True)
    ninja = (build_dir / 'build.ninja').read_text()
    compile_vars = ninja_variables(ninja, 'common/CMakeFiles/common.dir/patches/mac.cpp.o')
    link_vars = ninja_variables(ninja, 'bin/world')
    cache = (build_dir / 'CMakeCache.txt').read_text()
    compiler = re.search(r'^CMAKE_CXX_COMPILER:FILEPATH=(.*)$', cache, re.M)
    if not compiler:
        raise RuntimeError('Production C++ compiler is not recorded')
    binary = output / 'takp-spawn-wire-probe'
    cpp = Path(__file__).with_name('takp_spawn_wire_probe.cpp')
    command = [compiler[1]]
    for key in ('DEFINES', 'FLAGS', 'INCLUDES'):
        command += shlex.split(compile_vars[key])
    command += ['-I', str(source), str(cpp), '-o', str(binary)]
    command += shlex.split(link_vars['LINK_LIBRARIES'])
    try:
        subprocess.run(command, cwd=build_dir, check=True, capture_output=True, text=True,
                       timeout=180)
        completed = subprocess.run([str(binary), str(source / 'utils/patches/patch_Mac.conf'),
                                    str(output)], cwd=build_dir, check=True,
                                   capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as error:
        raise RuntimeError('Native Mac spawn wire probe failed:\n' +
                           (error.stdout + error.stderr)[-8000:]) from error
    packet_sizes = {}
    for count in (1, 56, 100):
        payload = (output / ('bulk-' + str(count) + '.bin')).read_bytes()
        check_rows(decode_wire(payload, count), count, 0)
        packet_sizes[str(count)] = len(payload)
    total_individual_bytes = 0
    for i in range(156):
        payload = (output / ('new-' + str(i) + '.bin')).read_bytes()
        check_rows(decode_wire(payload, 1), 1, i)
        total_individual_bytes += len(payload)
    report = {'format': 1, 'wire_spawn_bytes': 224, 'bulk_packet_sizes': packet_sizes,
              'individual_new_spawn_packets': 156,
              'individual_encrypted_bytes': total_individual_bytes,
              'native_probe_stdout': completed.stdout.strip(),
              'result': 'passed'}
    (output / 'spawn-wire.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qualify_spawn_wire(args.build, args.source, args.output), indent=2))
