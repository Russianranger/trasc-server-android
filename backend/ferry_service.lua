-- Qeynos <-> Erud's Crossing <-> Erudin. One owner writes each protocol stage.
-- Installed under a reserved module name; existing player/NPC quests are kept.
local json = require("json")
local cfg = require("trasc_ferry_config")
local M = {}
local live = { reseated = {}, first_seen = {} }
local PACKET = "TRASC_FERRY_PASSENGER_V1"
local function now() return os.time() end
local function list() return eq.get_entity_list() end
local function valid(e) return e and e.valid end
local function decode(value)
    if not value or value == "" then return nil end
    local ok, data = pcall(json.decode, value)
    if ok and type(data) == "table" then return data end
end
local function ticket_key(id) return cfg.key.."_rider_"..tostring(id) end
local function ticket(id, value)
    if value then eq.set_data(ticket_key(id), json.encode(value))
    else eq.delete_data(ticket_key(id)) end
end
local function read_state()
    local s = decode(eq.get_data(cfg.key.."_state"))
    if s and s.installation == cfg.installation and s.version == 1 and
       cfg.phases[s.phase] and type(s.epoch) == "string" then return s end
end
local function write(s, event)
    s.updated = now()
    if event then
        s.history = s.history or {}
        table.insert(s.history, {time=now(), event=event, phase=s.phase, sequence=s.sequence})
        while #s.history > 64 do table.remove(s.history, 1) end
        eq.debug("TRASC ferry: "..event.." phase="..s.phase.." sequence="..s.sequence)
    end
    eq.set_data(cfg.key.."_state", json.encode(s))
end
local function each_client(fn)
    for client in list():GetClientList().entries do
        if valid(client) and client:Connected() then fn(client) end
    end
end
local function pose(ship)
    return {x=ship:GetX(), y=ship:GetY(), z=ship:GetZ(), h=ship:GetHeading()}
end
local function heading(a,b)
    -- Lua 5.1 exposes atan2 rather than the two-argument atan of newer Lua.
    return (math.atan2(b.x-a.x,b.y-a.y)*512/(2*math.pi))%512
end
local function distance(a,b) return math.sqrt((a.x-b.x)^2+(a.y-b.y)^2) end
local function hold(ship)
    ship:StopWandering()
    ship:SaveGuardSpot()
    ship:SetRunning(false)
