"""Run the shipped Lua in three isolated zones with delayed client handshakes.

This verifies coordination and recovery, not RoF2's physical deck collision.
The native packet observer has a separate compiled fixture.
"""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import ferry_route
try:
    from lupa.lua51 import LuaRuntime, lua_type
except ImportError:
    LuaRuntime=None

FACTORIES='''
function make_ship(id,kind,x,y,z,h)
 local s={valid=true,id=id,kind=kind,x=x,y=y,z=z,h=h,vars={}}
 function s:CastToNPC() return self end
 function s:GetID() return self.id end
 function s:GetNPCTypeID() return self.kind end
 function s:GetX() return self.x end
 function s:GetY() return self.y end
 function s:GetZ() return self.z end
 function s:GetHeading() return self.h end
 function s:GetEntityVariable(k) return self.vars[k] or '' end
 function s:SetEntityVariable(k,v) self.vars[k]=v end
 function s:StopWandering() self.target=nil end
 function s:SaveGuardSpot() end
 function s:SetRunning(r) self.running=r end
 function s:MoveTo(x,y,z,h,save) self.target={x=x,y=y,z=z} end
 return s
end
function make_client(id,entity)
 local c={valid=true,id=id,entity=entity,packet='',connected=true,messages={}}
 function c:CharacterID() return self.id end
 function c:GetID() return self.entity end
 function c:Connected() return self.connected end
 function c:GetEntityVariable(k) return self.packet end
 function c:DeleteEntityVariable(k) self.packet='' end
 function c:Message(color,text) self.messages[#self.messages+1]=text end
 function c:MovePC(zone,x,y,z,h) request_move(self.id,zone,x,y,z,h) end
 return c
end
function entries(items)
 local index=0
 return {entries=function() index=index+1;return items[index] end}
end
'''


def plain(v):
    if lua_type(v)!='table':return v
    keys=list(v.keys())
    if all(type(k) is int for k in keys) and sorted(keys)==list(range(1,len(keys)+1)):
        return [plain(v[i]) for i in range(1,len(keys)+1)]
    return {str(k):plain(v[k]) for k in keys}


