"""Build one test TU with the actual upstream bodies and production overlay.

The retained excerpt is GPL-2.0 source, not proprietary client machine code.
Only pointer width is widened for the optional 64-bit host fixture.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import client_mouse


def generate(output):
    folder = Path(__file__).resolve().parent
    source = (folder / 'fixtures/checksum_upstream.cpp').read_text()
    changed = client_mouse.checksum_overlay(source)
    units = []
    for prefix, text in [('legacy_', source), ('patched_', changed)]:
        start = text.index('int __cdecl memcheck0(unsigned char *buffer, int count)\n{')
        end = text.index('\nint __cdecl memcheck2(', start)
        body = text[start:end].replace('memcheck0(', prefix+'memcheck0(').replace('memcheck1(', prefix+'memcheck1(')
        body = body.replace('unsigned int b=(int) &buffer[i];', 'uintptr_t b=reinterpret_cast<uintptr_t>(&buffer[i]);')
        units.append(body)
    harness = (folder / 'spell_checksum.cpp').read_text()
    Path(output).write_text(harness.replace('// UPSTREAM_FUNCTION_BODIES', '\n'.join(units)))


if __name__ == '__main__':
    generate(sys.argv[1])
