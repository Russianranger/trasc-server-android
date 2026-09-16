"""CI sink: enforce the same wire contract with a real-time playback head.

No audio device exists in CI. This captures samples from real ALSA/Wine and
models bounded Android acceptance; it is not evidence of audible Thor playback.
"""
import json
from pathlib import Path
import socket
import struct
import threading
import time


class Receiver:
    def __init__(self, path):
        self.path = Path(path); self.path.unlink(missing_ok=True)
        self.server = socket.socket(socket.AF_UNIX); self.server.bind(str(path)); self.server.listen(8)
        self.server.settimeout(.2); self.closed = False; self.reports = []; self.errors = []; self.clients = []
        self.thread = threading.Thread(target=self.accept, daemon=True); self.thread.start()

    def accept(self):
        while not self.closed:
            try: client, _ = self.server.accept()
            except socket.timeout: continue
            except OSError: break
            self.clients.append(client)
            threading.Thread(target=self.stream, args=(client,), daemon=True).start()

    def stream(self, client):
        report = {'frames': 0, 'nonzero_samples': 0, 'left_nonzero': 0, 'right_nonzero': 0, 'starts': 0, 'resets': 0}
        self.reports.append(report)
        def recv(size):
            data = b''
            while len(data) < size:
                more = client.recv(size-len(data))
                if not more: raise EOFError()
                data += more
            return data
        def word(): return struct.unpack('<I', recv(4))[0]
        def reply(value): client.sendall(struct.pack('<I', value))
        try:
            assert tuple(word() for _ in range(4)) == (0x50414c54, 1, 48000, 2)
            capacity = word(); assert 64 <= capacity <= 48000
            reply(0); running = False; played = queued = 0; last = time.monotonic()
            while True:
                command = word(); now = time.monotonic()
                if running: played = min(queued, played+(now-last)*48000)
                last = now
                if command == 1:
                    running = True; report['starts'] += 1; reply(0)
                elif command == 2:
                    running = False; queued = played = 0; reply(0)
                elif command == 3: reply(int(played) & 0xffffffff)
                elif command == 4:
                    frames = word(); assert 0 < frames <= 4096
                    data = recv(frames*4)
                    accepted = max(0, min(frames, capacity-int(queued-played)))
                    samples = struct.unpack('<'+'h'*accepted*2, data[:accepted*4])
                    report['frames'] += accepted
                    report['nonzero_samples'] += sum(v != 0 for v in samples)
                    report['left_nonzero'] += sum(v != 0 for v in samples[::2])
                    report['right_nonzero'] += sum(v != 0 for v in samples[1::2])
                    queued += accepted; reply(accepted)
                elif command == 5:
                    running = False; queued = played = 0; report['resets'] += 1; reply(0)
                else: raise AssertionError(('unknown command', command))
        except EOFError: pass
        except Exception as error:
            if not self.closed: self.errors.append(str(error))
        finally: client.close()

    def snapshot(self): return {'streams': self.reports, 'errors': self.errors}

    def close(self):
        self.closed = True; self.server.close()
        for client in self.clients:
            try: client.shutdown(socket.SHUT_RDWR); client.close()
            except OSError: pass
        self.thread.join(1); self.path.unlink(missing_ok=True)