end
local function passenger(client, ship)
    if not valid(ship) then return nil end
    local fields = {}
    for v in string.gmatch(client:GetEntityVariable(PACKET), "[^,]+") do
        fields[#fields+1] = tonumber(v)
    end
    if #fields ~= 7 or fields[2] ~= ship:GetID() or fields[3] ~= cfg.ship or
       now()-fields[1] < 0 or now()-fields[1] > 5 then return nil end
    return {id=client:CharacterID(), x=fields[4], y=fields[5], z=fields[6], h=fields[7]}
end
local function ship_for(s, phase, at)
    local ship = list():GetNPCByNPCTypeID(cfg.ship)
    if valid(ship) and ship:GetEntityVariable("trasc_ferry_epoch") == s.epoch and
       ship:GetEntityVariable("trasc_ferry_segment") == tostring(phase) then return ship end
    eq.depop_all(cfg.ship)
    ship = eq.spawn2(cfg.ship, 0, 0, at.x, at.y, at.z, at.h or 0):CastToNPC()
    if not valid(ship) then error("Unable to create the destination ferry") end
    ship:SetEntityVariable("trasc_ferry_managed", "1")
    ship:SetEntityVariable("trasc_ferry_epoch", s.epoch)
    ship:SetEntityVariable("trasc_ferry_segment", tostring(phase))
    hold(ship)
    return ship
end
local function move_to(ship, zone, target)
    local dock = cfg.docks[tostring(zone)]
    local p = {x=dock[1],y=dock[2]}
    ship:SetRunning(distance(pose(ship),p)>250 and distance(target,p)>250)
    -- The scoped native waypoint patch preserves this waterline.
    ship:MoveTo(target.x,target.y,target.z,-1,true)
end
local function shore(client, zone, message)
    local p=cfg.shore[tostring(zone)]
    client:Message(15,message)
    client:MovePC(zone,p[1],p[2],p[3],p[4])
    client:DeleteEntityVariable(PACKET)
    ticket(client:CharacterID(),nil)
end
local function recover_clients(s, zone)
    local present={}
    each_client(function(client)
        local id=client:CharacterID()
        present[id]=true
        local t=decode(eq.get_data(ticket_key(id)))
        local seen=live.first_seen[id]
        if not seen or seen.entity~=client:GetID() then
            seen={entity=client:GetID(),at=now(),login_ride=t and t.kind=="ride"}
            live.first_seen[id]=seen
        end
        if not t then return end
        if t.epoch ~= s.epoch or t.kind == "recover" or
           (t.kind == "transfer" and now() > t.deadline) then
            shore(client,zone,"The ferry crossing was interrupted. You have been returned to this dock.")
        elseif t.kind == "ride" then
            local ship=list():GetNPCByNPCTypeID(cfg.ship)
            if passenger(client,ship) then
                seen.login_ride=false
            elseif now()-seen.at>5 then
                if seen.login_ride then
                    shore(client,zone,"The ferry moved while you were away. You have been returned to this dock.")
                else ticket(id,nil) end -- A connected passenger walked off.
            end
        end
    end)
    for id in pairs(live.first_seen) do
        if not present[id] then live.first_seen[id]=nil end
    end
end
local function collect(ship,s,zone)
    local riders={}
    each_client(function(client)
        local r=passenger(client,ship)
        if r then
            riders[#riders+1]=r
            local old=decode(eq.get_data(ticket_key(r.id)))
            if not old or old.kind ~= "ride" or old.epoch ~= s.epoch or old.zone ~= zone then
                ticket(r.id,{kind="ride",epoch=s.epoch,zone=zone})
            end
        end
    end)
    return riders
end
local function arrival_pose(phase)
    local path=cfg.phases[phase].points
    return {x=path[1].x,y=path[1].y,z=path[1].z,h=heading(path[1],path[2])}
end
local function passenger_world(r,p)
    local a=p.h*2*math.pi/512
    return p.x+r.x*math.cos(a)+r.y*math.sin(a),
           p.y-r.x*math.sin(a)+r.y*math.cos(a),p.z+r.z,(r.h+p.h)%512
end
local function retire_source(s,zone)
    local ship=list():GetNPCByNPCTypeID(cfg.ship)
    if not valid(ship) then return end
    hold(ship)
    local aboard=false
    each_client(function(client)
        if passenger(client,ship) then
            aboard=true
            if now()-(s.transfer_started or s.updated)>cfg.departure_guard then
                shore(client,zone,"The crossing did not complete. You have been returned to the departure dock.")
            end
        end
    end)
    if not aboard then eq.depop_all(cfg.ship) end
end
local function source_transfer(s,ship,zone)
    if s.status == "prepare" then
        if now()-s.updated>60 then
            s.status="fault";s.error="Destination zone did not prepare its ship; passengers remain aboard."
            write(s,"destination preparation timed out")
        end
        return
    end
    if s.status ~= "ready" then return end
    s.riders=collect(ship,s,zone) -- Walking off during preparation cancels boarding.
    s.status="receiving";s.transfer_started=now();s.deadline=now()+cfg.transfer_timeout
    local dest=cfg.phases[s.next_phase].zone
    for _,r in ipairs(s.riders) do
        ticket(r.id,{kind="transfer",epoch=s.epoch,sequence=s.sequence,
                    zone=dest,from=zone,deadline=s.deadline})
    end
    write(s,"destination ready; transferring "..#s.riders.." passengers")
    for _,r in ipairs(s.riders) do
        local client=list():GetClientByCharID(r.id)
        if valid(client) then
            local x,y,z,h=passenger_world(r,s.destination)
            client:Message(15,"Crossing the zone boundary. The ship will wait while you load.")
            client:MovePC(dest,x,y,z,h)
        end
    end
end
local function receive(s,zone)
    local ship=ship_for(s,s.next_phase,s.destination or arrival_pose(s.next_phase))
    hold(ship)
    if s.status == "prepare" then
        s.destination=pose(ship);s.status="ready"
        write(s,"destination ship prepared")
        return
    end
    if s.status ~= "receiving" then return end
    local complete=true
    for _,r in ipairs(s.riders) do
        if not r.delivered then
            local client=list():GetClientByCharID(r.id)
            if valid(client) and client:Connected() and passenger(client,ship) then
                r.delivered=true
                ticket(r.id,{kind="ride",epoch=s.epoch,zone=zone})
            elseif now()>=s.deadline then
                r.delivered=true;r.failed=true
                if valid(client) and client:Connected() then
                    shore(client,zone,"The ferry could not confirm deck attachment. You have been returned to the arrival dock.")
                end -- An offline rider retains the recovery ticket for their next login.
            else
                complete=false
                if valid(client) and client:Connected() and now()-s.transfer_started>10 and
                   live.reseated[r.id]~=s.sequence then
                    local x,y,z,h=passenger_world(r,pose(ship))
                    client:MovePC(zone,x,y,z+1,h)
                    live.reseated[r.id]=s.sequence
                end
            end
        end
    end
    if complete and now()-s.transfer_started>=cfg.arrival_hold then
        local failed=0
        for _,r in ipairs(s.riders) do if r.failed then failed=failed+1 end end
        s.phase=s.next_phase;s.next_phase=nil;s.point=1;s.status="pause"
        s.wait_until=now()+5;s.pose=pose(ship);s.destination=nil
        write(s,"handoff complete; failed riders="..failed)
    else
        write(s)
    end
end
local function drive(s,zone)
    if s.status=="receiving" then retire_source(s,zone);return end
    local path=cfg.phases[s.phase].points
    local at=s.pose or {x=path[s.point].x,y=path[s.point].y,z=path[s.point].z,
                       h=heading(path[s.point],path[math.min(s.point+1,#path)])}
    local ship=ship_for(s,s.phase,at)
    if s.status=="prepare" or s.status=="ready" then
        hold(ship);source_transfer(s,ship,zone);return
    end
    if s.status=="fault" then hold(ship);return end
    s.riders=collect(ship,s,zone);s.pose=pose(ship)
    if s.status=="pause" then
        hold(ship)
        if now()<(s.wait_until or 0) then write(s);return end
        if s.point==#path then
            s.status="prepare";s.next_phase=s.phase%#cfg.phases+1
            s.sequence=s.sequence+1;s.destination=arrival_pose(s.next_phase)
            write(s,"requesting next zone");return
        end
        s.point=s.point+1;s.status="sailing"
        move_to(ship,zone,path[s.point]);live.moving=s.epoch..":"..s.phase..":"..s.point
        write(s,"departing waypoint "..(s.point-1));return
    end
    if s.status=="sailing" then
        local target=path[s.point]
        if distance(pose(ship),target)<0.6 then
            hold(ship);s.status="pause";s.wait_until=now()+math.max(target.pause or 0,2)
            s.pose=pose(ship);write(s,"arrived waypoint "..s.point)
        else
            local movement=s.epoch..":"..s.phase..":"..s.point
            if live.moving~=movement then move_to(ship,zone,target);live.moving=movement end
            write(s)
        end
    end
end
function M.spawn(e,zone)
    if eq.get_zone_id()~=zone or eq.get_zone_instance_id()~=0 then return end
    live={reseated={},first_seen={}}
    eq.set_timer("trasc_ferry",1000)
end
function M.tick(e,zone)
    if e.timer~="trasc_ferry" or eq.get_zone_id()~=zone or eq.get_zone_instance_id()~=0 then return end
    local s=read_state()
    if not s then return end
    recover_clients(s,zone)
    if s.next_phase and cfg.phases[s.next_phase].zone==zone and
       (s.status=="prepare" or s.status=="ready" or s.status=="receiving") then
        receive(s,zone)
    elseif cfg.phases[s.phase].zone==zone then drive(s,zone)
    else retire_source(s,zone) end
end
-- Pure helpers are also used by the deterministic multi-zone protocol fixture.
M.passenger_world=passenger_world
return M
