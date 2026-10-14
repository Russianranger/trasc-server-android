#!/usr/bin/env python3
"""Run the unchanged PE32 fixture as eqgame.exe in a disposable CI prefix.

This wrapper changes registry settings only when the isolated fixture requests
wineboot. It is never installed in an APK or an existing player prefix.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

WINE = ['/usr/local/bin/box64', '/opt/wine/bin/wine']
GLOBAL = r'HKCU\Software\Wine\X11 Driver'
APP = r'HKCU\Software\Wine\AppDefaults\eqgame.exe\X11 Driver'


def main():
    arguments = sys.argv[1:]
    if not arguments:
        return 2
    if arguments[0] == 'wineboot':
        status = subprocess.run([*WINE, *arguments]).returncode
        if status:
            return status
        for variable, key in (('TRASC_FIXTURE_GLOBAL_GRAB', GLOBAL),
                              ('TRASC_FIXTURE_APP_GRAB', APP)):
            value = os.environ.get(variable)
            if value:
                if value not in ('N', 'Y'):
                    raise ValueError('Invalid disposable-prefix GrabPointer control')
                subprocess.run([*WINE, 'reg', 'add', key, '/v', 'GrabPointer',
                                '/t', 'REG_SZ', '/d', value, '/f'], check=True)
        receipt = {'fixture_only': True, 'process_name': 'eqgame.exe', 'keys': {}}
        for key in (GLOBAL, APP):
            values = {}
            for name in ('GrabPointer', 'UseXInput2', 'UseTakeFocus', 'UseXVidMode'):
                query = subprocess.run([*WINE, 'reg', 'query', key, '/v', name],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True)
                if query.returncode not in (0, 1):
                    raise RuntimeError('Disposable-prefix registry read failed')
                match = re.search(r'\b' + name + r'\s+(REG_\w+)\s+([^\r\n]*)', query.stdout)
                values[name] = {'present': bool(match), 'type': match[1] if match else None,
                                'value': match[2].strip() if match else None,
                                'returncode': query.returncode}
            receipt['keys'][key] = values
        path = Path(os.environ['TRASC_FIXTURE_CONFIGURATION'])
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        return 0
    # Exercise precisely the launcher's per-eqgame.exe Wine/Box64 selection.
    for index, value in enumerate(arguments):
        if value.lower() == r'd:\cursor-probe.exe':
            directory = Path(os.environ['WINEPREFIX']) / 'dosdevices' / 'd:'
            shutil.copyfile(directory / 'cursor-probe.exe', directory / 'eqgame.exe')
            arguments[index] = r'D:\eqgame.exe'
    os.execvpe(WINE[0], [*WINE, *arguments], os.environ)


if __name__ == '__main__':
    sys.exit(main())
