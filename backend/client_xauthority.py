"""Private X11 authorization for the launcher's single-owner display sessions.

Android can deny the hard links used by xauth's shared-file lock. Each launch
already owns a fresh session directory, so write its one Xau-format record
directly and atomically instead. This retains cookie authentication; it does
not enable unauthenticated X11 connections or put the cookie in command logs.
"""
import os
from pathlib import Path
import secrets
import socket
import struct
import tempfile


def write_xauthority(path, display_number):
    """Replace a private authority file with a fresh local MIT cookie (0600)."""
    if type(display_number) is not int or not 0 <= display_number <= 65535:
        raise ValueError('Invalid local X11 display number')
    hostname = os.fsencode(socket.gethostname())
    if not hostname or len(hostname) > 65535:
        raise ValueError('Invalid local X11 hostname')
    fields = (hostname, str(display_number).encode('ascii'),
              b'MIT-MAGIC-COOKIE-1', secrets.token_bytes(16))
    # Xau files contain big-endian CARD16 family/lengths; FamilyLocal is 256.
    record = struct.pack('>H', 256) + b''.join(
        struct.pack('>H', len(field)) + field for field in fields)
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.Xauthority-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(record)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
