"""CI-only observations around the unmodified Wine startup success gate.

Runs the production entry point with its original return-code/timeout checks.
Never retries or converts SIGKILL/nonzero exits into success. Android does not
package or invoke this test wrapper.
"""
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, '/opt/trasc-client')
import client_runner

original_run = client_runner.Supervisor.run


def memory_counters():
    result = {}
    for name in ('/sys/fs/cgroup/memory.events', '/sys/fs/cgroup/memory.current',
                 '/sys/fs/cgroup/memory/memory.failcnt', '/proc/meminfo'):
        try: result[name] = Path(name).read_text()[:4096]
        except OSError: pass
    return result


def observed_run(self, args, timeout=180, env=None, label='Wine setup'):
    if label != '32-bit Wine check':
        return original_run(self, args, timeout=timeout, env=env, label=label)
    # Limit additional Wine tracing to the small PE32 cmd /c exit 0 probe.
    traced = dict(env or self.env)
    traced['WINEDEBUG'] = traced.get('WINEDEBUG', '') + ',trace+process,trace+thread'
    before = len(self.children)
    done = threading.Event()
    evidence = {'label':label, 'before':memory_counters(), 'samples':[]}
    started = time.monotonic()

    def observe():
        while not done.wait(.1):
            for child in list(self.children)[before:before+4]:
                sample = {'seconds':round(time.monotonic()-started, 3), 'pid':child.pid}
                for name in ('stat', 'status', 'wchan', 'syscall'):
                    try: sample[name] = Path('/proc',str(child.pid),name).read_text()[:4096]
                    except OSError: pass
                evidence['samples'].append(sample)
            if len(evidence['samples']) > 256: del evidence['samples'][:-256]

    thread = threading.Thread(target=observe, daemon=True)
    thread.start()
    try:
        # Keep the actual production spawn/wait logic, timeout and exit==0 gate.
        return original_run(self, args, timeout=timeout, env=traced, label=label)
    finally:
        done.set();thread.join(timeout=1)
        evidence.update(after=memory_counters(), seconds=round(time.monotonic()-started,3),
                        children=[{'pid':p.pid,'returncode':p.returncode} for p in self.children[before:before+4]])
        # Separate cold and warm reports, so a later phase cannot hide evidence.
        report=client_runner.LOGS/('wine32-exit-'+self.status.get('prefix_update','unknown')+'.json')
        report.write_text(json.dumps(evidence,indent=2))


client_runner.Supervisor.run = observed_run
if __name__ == '__main__': client_runner.main()
