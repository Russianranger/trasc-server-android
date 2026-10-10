// GPL-3.0-or-later. Included only by the qualified EQEmu zone translation unit.
// This one-shot launcher adapter has no listener and never enters the zone loop.
#include "../common/json/json.hpp"
#include "../common/repositories/account_repository.h"
#include "../common/repositories/rule_sets_repository.h"
#include "client.h"
#include <openssl/sha.h>
#include <cctype>
#include <iostream>
#include <memory>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>

namespace TrascBotBridge {
using Json = nlohmann::json;
constexpr const char* Profile = "@TRASC_PROFILE@";
constexpr const char* Revision = "@TRASC_REVISION@";
constexpr const char* Identity = "@TRASC_IDENTITY@";

static Json Capabilities() {
    return {{"format", 1}, {"profile", Profile}, {"offline_create", true},
        {"creation_receipt_table", "trasc_bot_creation_receipts"},
        {"source_revision", Revision}, {"patch_identity", Identity},
        {"shared_content_database_required", true}};
}

static std::string Hash(const std::string& input) {
    unsigned char bytes[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(input.data()), input.size(), bytes);
    constexpr const char* hex = "0123456789abcdef";
    std::string result;
    for (unsigned char byte : bytes) {
        result += hex[byte >> 4];
        result += hex[byte & 15];
    }
    return result;
}

static void Require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static MySQLRequestResult Query(const std::string& sql) {
    auto result = database.QueryDatabase(sql, false);
    Require(result.Success(), "Bot creation database operation failed; no bots were committed.");
    return result;
}

static bool HexHash(const std::string& value) {
    return std::regex_match(value, std::regex("[a-f0-9]{64}"));
}

static uint32_t Unsigned(const Json& object, const char* key, uint32_t minimum, uint32_t maximum) {
    Require(object.contains(key) && object.at(key).is_number_integer(), "Invalid bot creation number.");
    const auto number = object.at(key).get<int64_t>();
    Require(number >= minimum && number <= maximum, "Bot creation number is outside its valid range.");
    return static_cast<uint32_t>(number);
}

static std::string ReadRequest() {
    std::string input;
    char buffer[4096];
    while (std::cin.read(buffer, sizeof(buffer)) || std::cin.gcount()) {
        input.append(buffer, static_cast<size_t>(std::cin.gcount()));
        Require(input.size() <= 65536, "Bot creation request is too large.");
    }
    return input;
}

static void ValidateReceiptBots(const Json& receipt, uint32_t owner_id) {
    Require(receipt.contains("bots") && receipt.at("bots").is_array(), "Bot creation receipt is invalid.");
    for (const auto& bot : receipt.at("bots")) {
        const auto id = Unsigned(bot, "id", 1, UINT32_MAX);
        auto found = Query(fmt::format("SELECT owner_id,name,`class`,race,gender FROM bot_data WHERE bot_id={} FOR UPDATE", id));
        Require(found.RowCount() == 1, "Saved bot creation receipt no longer matches this database; refresh the roster.");
        auto row = found.begin();
        Require(Strings::ToUnsignedInt(row[0]) == owner_id && row[1] && bot.at("name") == row[1] &&
            Strings::ToUnsignedInt(row[2]) == bot.at("class").get<uint32_t>() &&
            Strings::ToUnsignedInt(row[3]) == bot.at("race").get<uint32_t>() &&
            Strings::ToUnsignedInt(row[4]) == bot.at("gender").get<uint32_t>(),
            "Saved bot creation receipt no longer matches the selected owner.");
        // Run the same loader used for in-game spawning, including persisted
        // appearance, inventory, stance and bot settings, in this fresh process.
        std::unique_ptr<Bot> loaded(Bot::LoadBot(id));
        Require(loaded && loaded->GetBotID() == id && loaded->GetBotOwnerCharacterID() == owner_id &&
            bot.at("name") == loaded->GetCleanName() && loaded->GetClass() == bot.at("class").get<uint32_t>() &&
            loaded->GetRace() == bot.at("race").get<uint32_t>() && loaded->GetGender() == bot.at("gender").get<uint32_t>(),
            "The newly saved bot could not be loaded by this server; the batch was rolled back.");
    }
}

static int Create() {
    bool transaction = false;
    std::unique_ptr<Client> owner;
    std::unique_ptr<Zone> context;
    auto reject = [&](const std::string& message) {
        owner.reset();
        is_zone_loaded = false;
        context.reset();
        zone = nullptr;
        database.SetTrascAtomicBatch(false);
        content_db.SetTrascAtomicBatch(false);
        if (transaction) database.QueryDatabase(std::string("ROLLBACK"), false);
        std::cout << "TRASC_BOT_RESULT " << Json({{"format", 1}, {"ok", false}, {"error", message}}).dump() << std::endl;
        return 1;
    };
    try {
        EQEmuLogSys::Instance()->SilenceConsoleLogging();
        const auto request = Json::parse(ReadRequest());
        Require(request.is_object() && request.value("format", 0) == 1 && request.value("profile", "") == Profile,
            "Bot creation request does not match this server adapter.");
        Require(request.value("database", "") == Config->DatabaseDB, "Selected bot database changed; refresh the roster.");
        Require(Config->ContentDbHost.empty() ||
            (Config->ContentDbHost == Config->DatabaseHost && Config->ContentDbName == Config->DatabaseDB &&
             Config->ContentDbPort == Config->DatabasePort && Config->ContentDbUsername == Config->DatabaseUsername &&
             Config->ContentDbPassword == Config->DatabasePassword),
            "Offline bot creation requires the same data/content database and credentials.");
        // The normal configuration may name the same DB twice. Share its
        // actual connection for this one-shot command, rather than opening a
        // second transaction for starting items.
        content_db.SetMySQL(database);
        const auto request_id = request.value("request_id", "");
        const auto draft_hash = request.value("draft_hash", "");
        const auto identity_hash = request.value("identity_hash", "");
        Require(std::regex_match(request_id, std::regex("[A-Za-z0-9_-]{16,64}")) && HexHash(draft_hash) && HexHash(identity_hash),
            "Invalid bot creation retry identity.");
        const auto& requested_owner = request.at("owner");
        const auto owner_id = Unsigned(requested_owner, "id", 1, UINT32_MAX);
        const auto account_id = Unsigned(requested_owner, "account_id", 1, UINT32_MAX);
        const auto owner_level = Unsigned(requested_owner, "level", 1, 255);
        const auto owner_name = requested_owner.at("name").get<std::string>();
        const auto& bots = request.at("bots");
        Require(bots.is_array() && !bots.empty() && bots.size() <= 24, "Choose between 1 and 24 bots per creation batch.");
        Require(Hash(bots.dump()) == request.value("bots_hash", ""), "Bot creation draft changed; preview it again.");
        std::set<std::string> names;
        for (const auto& bot : bots) {
            Require(bot.is_object() && bot.size() == 4, "Bot creation draft contains unsupported fields.");
            const auto name = bot.at("name").get<std::string>();
            Require(std::regex_match(name, std::regex("[A-Za-z]{4,15}")), "Bot names must have 4 to 15 ASCII letters.");
            std::string folded = name;
            for (char& letter : folded) letter = static_cast<char>(std::tolower(static_cast<unsigned char>(letter)));
            Require(names.insert(folded).second, "The bot draft contains duplicate names.");
            Unsigned(bot, "class", 1, 16);
            Unsigned(bot, "race", 1, 522);
            Unsigned(bot, "gender", 0, 1);
        }

        // A single shared connection makes the normal Bot::Save, quest queries,
        // starting items and retry receipt participate in the same transaction.
        std::set<std::string> transactional_tables;
        auto engines = Query("SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()");
        for (auto engine : engines) {
            if (engine[0] && engine[1] && std::string(engine[1]) == "InnoDB") transactional_tables.insert(engine[0]);
        }
        Require(transactional_tables.count("bot_data") && transactional_tables.count("character_data") &&
            transactional_tables.count("trasc_bot_creation_receipts") && transactional_tables.count("_trasc_bot_manager_identity"),
            "Bot data, owners and creation receipts must use InnoDB; no storage engine was changed.");
        database.SetTrascWritableTables(transactional_tables);
        content_db.SetTrascWritableTables(transactional_tables);
        Query("START TRANSACTION");
        transaction = true;
        database.SetTrascAtomicBatch(true);
        content_db.SetTrascAtomicBatch(true);
        const auto failures_before = database.GetTrascQueryFailures() + content_db.GetTrascQueryFailures();
        auto incarnation = Query("SELECT incarnation FROM _trasc_bot_manager_identity WHERE id=1 FOR UPDATE");
        Require(incarnation.RowCount() == 1 && incarnation.begin()[0] &&
            request.value("database_instance", "") == incarnation.begin()[0],
            "This database was replaced or restored; refresh the bot roster.");
        auto active = Query(fmt::format("SELECT c.account_id,c.name,c.level,c.zone_id,a.name FROM character_data c JOIN account a ON a.id=c.account_id WHERE c.id={} AND c.deleted_at IS NULL FOR UPDATE", owner_id));
        Require(active.RowCount() == 1, "The selected owner is no longer an active character.");
        auto row = active.begin();
        Require(Strings::ToUnsignedInt(row[0]) == account_id && row[1] && owner_name == row[1] &&
            Strings::ToUnsignedInt(row[2]) == owner_level && row[4] && requested_owner.at("account") == row[4],
            "The selected owner changed; refresh the roster.");
        const auto zone_id = Strings::ToUnsignedInt(row[3]);

        const auto zone_name = ZoneName(zone_id);
        Require(zone_id && zone_name, "The selected owner's zone is not available in this server's content database.");
        // Load the owner's actual zone rules, but never boot its population.
        context = std::make_unique<Zone>(zone_id, 0, zone_name, true);
        zone = context.get();
        zone->SetStaticZone(false);
        Require(zone->LoadZoneCFG(zone_name, 0), "Could not load the owner's zone configuration.");
        if (RuleManager::Instance()->GetActiveRulesetID() != zone->GetTrascOfflineRuleset()) {
            const auto rules_name = RuleSetsRepository::GetRuleSetName(database, zone->GetTrascOfflineRuleset());
            Require(!rules_name.empty() && RuleManager::Instance()->LoadRules(&database, rules_name, false),
                "Could not load the owner's zone rules.");
        }
        Require(RuleB(Bots, Enabled), "Bots are disabled by this server's zone rules.");
        zone->LoadAlternateAdvancement();
        zone->LoadBaseData();

        auto prior = Query(fmt::format("SELECT draft_hash,identity_hash,owner_id,result_json FROM trasc_bot_creation_receipts WHERE request_id='{}' FOR UPDATE", request_id));
        if (prior.RowCount()) {
            auto saved = prior.begin();
            Require(saved[0] && draft_hash == saved[0] && saved[1] && identity_hash == saved[1] &&
                Strings::ToUnsignedInt(saved[2]) == owner_id && saved[3], "This creation token belongs to another draft or restored database.");
            auto result = Json::parse(saved[3]);
            Require(result.at("owner") == requested_owner, "The creation receipt owner changed; refresh the roster.");
            Json saved_draft = result.at("bots");
            for (auto& bot : saved_draft) bot.erase("id");
            Require(saved_draft == bots, "This creation token belongs to another bot draft.");
            ValidateReceiptBots(result, owner_id);
            Require(database.GetTrascQueryFailures() + content_db.GetTrascQueryFailures() == failures_before,
                "The saved bot state could not be reloaded; no bots were committed.");
            context.reset();
            zone = nullptr;
            database.SetTrascAtomicBatch(false);
            content_db.SetTrascAtomicBatch(false);
            Query("COMMIT");
            transaction = false;
            result["reused"] = true;
            result["format"] = 1;
            result["ok"] = true;
            result["native_load_verified"] = true;
            std::cout << "TRASC_BOT_RESULT " << result.dump() << std::endl;
            return 0;
        }

        // Do not boot a populated zone: no NPC spawns, doors, corpse updates,
        // network listeners, world connection or character login/save occurs.
        is_zone_loaded = true; // Makes this owner's local player quest discoverable, without a population or event loop.
        parse->ReloadQuests(true);
        owner = std::make_unique<Client>();
        Require(owner->PrepareTrascOfflineBotOwner(owner_id, account_id), "Could not load the selected owner's profile.");
        std::list<std::string> quest_errors_before;
        parse->GetErrors(quest_errors_before);
        Json result = {{"owner", requested_owner}, {"bots", Json::array()}};
        for (const auto& bot : bots) {
            const auto name = bot.at("name").get<std::string>();
            const auto bot_id = helper_bot_create(owner.get(), name, bot.at("class").get<uint8_t>(),
                bot.at("race").get<uint16_t>(), bot.at("gender").get<uint8_t>());
            Require(bot_id != 0, "The server rejected bot creation. Check name, race/class, owner level and creation limits.");
            Require(database.GetTrascQueryFailures() + content_db.GetTrascQueryFailures() == failures_before,
                "A bot state, starting item or quest database save failed; the batch was rolled back.");
            std::list<std::string> quest_errors;
            parse->GetErrors(quest_errors);
            Require(quest_errors == quest_errors_before, "The owner's bot creation quest failed; the batch was rolled back.");
            result["bots"].push_back({{"id", bot_id}, {"name", name}, {"class", bot.at("class")},
                {"race", bot.at("race")}, {"gender", bot.at("gender")}});
        }
        ValidateReceiptBots(result, owner_id);
        const auto serialized = result.dump();
        Query(fmt::format("INSERT INTO trasc_bot_creation_receipts(request_id,draft_hash,identity_hash,owner_id,result_json) VALUES('{}','{}','{}',{},'{}')",
            request_id, draft_hash, identity_hash, owner_id, database.Escape(serialized)));
        // Destruct the no-login owner before committing: destructor-side query
        // failures are also part of the atomic batch, and it cannot save a PP.
        owner.reset();
        is_zone_loaded = false;
        context.reset();
        zone = nullptr;
        Require(database.GetTrascQueryFailures() + content_db.GetTrascQueryFailures() == failures_before,
            "A bot creation cleanup operation failed; the batch was rolled back.");
        database.SetTrascAtomicBatch(false);
        content_db.SetTrascAtomicBatch(false);
        Query("COMMIT");
        transaction = false;
        result["format"] = 1;
        result["ok"] = true;
        result["reused"] = false;
        result["native_load_verified"] = true;
        std::cout << "TRASC_BOT_RESULT " << result.dump() << std::endl;
        return 0;
    } catch (const std::exception& error) {
        return reject(error.what());
    } catch (...) {
        // The native Perl parser can throw a string or a dangling const char*
        // during initialization. Do not dereference or expose that payload.
        return reject("The server could not initialize or create bots; no bots were committed. Check this world's quest parser dependencies and server logs.");
    }
}
} // namespace TrascBotBridge

