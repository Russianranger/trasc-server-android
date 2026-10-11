"""Emit fixture input through the unchanged production TRASCIN1/XFlush parser.

No XSync is performed between packets. The caller measures the actual native
consumer separately; these counters describe submitted wire packets only.
"""
import errno
import math
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import time


class TrascInputTransport:
    def __init__(self, binary, path, env, log_path, timeout=10):
        if not math.isfinite(timeout) or not 0 < timeout <= 10:
            raise ValueError('Input readiness timeout must be within 10 seconds')
        self.path = Path(path).absolute()
        if len(os.fsencode(self.path)) > 107:
            raise ValueError('Fixture socket path exceeds the Unix socket limit')
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError('Refusing to replace an existing fixture input path: ' + str(self.path))
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.mask = 0
        self.process = None
        self._socket = None
        self._socket_identity = None
        self._log = None
        self._closed = False
        self._native_decoded = None
        self._started = time.monotonic()
        self._counts = {'packets': 0, 'relative': 0, 'absolute': 0, 'buttons': 0,
                        'zero_relative': 0, 'relative_sum': [0, 0],
                        'positive_axes': [0, 0], 'negative_axes': [0, 0],
                        'wire_bytes': 0, 'writes': 0}
        try:
            self._log = self.log_path.open('wb')
            self.process = subprocess.Popen([str(Path(binary).absolute()), str(self.path)],
                                            env=dict(os.environ, **env),
                                            stdout=self._log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('TRASCIN1 fixture helper exited before readiness: ' +
                                       str(self.process.returncode))
                candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    candidate.settimeout(max(.001, min(1, deadline - time.monotonic())))
                    candidate.connect(str(self.path))
                except OSError as error:
                    candidate.close()
                    if error.errno not in (errno.ENOENT, errno.ECONNREFUSED, errno.EAGAIN):
                        raise
                    time.sleep(min(.02, max(0, deadline - time.monotonic())))
                    continue
                self._socket = candidate
                try:
                    entry = self.path.lstat()
                    if stat.S_ISSOCK(entry.st_mode):
                        self._socket_identity = (entry.st_dev, entry.st_ino)
                except FileNotFoundError:
                    pass
                hello = bytearray()
                while len(hello) < 8:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('TRASCIN1 fixture handshake timed out')
                    candidate.settimeout(min(1, remaining))
                    try:
                        chunk = candidate.recv(8 - len(hello))
                    except socket.timeout:
                        if self.process.poll() is not None:
                            raise RuntimeError('TRASCIN1 fixture exited during handshake')
                        continue
                    if not chunk:
                        raise RuntimeError('TRASCIN1 fixture disconnected during handshake')
                    hello.extend(chunk)
                if hello != b'TRASCIN1':
                    raise RuntimeError('Unsupported fixture input protocol: ' + repr(bytes(hello)))
                candidate.settimeout(3)
                return
            raise TimeoutError('TRASCIN1 fixture socket did not become ready')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _packet(event, mask):
        if len(event) == 2:
            event = (1, event[0], event[1], mask)
        if len(event) != 4 or any(not isinstance(value, int) for value in event):
            raise ValueError('Input event must contain 2 or 4 integers')
        kind, x, y, next_mask = event
        if kind not in (0, 1, 2) or not -4096 <= x <= 4096 or not -4096 <= y <= 4096 or not 0 <= next_mask <= 31:
            raise ValueError('Input event exceeds the production protocol bounds')
        return (kind, x, y, next_mask), struct.pack('!IiiI', kind, x, y, next_mask)

    def burst(self, events, fragment_sizes=None):
        """Submit motion pairs or full (type,x,y,mask) packets without pacing.

        Fragment sizes repeat over the byte stream, including packet boundaries,
        to exercise the real read_input loop rather than a replacement parser.
        """
        if self._closed or self._socket is None:
            raise RuntimeError('Fixture input transport is closed')
        fragments = tuple(fragment_sizes or ())
        if any(not isinstance(size, int) or size <= 0 for size in fragments):
            raise ValueError('Fragment sizes must be positive integers')
        packets, encoded, mask = [], [], self.mask
        for event in events:
            packet, wire = self._packet(event, mask)
            packets.append(packet)
            encoded.append(wire)
            mask = packet[3]
        payload = b''.join(encoded)
        if not payload:
            return
        if fragments:
            offset, index = 0, 0
            while offset < len(payload):
                chunk = payload[offset:offset + fragments[index % len(fragments)]]
                self._socket.sendall(chunk)
                self._counts['writes'] += 1
                offset += len(chunk)
                index += 1
        else:
            self._socket.sendall(payload)
            self._counts['writes'] += 1
        self.mask = mask
        self._counts['wire_bytes'] += len(payload)
        for kind, x, y, _ in packets:
            self._counts['packets'] += 1
            self._counts[('absolute', 'relative', 'buttons')[kind]] += 1
            if kind == 1:
                if not x and not y:
                    self._counts['zero_relative'] += 1
                for axis, value in enumerate((x, y)):
                    self._counts['relative_sum'][axis] += value
                    if value > 0:
                        self._counts['positive_axes'][axis] += 1
                    elif value < 0:
                        self._counts['negative_axes'][axis] += 1

    def motion(self, dx, dy):
        self.burst(((dx, dy),))

    def button(self, down, which=3):
        if which not in (1, 2, 3, 4, 5):
            raise ValueError('Fixture mouse button must be between 1 and 5')
        bit = 1 << (which - 1)
        mask = self.mask | bit if down else self.mask & ~bit
        self.burst(((2, 0, 0, mask),))

    def absolute(self, x, y):
        """Normalize only an explicitly free UI phase, never active look."""
        self.burst(((0, x, y, self.mask),))

    def zeros(self, count):
        if not isinstance(count, int) or not 0 <= count <= 100000:
            raise ValueError('Zero-packet count is outside fixture limits')
        self.burst((0, 0) for _ in range(count))

    def paced(self, events, interval=.016):
        """Use controller-sized deltas at a specified producer cadence."""
        if not math.isfinite(interval) or not 0 <= interval <= 1:
            raise ValueError('Fixture packet interval must be within one second')
        target = time.monotonic()
        for event in events:
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.burst((event,))
            target += interval

    def summary(self):
        return {**{key: list(value) if isinstance(value, list) else value
                   for key, value in self._counts.items()},
                'mask': self.mask, 'seconds': time.monotonic() - self._started,
                'protocol': 'TRASCIN1', 'pipeline': 'production parser; per-packet XFlush',
                'closed': self._closed,
                'native_decoded': dict(self._native_decoded) if self._native_decoded is not None else None}

    def _read_native_counts(self):
        try:
            content = self.log_path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return False
        matches = re.findall(r'Input consumer disconnected: relative=(\d+) absolute=(\d+) buttons=(\d+)', content)
        if not matches:
            return False
        self._native_decoded = dict(zip(('relative', 'absolute', 'buttons'), map(int, matches[-1])))
        return True

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._socket is not None:
            try:
                # EOF follows the parser's final XSync and button release. This
                # drains pending requests without changing normal packet pacing.
                self._socket.shutdown(socket.SHUT_WR)
                self._socket.settimeout(1)
                while self._socket.recv(256):
                    pass
            except OSError:
                pass
            finally:
                self._socket.close()
                self._socket = None
        if self.process is not None:
            # The production parser closes its socket immediately before
            # printing final counts. Await that line before terminating it.
            deadline = time.monotonic() + 1
            while not self._read_native_counts() and self.process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(.01, remaining))
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._socket_identity is not None:
            try:
                entry = self.path.lstat()
                if stat.S_ISSOCK(entry.st_mode) and (entry.st_dev, entry.st_ino) == self._socket_identity:
                    self.path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
