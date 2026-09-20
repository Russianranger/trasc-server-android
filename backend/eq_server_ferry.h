// Passenger observations for the opt-in TRASC Qeynos–Erudin ferry quests.
// The original RoF2 vehicle-relative movement conversion remains authoritative.
#pragma once
#include <cmath>
#include <ctime>
#include <string>

namespace TrascFerry {
constexpr const char *PacketKey = "TRASC_FERRY_PASSENGER_V1";

template <typename ClientType, typename MobType>
void RecordPassenger(ClientType &client, MobType *boat, unsigned vehicle_id,
                     float x, float y, float z, float heading)
{
    if (!vehicle_id || !boat || !boat->IsNPC() || !boat->GetIsBoat() ||
        boat->GetEntityVariable("trasc_ferry_managed") != "1" ||
        !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z) ||
        !std::isfinite(heading) || std::abs(x) > 256 || std::abs(y) > 512 ||
        z < 0 || z > 160) {
        client.DeleteEntityVariable(PacketKey);
        return;
    }
    // One value keeps each snapshot coherent. These are the client's actual
    // local coordinates, including updates suppressed while the boat turns.
    client.SetEntityVariable(PacketKey,
        std::to_string(std::time(nullptr)) + "," + std::to_string(vehicle_id) + "," +
        std::to_string(boat->GetNPCTypeID()) + "," + std::to_string(x) + "," +
        std::to_string(y) + "," + std::to_string(z) + "," + std::to_string(heading));
}
}
