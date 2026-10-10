// Exercise the production Mac packet translator. Decoding is performed
// separately in Python using literal wire offsets and an inverse cipher.
#include "common/eq_packet.h"
#include "common/eq_packet_structs.h"
#include "common/eq_packet_translator.h"
#include "common/eqemu_logsys.h"
#include "common/patches/mac.h"
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

EQEmuLogSys LogSys;

static void emit(EQPacketTranslator &translator, EmuOpcode opcode, int count,
                 int start, const std::string &path)
{
    auto packet = new EQApplicationPacket(opcode, count * sizeof(NewSpawn_Struct));
    auto rows = reinterpret_cast<NewSpawn_Struct *>(packet->pBuffer);
    for (int i = 0; i < count; ++i) {
        int n = start + i;
        auto &spawn = rows[i].spawn;
        std::string name = "Paineel_fixture_" + std::to_string(n);
        std::strncpy(spawn.name, name.c_str(), sizeof(spawn.name) - 1);
        spawn.spawnId = 400 + n;
        spawn.race = n % 2 ? 3 : 60;
        spawn.NPC = 1;
        spawn.bodytype = 1;
        spawn.class_ = 1;
        spawn.gender = n % 2;
        spawn.level = 1 + n % 60;
        spawn.curHp = 100;
        spawn.x = 500 + n;
        spawn.y = 700 + n;
        spawn.z = -120 + n;
        spawn.heading = n % 256;
        spawn.size = 6.0f;
        spawn.walkspeed = .7f;
        spawn.runspeed = 1.25f;
        spawn.StandState = 100;
        spawn.invis = 0;
    }
    EQPacketEncodeResult result;
    translator.Encode(&packet, &result, true);
    auto wire = result.Packet();
    if (packet || !wire || !wire->size || wire->GetOpcode() != OP_ZoneSpawns ||
        translator.EmuToEQ(wire->GetOpcode()) != 0x415f || !result.Reliable()) {
        throw std::runtime_error("Production translator did not emit reliable Mac zone spawns");
    }
    std::ofstream output(path, std::ios::binary);
    output.write(reinterpret_cast<const char *>(wire->pBuffer), wire->size);
    if (!output) throw std::runtime_error("Could not save encoded wire packet");
}

int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    try {
        EQPacketTranslator translator;
        if (!translator.LoadOpcodes(argv[1])) throw std::runtime_error("Missing Mac opcode map");
        Mac::Register(translator);
        std::string root = argv[2];
        for (int count : {1, 56, 100}) {
            emit(translator, OP_ZoneSpawns, count, 0,
                 root + "/bulk-" + std::to_string(count) + ".bin");
        }
        // Cold zone boot creates NPCs after the initial zone entry. Their
        // deferred notifications use OP_NewSpawn, rather than the bulk path.
        for (int i = 0; i < 156; ++i) {
            emit(translator, OP_NewSpawn, 1, i,
                 root + "/new-" + std::to_string(i) + ".bin");
        }
        std::cout << "internal_spawn_bytes=" << sizeof(Spawn_Struct) << "\n";
        std::cout << "bulk_packets=3 new_spawn_packets=156\n";
    } catch (const std::exception &error) {
        std::cerr << error.what() << "\n";
        return 1;
    }
}
