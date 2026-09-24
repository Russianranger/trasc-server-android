"""Cancellation must stop extractor descendants before their stage is removed."""
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engine import Engine


@unittest.skipUnless(hasattr(os, 'fork'), 'POSIX process groups required')
class EngineProcessTests(unittest.TestCase):
    def test_cancel_kills_writing_child_even_when_wrapper_exits(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = Engine(temp)
            ready, heartbeat = Path(temp) / 'ready', Path(temp) / 'heartbeat'
            script = '''import os,signal,time
from pathlib import Path
pid=os.fork()
if pid==0:
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    Path('ready').write_text(str(os.getpid()))
    while True:
        with open('heartbeat','ab') as f: f.write(b'x')
        time.sleep(.02)
while True: time.sleep(1)
'''
            errors = []
            def run():
                try: engine.run([sys.executable, '-c', script], timeout=10)
                except Exception as error: errors.append(error)
            runner = threading.Thread(target=run)
            runner.start()
            child = None
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline: time.sleep(.02)
                self.assertTrue(ready.exists(), 'Extractor child started')
                child = int(ready.read_text())
                engine.cancel.set()
                runner.join(7)
                self.assertFalse(runner.is_alive(), 'Cancellation must finish')
                self.assertEqual(len(errors), 1)
                self.assertIn('cancel', str(errors[0]).lower())
                size = heartbeat.stat().st_size
                time.sleep(.12)
                self.assertEqual(heartbeat.stat().st_size, size, 'Child continued writing after cancellation')
                self.assertIsNone(engine.command)
            finally:
                engine.cancel.set()
                if child:
                    try: os.kill(child, signal.SIGKILL)
                    except ProcessLookupError: pass
                runner.join(7)


if __name__ == '__main__': unittest.main()
