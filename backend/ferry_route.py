"""One managed route; XYZ, EQ heading units (512 per turn)."""
import math

ZONES = {1: 'qeynos', 98: 'erudsxing', 24: 'erudnext'}
NAME = 'TRASC_Voyager'
# Deck elevations from the collision maps: Qeynos 0, Crossing .03125,
# Erudin 20. Preserve the accepted SHIP deck-to-origin relationship.
DOCKS = {1: (319.0, 13.0, -39.5), 98: (580.0, -1772.78125, -39.5),
         24: (-443.0, 95.96875, -19.5)}
SHORE = {1: (220.0, 13.0, 4.0, 128.0),
         98: (700.0, -1772.78125, 4.0, 384.0),
         24: (-340.0, 95.96875, 24.0, 384.0)}
HARBOR_SPEED = 0.55


def point(zone, x, y, pause=0):
    return dict(x=x, y=y, z=DOCKS[zone][2], pause=pause)


def phases():
    """Use pinned seed grid-200/201 corridors, with SHIP dock clearance.

    Transfers occur at explicit offshore gates inside the maps. They use
    solicited zoning, so they do not change ordinary walking zone points.
    """
    paths = [
        (1, [(940.166,-525.301), (842.677,-477.719), (662.628,-393.373),
             (550.833,-343.819), (443.253,-304.124), (350.494,-251.647),
             (319,-187.35), (319,13,90), (319,320), (550,400),
             (940,0), (940.166,-525.301)]),
        (98, [(661.68,-4166.92), (709.78,-3741.61), (691.473,-3477.17),
              (672.289,-3211.51), (665.716,-3077.98), (652.572,-2810.91),
              (580,-2275.81), (580,-2000), (580,-1772.78125,60),
              (580,-1520), (534.278,-1398.07), (482.72,-1264.41),
              (386.583,-1015.16), (290.64,-766.464), (194.462,-517.14),
              (50.782,-144.665), (-98.7043,242.865), (-291.007,741.377),
              (-434.916,1114.43), (-579.151,1488.33), (-771.47,1986.93),
              (-857.241,2209.27)]),
        (24, [(-1354.36,178.488), (-1135.52,173.545), (-765.103,136.485),
              (-650,300), (-540,420), (-443,420), (-443,95.96875,90),
              (-443,-220), (-675.106,-248), (-1055.88,-248),
              (-1219.9,-247.846), (-1354.36,178.488)]),
        (98, [(-590.729,2541.22), (-513.677,2391.85), (-454.148,2186.47),
              (-342.536,1801.46), (-230.891,1416.38), (-119.294,1031.43),
              (-1.1704,512.559), (26.1907,113.851), (119.842,-131.247),
              (269.372,-352.587), (338.321,-607.636), (429.915,-856.629),
              (507.549,-1110.4), (580,-1412.75), (580,-1529.23),
              (580,-1772.78125,60), (580,-2000), (577.828,-2456.87),
              (472.635,-3522.73), (396.146,-4184.09), (360.236,-4448.14)]),
    ]
    return [dict(zone=zone, points=[point(zone,*p) for p in path]) for zone,path in paths]


def heading(a, b):
    return math.atan2(b['x']-a['x'], b['y']-a['y'])*512/(2*math.pi) % 512


def config(ids, installation):
    return dict(version=1, installation=installation, key='trasc_ferry_'+installation,
        ship=ids['ship'], controllers=ids['controllers'], phases=phases(),
        docks={str(k): list(v) for k,v in DOCKS.items()},
        shore={str(k): list(v) for k,v in SHORE.items()},
        start_phase=1, start_point=8, harbor_speed=HARBOR_SPEED,
        arrival_hold=20, transfer_timeout=180, departure_guard=10)
