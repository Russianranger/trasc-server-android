#include "../backend/eq_server_ferry.h"
#include <cassert>
#include <limits>
#include <map>

struct Client {
    std::map<std::string,std::string> variables;
    void SetEntityVariable(std::string k,std::string v) { variables[k]=v; }
    void DeleteEntityVariable(std::string k) { variables.erase(k); }
};
struct Boat {
    bool npc=true,boat=true;
    std::string managed="1";
    bool IsNPC() const { return npc; }
    bool GetIsBoat() const { return boat; }
    std::string GetEntityVariable(std::string) const { return managed; }
    unsigned GetNPCTypeID() const { return 456; }
};
int main() {
    Client c; Boat b;
    TrascFerry::RecordPassenger(c,&b,103,59.5f,-173.25f,39.0f,500.5f);
    auto value=c.variables.at(TrascFerry::PacketKey);
    assert(value.find(",103,456,59.500000,-173.250000,39.000000,500.500000")!=std::string::npos);
    TrascFerry::RecordPassenger(c,&b,0,0,0,0,0);
    assert(c.variables.empty()); // A real disembark clears any old attachment.
    for (int reason=0;reason<7;++reason) {
        c.SetEntityVariable(TrascFerry::PacketKey,"stale");b=Boat{};
        float x=1,y=2,z=39,h=0;
        if(reason==0)b.managed="";
        if(reason==1)b.npc=false;
        if(reason==2)b.boat=false;
        if(reason==3)x=std::numeric_limits<float>::quiet_NaN();
        if(reason==4)y=513;
        if(reason==5)z=-1;
        if(reason==6)h=std::numeric_limits<float>::infinity();
        TrascFerry::RecordPassenger(c,&b,103,x,y,z,h);
        assert(c.variables.empty());
    }
    c.SetEntityVariable(TrascFerry::PacketKey,"stale");
    TrascFerry::RecordPassenger(c,static_cast<Boat*>(nullptr),103,1,2,39,0);
    assert(c.variables.empty());
}