class World:
    def __init__(self):
        self.time=1000;self.db={};self.zones={};self.clients={};self.nextid=100
        self.pending=[];self.moves=[];self.loads={};self.no_attach=set();self.disabled=set()
        self.cfg=ferry_route.config(dict(ship=42,controllers={'1':43,'98':44,'24':45}),'a'*24)
        for phase in self.cfg['phases']:
            for p in phase['points']:p['pause']=1
        self.cfg.update(arrival_hold=3,transfer_timeout=20,departure_guard=10)
        p=self.cfg['phases'][0]['points'][7]
        self.state=dict(version=1,installation='a'*24,epoch='initial',phase=1,point=8,
            status='pause',sequence=0,wait_until=1001,updated=1000,riders=[],history=[],pose=dict(p,h=0))
        self.save()
        for zone in (1,98,24):self.make_zone(zone)
        self.step()

    def save(self):self.db[self.cfg['key']+'_state']=json.dumps(self.state)
    def read(self):self.state=json.loads(self.db[self.cfg['key']+'_state']);return self.state

    def make_zone(self,zone):
        lua=LuaRuntime(unpack_returned_tuples=True);g=lua.globals();lua.execute(FACTORIES)
        z={'lua':lua,'ship':None};self.zones[zone]=z
        g.pyencode=lambda v:json.dumps(plain(v),separators=(',',':'))
        g.pydecode=lambda s:lua.table_from(json.loads(s),recursive=True)
        g.config=lua.table_from(copy.deepcopy(self.cfg),recursive=True)
        lua.execute('package.preload["json"]=function() return {encode=pyencode,decode=pydecode} end; package.preload["trasc_ferry_config"]=function() return config end')
        g.clock=lambda:self.time;lua.execute('os.time=clock')
        g.request_move=lambda cid,dest,x,y,pz,h:self.move(zone,cid,dest,x,y,pz,h)
        def spawn(kind,grid,unused,x,y,pz,h):
            self.nextid+=1;z['ship']=g.make_ship(self.nextid,kind,x,y,pz,h);return z['ship']
        def depop(kind):
            if z['ship'] is not None:z['ship'].valid=False
            z['ship']=None
        def clients():return g.entries(lua.table_from([c['obj'] for c in self.clients.values() if c['zone']==zone and c['obj'].connected]))
        entity=lua.table_from({
            'GetNPCByNPCTypeID':lambda _,kind:z['ship'] or lua.table_from({'valid':False}),
            'GetClientByCharID':lambda _,cid:self.clients[cid]['obj'] if cid in self.clients and self.clients[cid]['zone']==zone else lua.table_from({'valid':False}),
            'GetClientList':lambda _:clients(),
        })
        g.eq=lua.table_from({'get_entity_list':lambda:entity,'get_zone_id':lambda:zone,
            'get_zone_instance_id':lambda:0,'spawn2':spawn,'depop_all':depop,'set_timer':lambda *a:None,
            'get_data':lambda k:self.db.get(k,''),'set_data':lambda k,v:self.db.__setitem__(k,v),
            'delete_data':lambda k:self.db.pop(k,None),'debug':lambda *a:None})
        z['module']=lua.execute((Path(__file__).parents[1]/'backend/ferry_service.lua').read_text())
        z['module'].spawn(lua.table_from({}),zone)

    def add(self,cid,zone=1,attached=True):
        z=self.zones[zone];self.nextid+=1
        obj=z['lua'].globals().make_client(cid,self.nextid)
        self.clients[cid]=dict(zone=zone,obj=obj,attached=attached,offset=[31,-80,40,77])
        self.packet(cid);return obj

    def packet(self,cid):
        c=self.clients[cid];ship=self.zones[c['zone']]['ship'] if c['zone'] in self.zones else None
        if c['attached'] and ship is not None:
            c['obj'].packet=','.join(map(str,[self.time,ship.id,42,*c['offset']]))
        else:c['obj'].packet=''

    def move(self,source,cid,dest,x,y,z,h):
        s=self.read();self.moves.append(dict(source=source,dest=dest,id=cid,x=x,y=y,z=z,h=h,
            sequence=s['sequence'],time=self.time,status=s['status']))
        if source==dest:
            self.clients[cid]['attached']=cid not in self.no_attach and s['status']=='receiving'
            return
        self.clients[cid]['obj'].connected=False;self.clients[cid]['zone']=0
        self.pending.append(dict(cid=cid,zone=dest,time=self.time+self.loads.get(cid,2)))

    def step(self,n=1):
        for _ in range(n):
            self.time+=1
            for p in self.pending[:]:
                if p['time']<=self.time:
                    self.pending.remove(p);self.add(p['cid'],p['zone'],p['cid'] not in self.no_attach)
            for z in self.zones.values():
                ship=z['ship']
                if ship is not None and ship.target is not None:
                    t=ship.target;dx=t.x-ship.x;dy=t.y-ship.y;length=math.hypot(dx,dy)
                    ship.h=math.atan2(dx,dy)*512/(2*math.pi)%512
                    # Compress sailing time, retaining the actual geographic path.
                    f=min(1,500/max(length,.001));ship.x+=dx*f;ship.y+=dy*f;ship.z=t.z
                    if f==1:ship.target=None
            for cid in self.clients:self.packet(cid)
            for zone,z in self.zones.items():
                if zone not in self.disabled:z['module'].tick(z['lua'].table_from({'timer':'trasc_ferry'}),zone)
            self.read()

    def until(self,predicate,limit=400):
        for _ in range(limit):
            if predicate():return
            self.step()
        raise AssertionError('Timed out: '+json.dumps(self.state))


