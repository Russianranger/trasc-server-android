"""Recognize the five-part PEQ seed without executing its client SOURCE script."""
from pathlib import PurePosixPath
import re


PARTS = tuple('create_tables_' + name + '.sql' for name in
              ('content', 'login', 'player', 'state', 'system'))
MAX_MANIFEST_BYTES = 64 * 1024


def is_wrapper(identifier):
    return PurePosixPath(identifier.partition('!')[2] or identifier).name.lower() in (
        'create_all_tables.sql', 'create_all_tables.sql.gz')


def parse_manifest(stream):
    data = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError('PEQ bundle manifest is too large')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('PEQ bundle manifest must be UTF-8') from None
    # Only comments and the known SOURCE list belong in this wrapper. It is
    # never handed to the MariaDB client, which could otherwise read host paths.
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = '\n'.join(line for line in text.splitlines()
                     if not re.match(r'^\s*(?:--(?:\s|$)|#)', line))
    names = []
    for statement in text.split(';')[:-1]:
        match = re.fullmatch(r'\s*source\s+([^\s;]+)\s*', statement, flags=re.I)
        if not match:
            raise ValueError('PEQ bundle manifest contains unsupported SQL or commands')
        name = match.group(1)
        if PurePosixPath(name).name != name or '\\' in name or ':' in name:
            raise ValueError('PEQ bundle SOURCE paths must name files in the same folder')
        names.append(name)
    if text.split(';')[-1].strip():
        raise ValueError('PEQ bundle manifest contains an incomplete SOURCE command')
    if len(names) != len(set(names)):
        raise ValueError('PEQ bundle manifest repeats a SQL part')
    if tuple(names) != PARTS:
        raise ValueError('PEQ bundle must list content, login, player, state and system in that order')
    return names


def component_ids(identifier, names):
    archive, separator, member = identifier.partition('!')
    parent = PurePosixPath(member if separator else archive).parent
    prefix = archive + '!' if separator else ''
    return [prefix + str(parent / name) for name in names]
