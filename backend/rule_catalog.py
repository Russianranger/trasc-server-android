"""Rule metadata from the user's server source; no C++ is evaluated."""
import ast
from decimal import Decimal, InvalidOperation
import re
import struct

XP_NAMES = ('ExpMultiplier', 'FinalExpMultiplier', 'AAExpMultiplier',
            'GroupExpMultiplier', 'RaidExpMultiplier', 'FinalRaidExpMultiplier')
KNOWN = {'Zone:StateSavingOnShutdown': {'type': 'bool'}}
KNOWN.update({'Character:' + n: {'type': 'real', 'min': '0'} for n in XP_NAMES})
KNOWN['Character:RaidExpMultiplier']['max'] = '1'


def metadata(name, kind, description='', default=None, source='database'):
    rule = {'type': kind, 'description': description, 'source': source}
    if default is not None:
        rule['default'] = default
    if kind == 'int':
        rule.update(min='-2147483648', max='2147483647', bounds_source='32-bit server integer')
    elif kind == 'real':
        rule.update(min='-3.4028234663852886e38', max='3.4028234663852886e38', bounds_source='32-bit server real number')
    if name in KNOWN:
        rule.update(KNOWN[name])
        if name.startswith('Character:'):
            rule['bounds_source'] = 'Nonnegative XP multiplier' if not name.endswith(':RaidExpMultiplier') else 'Raid penalty fraction (0–1)'
    if name == 'Character:DeathExpLossMultiplier' and kind == 'int' and '10=11%' in description:
        rule.update(min='0', max='10', bounds_source='Server death-loss table index (0–10)')
    # Only explicit constraints are extracted. "Minimum number of mobs" describes
    # the setting, not a minimum permitted input. Negative disable sentinels survive.
    match = re.search(r'cannot go below\s+(-?\d+(?:\.\d+)?)', description, re.I)
    if match and kind in ('int', 'real'):
        rule.update(min=match[1], bounds_source='Documented in server rule description')
    match = re.search(r'(?:valid|allowed) (?:range|values)\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*(?:to|through|\.\.|–)\s*(-?\d+(?:\.\d+)?)', description, re.I)
    if match and kind in ('int', 'real'):
        rule.update(min=match[1], max=match[2], bounds_source='Documented in server rule description')
    return rule


def parse_source(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    quoted = r'"(?:\\.|[^"\\])*"'
    pattern = re.compile(r'^\s*RULE_(INT|REAL|BOOL|STRING)\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(' + quoted + r'|[^,\n]+)\s*,\s*((?:' + quoted + r'\s*)+)\)', re.M)
    result = {}
    for m in pattern.finditer(text):
        kind, category, key, default, notes = m.groups()
        name = category + ':' + key
        try:
            description = ''.join(ast.literal_eval(s) for s in re.findall(quoted, notes))
            default = ast.literal_eval(default) if kind == 'STRING' else default.strip()
            if kind == 'REAL':
                default = re.sub(r'[fF]$', '', default)
            if kind in ('INT', 'REAL'):
                Decimal(default)  # Skip expression defaults instead of executing them.
        except (ValueError, SyntaxError, InvalidOperation):
            default = None
            description = notes
        result[name] = metadata(name, kind.lower(), description, default, 'imported server source')
    return result


def validate_value(name, value, spec, max_length=128):
    value = str(value).lower() if isinstance(value, bool) else str(value)
    if '\x00' in value or len(value) > max_length:
        raise ValueError(f'{name}: value must be at most {max_length} characters without NUL bytes')
    kind = spec['type']
    if kind == 'bool':
        if value.lower() not in ('true', 'false', '0', '1'):
            raise ValueError(f'{name}: choose true or false')
        return 'true' if value.lower() in ('true', '1') else 'false'
    if kind in ('int', 'real'):
        if kind == 'int' and not re.fullmatch(r'[+-]?\d+', value.strip()):
            raise ValueError(f'{name}: enter a whole number')
        try:
            number = Decimal(value)
        except InvalidOperation:
            raise ValueError(f'{name}: enter a valid number') from None
        if not number.is_finite():
            raise ValueError(f'{name}: enter a finite number')
        low, high = spec.get('min'), spec.get('max')
        if low is not None and number < Decimal(low):
            raise ValueError(f'{name}: {value} is below the minimum {low}')
        if high is not None and number > Decimal(high):
            raise ValueError(f'{name}: {value} is above the maximum {high}')
        if kind == 'real':
            try:
                converted = struct.unpack('f', struct.pack('f', float(number)))[0]
                if number and converted == 0:
                    raise ValueError(f'{name}: magnitude is too small for the server’s 32-bit real number')
            except OverflowError:
                raise ValueError(f'{name}: value exceeds the server’s real-number range') from None
        return value.strip()  # Preserve tiny multipliers and user precision.
    return value
