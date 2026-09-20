"""Auditable, idempotent server patch for observing managed ferry passengers."""
import hashlib
import json
from pathlib import Path
import shutil

FEATURE = 'TRASC_FERRY_PASSENGER_V1'
INCLUDE = '#include "client.h"\n'
ADDED_INCLUDE = '#include "eq_server_ferry.h"\n'
ANCHOR = '\tbool\ton_boat = (ppu->vehicle_id != 0);\n'
CALL = '''\n\t// TRASC_FERRY_PASSENGER_V1: observe only explicitly managed ferries.
\tTrascFerry::RecordPassenger(*this,
\t\ton_boat ? entity_list.GetMob(ppu->vehicle_id) : nullptr, ppu->vehicle_id,
\t\tppu->x_pos, ppu->y_pos, ppu->z_pos, EQ12toFloat(ppu->heading));
'''
Z_ANCHOR = '\tm_CurrentWayPoint.z = GetFixedZ(dest);'
Z_FIXED = '''\t// TRASC_FERRY_PASSENGER_V1: a managed ship uses its fixed waterline.
\tif (!(GetIsBoat() && GetEntityVariable("trasc_ferry_managed") == "1")) {
\t\tm_CurrentWayPoint.z = GetFixedZ(dest);
\t}'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(server):
    """Keep the original source, and reject edits to an already patched file."""
    server = Path(server)
    source = server/'zone/client_packet.cpp'
    header = server/'zone/eq_server_ferry.h'
    marker = server/'zone/trasc-ferry-patch.json'
    original = server/'zone/client_packet.cpp.trasc-ferry-original'
    waypoints = server/'zone/waypoints.cpp'
    old_waypoints = server/'zone/waypoints.cpp.trasc-ferry-original'
    bundled = Path(__file__).with_name('eq_server_ferry.h')
    if any(p.is_symlink() for p in (source, header, marker, original, waypoints, old_waypoints)):
        raise ValueError('Ferry server support cannot follow source symlinks')
    before = source.read_bytes()
    code = before.decode('utf-8')
    before_waypoints = waypoints.read_bytes()
    waypoint_code = before_waypoints.decode('utf-8')
    if marker.exists():
        record = json.loads(marker.read_text())
        if digest(source) != record['patched'] or digest(original) != record['original']:
            raise ValueError('Ferry-patched server source changed. Import a clean source before rebuilding.')
        if digest(waypoints) != record['waypoints'] or digest(old_waypoints) != record['original_waypoints']:
            raise ValueError('Ferry-patched waypoint source changed. Import a clean source before rebuilding.')
        if not header.is_file() or digest(header) != record['header']:
            raise ValueError('Ferry server header changed. Import a clean source before rebuilding.')
        if digest(bundled) != record['header']:
            raise ValueError('Ferry support changed; import a clean source before rebuilding.')
        return record
    if original.exists() or header.exists() or old_waypoints.exists() or FEATURE in code or FEATURE in waypoint_code or ADDED_INCLUDE in code:
        raise ValueError('Unrecognized or interrupted ferry source patch; import a clean source')
    if code.count(INCLUDE) != 1 or code.count(ANCHOR) != 1:
        raise ValueError('This server source has an unsupported passenger movement handler')
    if waypoint_code.count(Z_ANCHOR) != 1:
        raise ValueError('This server source has an unsupported waypoint height handler')
    changed = code.replace(INCLUDE, INCLUDE+ADDED_INCLUDE).replace(ANCHOR, ANCHOR+CALL)
    original.write_bytes(before)
    try:
        old_waypoints.write_bytes(before_waypoints)
        shutil.copyfile(bundled, header)
        source.write_text(changed)
        waypoints.write_text(waypoint_code.replace(Z_ANCHOR, Z_FIXED))
        record = dict(feature=FEATURE, original=digest(original), patched=digest(source), header=digest(header),
                      waypoints=digest(waypoints), original_waypoints=digest(old_waypoints))
        marker.write_text(json.dumps(record, indent=2)+'\n')
    except BaseException:
        source.write_bytes(before)
        waypoints.write_bytes(before_waypoints)
        header.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        original.unlink(missing_ok=True)
        old_waypoints.unlink(missing_ok=True)
        raise
    return record


def deployed(engine):
    """Require the feature in the deployed build and the exact deployed zone ELF."""
    root = engine.work/'server/bin'
    try:
        record = json.loads((root/'build-info.json').read_text())
        support = record['ferry_support']
        return (support['feature'] == FEATURE and
                support['header'] == digest(Path(__file__).with_name('eq_server_ferry.h')) and
                record['zone_sha256'] == digest(root/'zone'))
    except (KeyError, ValueError, OSError, TypeError):
        return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('server')
    print(json.dumps(prepare(parser.parse_args().server), indent=2))
