#!/usr/bin/env python3
"""Verify original RoF2 boat models, collision filter/attachment and floor cache.

Requires the user's exact private eqgame.exe, pefile and unicorn. Graphics actors
are synthetic recording stubs: this does not render a ship or prove deck geometry.
No game files are modified or included.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP

SHA256='4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'
BASE=0x400000
HEAP=0x3000000
PLAYER=HEAP+0x1000
BOAT=HEAP+0x3000
INFO=HEAP+0x5000
SOURCE=HEAP+0x6000
HIT=HEAP+0x7000
ACTOR=HEAP+0x8000
TABLE=HEAP+0x9000
STUBS=HEAP+0xA000
STACK=HEAP+0x1F000
STOP=HEAP+0x1FF00

class Fixture:
    def __init__(self,image):
        self.u=Uc(UC_ARCH_X86,UC_MODE_32)
        self.u.mem_map(BASE,(len(image)+4095)&~4095);self.u.mem_write(BASE,image)
        self.u.mem_map(HEAP,0x20000)
        self.stubs={};self.queries=0
        self.u.hook_add(UC_HOOK_CODE,self.hook)
        self.put(PLAYER,0x9d71f0);self.put(BOAT,0x9d71f0);self.put(BOAT+0x234,INFO)
        self.put(PLAYER+0x148,10);self.put(BOAT+0x148,20)
        self.put(SOURCE,TABLE);self.put(HIT,TABLE+0x100);self.put(ACTOR,TABLE+0x200)
        # Graphic application-data conversion calls return controlled actors.
        self.stub(TABLE+0xc,PLAYER)
        self.stub(TABLE+0x100+0x20,ACTOR)
        self.stub(TABLE+0x100+0x30,1)
        self.stub(TABLE+0x200+0xc,BOAT)
        self.stubs[0x488450]=1  # Zone geometry availability only.
        self.put(BASE+0x9d2630,PLAYER)
    def put(self,a,v):self.u.mem_write(a,struct.pack('<I',v))
    def f32(self,a,v):self.u.mem_write(a,struct.pack('<f',v))
    def get(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def stub(self,slot,result):
        a=STUBS+len(self.stubs)*16;self.put(slot,a);self.stubs[a]=result
    def hook(self,u,a,size,_):
        if a in self.stubs:
            sp=u.reg_read(UC_X86_REG_ESP);u.reg_write(UC_X86_REG_EAX,self.stubs[a])
            u.reg_write(UC_X86_REG_EIP,self.get(sp));u.reg_write(UC_X86_REG_ESP,sp+4)
        elif a==0x50732B:
            self.queries+=1;u.emu_stop() # Next instruction starts original graphics query.
    def call(self,fn,this,args=(),cleanup=0,stop_at_query=False):
        self.put(STACK,STOP)
        for i,v in enumerate(args):self.put(STACK+4+i*4,v)
        u=self.u;u.reg_write(UC_X86_REG_ESP,STACK);u.reg_write(UC_X86_REG_ECX,this)
        saved={UC_X86_REG_EBX:0x12345678,UC_X86_REG_ESI:0x23456789,UC_X86_REG_EDI:0x3456789A,UC_X86_REG_EBP:0x456789AB}
        for r,v in saved.items():u.reg_write(r,v)
        u.emu_start(fn,STOP,count=10000)
        if stop_at_query:
            assert u.reg_read(UC_X86_REG_EIP)==0x50732B;return
        assert u.reg_read(UC_X86_REG_EIP)==STOP
        assert u.reg_read(UC_X86_REG_ESP)==STACK+4+cleanup
        for r,v in saved.items():assert u.reg_read(r)==v


def main():
    if not __debug__:raise SystemExit('Run without -O; assertions are the checks.')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('executable',type=Path);a=ap.parse_args()
    data=a.executable.read_bytes();actual=hashlib.sha256(data).hexdigest()
    if actual!=SHA256:raise SystemExit('Unsupported executable SHA256: '+actual)
    p=pefile.PE(data=data);assert p.OPTIONAL_HEADER.ImageBase==BASE
    image=p.get_memory_mapped_image();cases=[]
    assert struct.unpack_from('<I',image,0x9d7240-BASE)[0]==0x59e530
    # Both collision filtering and passenger transforms use this same bit-0 predicate.
    for flags,expected in [(0,False),(1,True),(2,False),(3,True),(8,False),(11,True),(27,True)]:
        f=Fixture(image);f.put(INFO+0x2c,flags)
        f.call(0x59e530,BOAT)
        assert bool(f.u.reg_read(UC_X86_REG_EAX)&255)==expected
        before=bytes(f.u.mem_read(PLAYER,0x1100))
        f.call(0x475f40,0,(HIT,SOURCE,1,0))
        assert f.get(PLAYER+0x150)==(BOAT if expected else 0)
        after=bytes(f.u.mem_read(PLAYER,0x1100))
        assert before[:0x150]==after[:0x150] and before[0x154:]==after[0x154:]
        cases.append(dict(case='collision_callback',flags=flags,attached=expected,only_vehicle_pointer_changed=expected))
    f=Fixture(image);f.put(PLAYER+0x150,BOAT)
    f.call(0x8cfce0,PLAYER);assert f.u.reg_read(UC_X86_REG_EAX)==BOAT
    f.call(0x8cfd10,PLAYER,(0,),cleanup=4);assert f.get(PLAYER+0x150)==0
    cases.append(dict(case='vehicle_get_and_detach',verified=True))
    # With the same XY and a settled cache, an unattached player reuses the floor.
    # An already attached passenger takes the fresh geometry path instead.
    for attached in (False,True):
        f=Fixture(image);f.put(PLAYER+0x150,BOAT if attached else 0)
        f.put(PLAYER+0x1060,3);f.f32(PLAYER+0x138,6)
        for off,v in ((0x1064,10),(0x1068,20),(0x106c,30),(0x1070,25)):f.f32(PLAYER+off,v)
        args=[struct.unpack('<I',struct.pack('<f',v))[0] for v in (10,20,30)]+[1]
        f.call(0x507230,PLAYER,args,cleanup=16,stop_at_query=attached)
        assert f.queries==int(attached)
        cases.append(dict(case='floor_cache',attached=attached,fresh_query=attached))
    # The floor-query filter tests the graphics actor's restriction mask before
    # the attachment callback. This is separate from the race's vehicle flags.
    for mask in (0,1,2,3,0x80,0x81):
        f=Fixture(image);f.put(INFO+0x2c,3)
        f.stub(TABLE+0x100+0x54,mask)  # GetCollisionRestrictionMask
        f.stub(TABLE+0x100+0x3c,1)    # Model collision volume
        before=bytes(f.u.mem_read(PLAYER,0x1100))
        f.call(0x476280,0,(HIT,SOURCE))
        accepted=not bool(mask&1)
        assert f.u.reg_read(UC_X86_REG_EAX)==int(accepted)
        assert bytes(f.u.mem_read(PLAYER,0x1100))==before
        if accepted:f.call(0x475f40,0,(HIT,SOURCE,1,0))
        assert f.get(PLAYER+0x150)==(BOAT if accepted else 0)
        cases.append(dict(case='floor_actor_filter',race_flags=3,collision_mask=mask,accepted=accepted))
    # Execute the original race-72 registration call sites, recording their
    # arguments instead of allocating the game's entire race table. The native
    # constructor initializes EDI to zero before these uninterrupted call sites.
    f=Fixture(image);registrations=[]
    f.u.reg_write(UC_X86_REG_ESP,STACK)
    f.u.emu_start(0x50a60a,0x50a60c,count=1)
    assert f.u.reg_read(UC_X86_REG_EDI)==0
    def register(u,address,size,_):
        if address!=0x50a440:return
        sp=u.reg_read(UC_X86_REG_ESP)
        race,gender,tag,flags,option=(f.get(sp+4+i*4) for i in range(5))
        name=bytes(u.mem_read(tag,16)).split(b'\0',1)[0].decode('ascii')
        registrations.append(dict(race=race,gender=gender,model_tag=name,flags=flags,option=option))
        u.reg_write(UC_X86_REG_EIP,f.get(sp));u.reg_write(UC_X86_REG_ESP,sp+24)
    f.u.hook_add(UC_HOOK_CODE,register)
    f.u.emu_start(0x50a834,0x50a86f,count=100)
    assert f.u.reg_read(UC_X86_REG_EIP)==0x50a86f
    assert f.u.reg_read(UC_X86_REG_ESP)==STACK
    assert registrations==[dict(race=72,gender=g,model_tag=t,flags=3,option=1)
                           for g,t in ((0,'SHIP'),(1,'PRE'),(2,'PRE'))]
    cases.append(dict(case='race_72_model_variants',registrations=registrations))
    print(json.dumps(dict(executable_sha256=actual,verified=True,scope='Original model registration, classification, floor filter, attachment callback and cache branch; synthetic graphics, no live boat repair claim',cases=cases),indent=2))

if __name__=='__main__':main()