bool Client::PrepareTrascOfflineBotOwner(uint32_t owner_id, uint32_t owner_account_id) {
    character_id = owner_id;
    account_id = owner_account_id;
    const auto account = AccountRepository::FindOne(database, account_id);
    if (!account.id || !database.LoadCharacterData(character_id, &m_pp, &m_epp)) return false;
    admin = account.status;
    lsaccountid = account.lsaccount_id;
    account_creation = account.time_creation;
    strn0cpy(account_name, account.name.c_str(), sizeof(account_name));
    strn0cpy(name, m_pp.name, sizeof(name));
    level = m_pp.level;
    race = m_pp.race;
    class_ = m_pp.class_;
    gender = m_pp.gender;
    deity = m_pp.deity;
    m_Position = glm::vec4(m_pp.x, m_pp.y, m_pp.z, m_pp.heading);
    current_hp = m_pp.cur_hp;
    current_mana = m_pp.mana;
    m_ClientVersion = EQ::versions::ClientVersion::RoF2;
    m_ClientVersionBit = EQ::versions::bitRoF2;
    m_inv.SetInventoryVersion(EQ::versions::MobVersion::RoF2);
    m_inv.SetGMInventory(GetGM());
    client_data_loaded = false; // Never write the character from this utility.
    // Upstream GetInventory returns false for a legitimately empty inventory.
    // Distinguish that owner from a failed load using an authoritative query.
    auto inventory = TrascBotBridge::Query(fmt::format("SELECT COUNT(*) FROM inventory WHERE character_id={}", character_id));
    if (inventory.RowCount() != 1 || !inventory.begin()[0]) return false;
    if (Strings::ToUnsignedInt(inventory.begin()[0])) {
        if (!database.GetInventory(this, true)) return false;
    } else if (!database.GetSharedBank(character_id, &m_inv, true, true)) {
        return false;
    }
    database.LoadCharacterSkills(character_id, &m_pp);
    database.LoadCharacterLanguages(character_id, &m_pp);
    database.LoadCharacterSpellBook(character_id, &m_pp);
    database.LoadCharacterMemmedSpells(character_id, &m_pp);
    database.LoadCharacterCurrency(character_id, &m_pp);
    database.LoadCharacterBindPoint(character_id, &m_pp);
    return true;
}
