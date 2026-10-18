// SPDX-License-Identifier: GPL-3.0-only
// Regression reference for Triptych's LoN card loader; not packaged in the APK.
// Reader, CardInfo and ParseArchetype below are copied verbatim from:
// https://github.com/Russianranger/Triptych-Triumvirate/blob/38a4f2ad03203cb2f12dbff26fd613cc47efba0a/Release-NMS-Server/world/lon_service.cpp
// Upstream license (GPL v3):
// https://github.com/Russianranger/Triptych-Triumvirate/blob/38a4f2ad03203cb2f12dbff26fd613cc47efba0a/Release-NMS-Server/LICENSE
// The small main adapts LoadData's card/index and pool acceptance checks into a
// bounded host-only oracle. Fixtures are synthetic, with no client assets.
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <zlib.h>
constexpr uint32_t kPropertySet=0x017;
constexpr uint32_t kKeyName=1, kKeySubtype=5, kKeySet=73, kKeyNumber=74, kKeyRarity=76, kKeyLoremaster=2051;

struct Reader {
	const uint8_t *d;
	size_t         n;
	size_t         p   = 0;
	bool           bad = false;

	Reader(const uint8_t *data, size_t size) : d(data), n(size) {}

	bool eof() const { return p >= n; }

	uint32_t U()
	{
		if (p >= n) { bad = true; return 0; }
		const uint8_t b0    = d[p++];
		const uint32_t hi   = b0 >> 4;
		const uint32_t extra = hi >> 1;
		const bool     neg  = (hi & 1) != 0;
		uint32_t mag   = b0 & 0x0F;
		uint32_t shift = 4;
		for (uint32_t i = 0; i < extra; ++i) {
			if (p >= n) { bad = true; return 0; }
			mag |= static_cast<uint32_t>(d[p++]) << shift;
			shift += 8;
		}
		return neg ? ~mag : mag;
	}

	int32_t I() { return static_cast<int32_t>(U()); }

	std::string S()
	{
		const uint32_t len = U();
		if (bad || len > 0x100000 || p + len + 1 > n) { bad = true; return {}; }
		std::string s(reinterpret_cast<const char *>(d + p), len);
		p += len + 1;   // the writer puts the NUL on the wire
		return s;
	}
};

struct CardInfo {
	std::string name;
	std::string subtype;
	int         set    = -1;
	int         number = 0;
	int         rarity = 0;
	bool        loremaster = false;
};

bool ParseArchetype(const uint8_t *p, size_t n, uint32_t &arch, CardInfo &out)
{
	Reader r(p, n);
	for (int i = 0; i < 4; ++i) r.U();
	arch = r.U();
	r.U();
	r.U();
	if (r.bad) return false;
	if (r.U() != 0) return true;     // no properties
	r.U();
	r.U();
	if (r.U() != kPropertySet) return false;
	r.U();
	const uint32_t count = r.U();
	for (uint32_t i = 0; i < count && !r.bad; ++i) {
		const uint32_t key = r.U();
		r.U();                         // ValueData class
		r.U();                         // version
		const uint32_t type = r.U();
		r.U();                         // owning flag
		switch (type) {
			case 1:
				if (r.U() && key == kKeyLoremaster) out.loremaster = true;
				break;
			case 2: {
				const int32_t v = r.I();
				if (key == kKeySet)    out.set    = v;
				if (key == kKeyNumber) out.number = v;
				if (key == kKeyRarity) out.rarity = v;
				if (key == kKeyLoremaster && v == 1) out.loremaster = true;
				break;
			}
			case 3: {
				std::string s = r.S();
				if (key == kKeyName)    out.name    = s;
				if (key == kKeySubtype) out.subtype = s;
				break;
			}
			case 6: {
				const uint32_t k = r.U();
				for (uint32_t j = 0; j < k && !r.bad; ++j) r.I();
				break;
			}
			default:
				return false;
		}
	}
	return !r.bad;
}

bool ReadBounded(const std::string &path, std::vector<uint8_t> &out)
{
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f || f.tellg() < 0 || f.tellg() > 128 * 1024 * 1024) return false;
    const auto size = static_cast<size_t>(f.tellg());
    f.seekg(0);
    out.resize(size);
    return size == 0 || static_cast<bool>(f.read(reinterpret_cast<char *>(out.data()), size));
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    std::vector<uint8_t> index, storage;
    int parsed = 0, failed = 0;
    std::map<uint32_t, CardInfo> cards;
    bool available = ReadBounded(std::string(argv[1]) + "/archetypes/index.dat", index)
                  && ReadBounded(std::string(argv[1]) + "/archetypes/storage.dat", storage);
    if (available) {
        Reader ir(index.data(), index.size());
        ir.U(); ir.U();
        while (!ir.eof() && !ir.bad) {
            const uint32_t a = ir.U(), c = ir.U(), u = ir.U(), o = ir.U();
            (void)a;
            if (ir.bad) break;
            if (static_cast<size_t>(o) + c > storage.size() || u == 0 || u > 8 * 1024 * 1024) {
                ++failed; continue;
            }
            std::vector<uint8_t> raw(u + 64);
            uLongf got = raw.size();
            if (uncompress(raw.data(), &got, storage.data() + o, c) != Z_OK || got == 0) {
                ++failed; continue;
            }
            uint32_t arch = 0;
            CardInfo info;
            if (!ParseArchetype(raw.data(), got, arch, info)) { ++failed; continue; }
            cards[arch] = info;
            ++parsed;
        }
    }
    std::set<int> pools;
    for (const auto &kv : cards) {
        const auto id = kv.first;
        const auto &card = kv.second;
        if (id < 20000000 || card.set < 0) continue;
        const bool loot = card.subtype.size() > 10
            && card.subtype.compare(card.subtype.size() - 10, 10, " Loot Card") == 0;
        if (loot && card.subtype != "EverQuest Loot Card") continue;
        pools.insert(card.set);
    }
    std::cout << "{\"valid\":" << (available && parsed > 0 && !pools.empty() ? "true" : "false")
              << ",\"parsed_archetypes\":" << parsed
              << ",\"unreadable_archetypes\":" << failed
              << ",\"booster_sets\":" << pools.size() << "}\n";
    return 0;
}