@unittest.skipIf(LuaRuntime is None,'Install lupa to run the required Lua protocol gate')
class ProtocolTests(unittest.TestCase):
    def test_four_handoffs_round_trip_preserve_passenger_offsets(self):
        w=World();w.add(1001);w.add(1002,attached=False)
        w.until(lambda:len([m for m in w.moves if m['source']!=m['dest']])>=4)
        transfers=[m for m in w.moves if m['source']!=m['dest']]
        self.assertEqual([(m['source'],m['dest']) for m in transfers],[(1,98),(98,24),(24,98),(98,1)])
        self.assertEqual({m['id'] for m in transfers},{1001})
        self.assertTrue(all(m['status']=='receiving' for m in transfers))
        for move,phase in zip(transfers,[2,3,4,1]):
            points=w.cfg['phases'][phase-1]['points'];a,b=points[:2];h=ferry_route.heading(a,b);r=math.radians(h*360/512)
            self.assertAlmostEqual(move['x'],a['x']+31*math.cos(r)-80*math.sin(r),places=5)
            self.assertAlmostEqual(move['y'],a['y']-31*math.sin(r)-80*math.cos(r),places=5)
            self.assertAlmostEqual(move['z'],a['z']+40,places=5)
            self.assertAlmostEqual(move['h'],(77+h)%512,places=5)

    def test_destination_waits_for_slow_loading_passenger(self):
        w=World();w.cfg['transfer_timeout']=80
        # Each runtime owns its loaded config; update the destination's timeout
        # through the source that creates the transfer deadline.
        for z in w.zones.values():z['lua'].globals().config.transfer_timeout=80
        w.add(1);w.add(2);w.loads[2]=40
        w.until(lambda:w.state['status']=='receiving');start=w.time
        w.step(25)
        self.assertEqual(w.state['status'],'receiving')
        ship=w.zones[98]['ship'];self.assertIsNone(ship.target)
        self.assertAlmostEqual(ship.x,w.cfg['phases'][1]['points'][0]['x'])
        w.until(lambda:w.state['phase']==2)
        self.assertGreaterEqual(w.time-start,40)

    def test_walking_off_while_destination_prepares_cancels_transfer(self):
        w=World();w.add(1)
        w.until(lambda:w.state['status']=='ready')
        w.clients[1]['attached']=False;w.step(3)
        self.assertEqual([m for m in w.moves if m['source']!=m['dest']],[])

    def test_unavailable_destination_holds_source_and_reports_fault(self):
        w=World();w.add(1);w.disabled.add(98)
        w.until(lambda:w.state['status']=='fault')
        self.assertIn('Destination',w.state['error'])
        self.assertEqual(w.moves,[]);self.assertIsNone(w.zones[1]['ship'].target)

    def test_failed_attachment_recovers_to_dock_and_does_not_deadlock(self):
        w=World();w.add(1);w.no_attach.add(1)
        w.until(lambda:w.state['phase']==2)
        recovery=[m for m in w.moves if m['source']==m['dest']==98]
        self.assertEqual(recovery[-1]['x'],ferry_route.SHORE[98][0])
        self.assertTrue(any('failed riders=1' in e['event'] for e in w.state['history']))

    def test_camped_passenger_returns_to_dock_after_ship_moves(self):
        w=World();w.add(1);w.step(2)
        w.clients[1]['obj'].connected=False;w.step(2)
        w.add(1,attached=False);w.step(7)
        self.assertTrue(any(m['source']==m['dest']==1 and m['x']==ferry_route.SHORE[1][0] for m in w.moves))

    def test_connected_passenger_can_walk_off_without_teleport(self):
        w=World();w.add(1);w.step(7)
        w.clients[1]['attached']=False;w.step(2)
        self.assertEqual(w.moves,[])
        self.assertNotIn(w.cfg['key']+'_rider_1',w.db)

    def test_restart_recovers_saved_rider_without_requiring_old_ship(self):
        w=World();w.add(1);w.step(1)
        w.state['epoch']='after-restart';w.save();w.step(1)
        self.assertTrue(any(m['source']==m['dest']==1 and m['x']==ferry_route.SHORE[1][0] for m in w.moves))

if __name__=='__main__':
    if LuaRuntime is None:raise SystemExit('The protocol gate requires lupa (Lua 5.1)')
    unittest.main()
