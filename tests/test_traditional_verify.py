import sys
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import traditional_verify as verify


def elf(path, machine=183, interpreter=verify.INTERPRETER, encoding=1):
    name = interpreter.encode() + b'\0'
    ident = b'\x7fELF\x02' + bytes([encoding]) + b'\x01' + bytes(9)
    header = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    program = struct.pack('<IIQQQQQQ', 3, 0, 120, 0, 0, len(name), len(name), 1)
    path.write_bytes(header + program + name)
    path.chmod(0o755)


def command(args):
    if args[0] == 'ldd':
        return ('\tlibc.so.6 => /lib/aarch64-linux-gnu/libc.so.6\n'
                '\tlibluajit-5.1.so.2 => /lib/aarch64-linux-gnu/libluajit-5.1.so.2\n'
                '\tlibperl.so.5.36 => /lib/aarch64-linux-gnu/libperl.so.5.36\n'
                '\tlibcrypto.so.3 => /lib/aarch64-linux-gnu/libcrypto.so.3\n')
    if args[0] == 'readelf': return 'Dynamic section: NEEDED [libc.so.6]\n'
    if args == ['openssl', 'version']: return 'OpenSSL 3.0.22 16 Jun 2026\n'
    if '-providers' in args:
        return 'Providers:\n  default\n    status: active\n  legacy\n    status: active\n'
    if '-cipher-algorithms' in args: return '  { 1.3.14.3.2.7, DES-CBC } @ legacy\n'
    raise AssertionError(args)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binaries = self.root / 'bin'; self.binaries.mkdir()
        self.evidence = self.root / 'evidence'
        for name in verify.BINARIES: elf(self.binaries / name)

    def test_validates_nine_without_executing_server(self):
        with patch.object(verify, '_command', side_effect=command) as runner:
            report = verify.verify(self.binaries, self.evidence)
        self.assertEqual(set(report['binaries']), set(verify.BINARIES))
        self.assertTrue(report['providers']['des_cbc'])
        self.assertEqual(json.loads((self.evidence / 'binary-verification.json').read_text()), report)
        self.assertTrue(all(call.args[0][0] in ('ldd', 'readelf', 'openssl') for call in runner.call_args_list))

    def test_rejects_wrong_architecture_before_loader_invocation(self):
        elf(self.binaries / 'world', machine=62)
        with patch.object(verify, '_command') as runner:
            with self.assertRaisesRegex(ValueError, 'ARM64'): verify.verify(self.binaries, self.evidence)
        runner.assert_not_called()
        self.assertFalse((self.evidence / 'binary-verification.json').exists())

    def test_rejects_wrong_interpreter_and_byte_order(self):
        for kwargs in ({'interpreter': '/lib64/ld-linux-x86-64.so.2'}, {'encoding': 2}):
            with self.subTest(kwargs=kwargs):
                elf(self.binaries / 'world', **kwargs)
                with self.assertRaises(ValueError): verify.inspect_elf(self.binaries / 'world')

    def test_rejects_truncated_program_headers(self):
        path = self.binaries / 'world'; path.write_bytes(path.read_bytes()[:80])
        with self.assertRaisesRegex(ValueError, 'truncated'): verify.inspect_elf(path)

    def test_rejects_symlink_binary(self):
        path = self.binaries / 'world'; path.unlink(); path.symlink_to('zone')
        with self.assertRaisesRegex(ValueError, 'regular'): verify.inspect_elf(path)

    def test_failure_removes_stale_manifest(self):
        self.evidence.mkdir(); stale = self.evidence / 'binary-verification.json'; stale.write_text('{}')
        def missing(args):
            return 'libluajit-5.1.so.2 => not found\n' if args[0] == 'ldd' else command(args)
        with patch.object(verify, '_command', side_effect=missing):
            with self.assertRaisesRegex(ValueError, 'unresolved'): verify.verify(self.binaries, self.evidence)
        self.assertFalse(stale.exists())

    def test_rejects_build_directory_runpath(self):
        def bad(args):
            return '0x0000001d (RUNPATH) Library runpath: [/work/builds/old/bin]' if args[0] == 'readelf' else command(args)
        with patch.object(verify, '_command', side_effect=bad):
            with self.assertRaisesRegex(ValueError, 'build-directory'): verify.verify(self.binaries, self.evidence)

    def test_requires_legacy_des_provider(self):
        for override in ('providers', 'ciphers'):
            with self.subTest(override=override):
                def missing(args):
                    if override == 'providers' and '-providers' in args:
                        return 'Providers:\n  default\n    status: active\n'
                    if override == 'ciphers' and '-cipher-algorithms' in args: return '  AES-128-CBC @ default\n'
                    return command(args)
                with patch.object(verify, '_command', side_effect=missing):
                    with self.assertRaisesRegex(ValueError, 'legacy'): verify.verify(self.binaries, self.evidence)
                self.assertFalse((self.evidence / 'binary-verification.json').exists())

    def test_requires_requested_parser_abi(self):
        def missing(args):
            output = command(args)
            return '\n'.join(line for line in output.splitlines() if 'libperl.so.' not in line) if args[0] == 'ldd' else output
        with patch.object(verify, '_command', side_effect=missing):
            with self.assertRaisesRegex(ValueError, 'perl'): verify.verify(self.binaries, self.evidence)
        self.assertFalse((self.evidence / 'binary-verification.json').exists())


if __name__ == '__main__': unittest.main()
