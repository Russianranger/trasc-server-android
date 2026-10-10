-- Exact additive migrations from Russianranger/Servertakp 25bf70acb6bd24853cf09e447ddd62b96a4491a4.
-- Isolated test database only; production Bots never applies these migrations.

-- 001_bot_records.sql
-- Additive installation: run against the destination server's existing peq.
-- Does not replace player records, change account access, or import a snapshot.
CREATE TABLE IF NOT EXISTS takp_bot_data (
 id INT UNSIGNED NOT NULL AUTO_INCREMENT,
 owner_character_id INT UNSIGNED NOT NULL,
 name VARCHAR(15) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
 class TINYINT UNSIGNED NOT NULL,
 race SMALLINT UNSIGNED NOT NULL,
 gender TINYINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (id), UNIQUE KEY bot_name (name), KEY bot_owner (owner_character_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_schema (
 version INT UNSIGNED NOT NULL PRIMARY KEY,
 installed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES (1);


-- 002_bot_runtime.sql
-- Additive, repeatable. Run after 001, against each destination's own database.
CREATE TABLE IF NOT EXISTS takp_bot_runtime (
 bot_id INT UNSIGNED NOT NULL PRIMARY KEY,
 active TINYINT UNSIGNED NOT NULL DEFAULT 0,
 hp INT NOT NULL DEFAULT -1,
 mana INT NOT NULL DEFAULT -1,
 generation INT UNSIGNED NOT NULL DEFAULT 0,
 stance TINYINT UNSIGNED NOT NULL DEFAULT 1,
 saved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_inventory (
 bot_id INT UNSIGNED NOT NULL,
 slot SMALLINT UNSIGNED NOT NULL,
 item_id INT UNSIGNED NOT NULL,
 charges SMALLINT UNSIGNED NOT NULL,
 PRIMARY KEY(bot_id,slot)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(2);


-- 003_bot_spell_state.sql
CREATE TABLE IF NOT EXISTS takp_bot_buffs (
 bot_id INT UNSIGNED NOT NULL, slot SMALLINT UNSIGNED NOT NULL,
 spell_id SMALLINT UNSIGNED NOT NULL, caster_level TINYINT UNSIGNED NOT NULL,
 ticks INT NOT NULL, counters INT NOT NULL, melee_rune INT UNSIGNED NOT NULL,
 magic_rune INT UNSIGNED NOT NULL, instrument_mod SMALLINT NOT NULL,
 PRIMARY KEY(bot_id,slot)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_recasts (
 bot_id INT UNSIGNED NOT NULL, spell_id SMALLINT UNSIGNED NOT NULL,
 available_at DATETIME(3) NOT NULL,
 PRIMARY KEY(bot_id,spell_id)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(3);


-- 004_bot_features.sql
-- Additive bot-only state; safe to repeat against each destination database.
CREATE TABLE IF NOT EXISTS takp_bot_settings (
 bot_id INT UNSIGNED PRIMARY KEY,
 ranged_mode TINYINT UNSIGNED NOT NULL DEFAULT 0,
 taunt_enabled TINYINT UNSIGNED NOT NULL DEFAULT 0,
 pet_enabled TINYINT UNSIGNED NOT NULL DEFAULT 1,
 follow_distance INT UNSIGNED NOT NULL DEFAULT 100,
 PRIMARY_ROLE VARCHAR(16) NOT NULL DEFAULT 'balanced'
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_supplies (
 bot_id INT UNSIGNED NOT NULL, item_id INT UNSIGNED NOT NULL,
 quantity INT UNSIGNED NOT NULL,
 PRIMARY KEY(bot_id,item_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_pets (
 bot_id INT UNSIGNED PRIMARY KEY, spell_id SMALLINT UNSIGNED NOT NULL,
 hp INT NOT NULL, mana INT NOT NULL, name VARCHAR(63) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_pet_buffs (
 bot_id INT UNSIGNED NOT NULL, slot SMALLINT UNSIGNED NOT NULL,
 spell_id SMALLINT UNSIGNED NOT NULL, caster_level TINYINT UNSIGNED NOT NULL,
 ticks INT NOT NULL, counters INT NOT NULL, melee_rune INT UNSIGNED NOT NULL,
 magic_rune INT UNSIGNED NOT NULL, instrument_mod SMALLINT NOT NULL,
 PRIMARY KEY(bot_id,slot)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_pet_items (
 bot_id INT UNSIGNED NOT NULL, slot SMALLINT UNSIGNED NOT NULL,
 item_id INT UNSIGNED NOT NULL, PRIMARY KEY(bot_id,slot)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_songs (
 bot_id INT UNSIGNED NOT NULL, position TINYINT UNSIGNED NOT NULL,
 spell_id SMALLINT UNSIGNED NOT NULL, PRIMARY KEY(bot_id,position)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(4);


-- 005_bot_configuration.sql
CREATE TABLE IF NOT EXISTS takp_bot_options (
 bot_id INT UNSIGNED NOT NULL, setting VARCHAR(32) NOT NULL,
 value INT NOT NULL, PRIMARY KEY(bot_id,setting)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_spell_settings (
 bot_id INT UNSIGNED NOT NULL, spell_id SMALLINT UNSIGNED NOT NULL,
 enabled TINYINT UNSIGNED NOT NULL DEFAULT 1,
 min_hp TINYINT UNSIGNED NOT NULL DEFAULT 0,
 max_hp TINYINT UNSIGNED NOT NULL DEFAULT 100,
 priority SMALLINT NOT NULL DEFAULT 0,
 PRIMARY KEY(bot_id,spell_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_blocked_buffs (
 bot_id INT UNSIGNED NOT NULL, spell_id SMALLINT UNSIGNED NOT NULL,
 PRIMARY KEY(bot_id,spell_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_heal_rotations (
 leader_bot_id INT UNSIGNED PRIMARY KEY,
 owner_character_id INT UNSIGNED NOT NULL,
 enabled TINYINT UNSIGNED NOT NULL DEFAULT 0,
 interval_ms INT UNSIGNED NOT NULL DEFAULT 3000,
 next_member INT UNSIGNED NOT NULL DEFAULT 0,
 next_cast_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_heal_rotation_members (
 leader_bot_id INT UNSIGNED NOT NULL, bot_id INT UNSIGNED NOT NULL,
 PRIMARY KEY(leader_bot_id,bot_id), UNIQUE KEY one_rotation_per_bot(bot_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS takp_bot_heal_rotation_targets (
 leader_bot_id INT UNSIGNED NOT NULL, name VARCHAR(63) NOT NULL,
 PRIMARY KEY(leader_bot_id,name)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(5);


-- 006_bot_abilities.sql
CREATE TABLE IF NOT EXISTS takp_bot_ability_recasts (
 bot_id INT UNSIGNED NOT NULL, kind VARCHAR(8) NOT NULL, ability_id INT UNSIGNED NOT NULL,
 ready_at DATETIME NOT NULL, PRIMARY KEY(bot_id,kind,ability_id)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(6);


-- 007_bot_name_reservations.sql
-- Additive shared name reservations. Existing collisions abort rather than rename/delete characters.
-- MariaDB 10.3+. Stop all world/zone processes before installing or rerunning.
CREATE TABLE IF NOT EXISTS takp_bot_name_registry (
 name VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL PRIMARY KEY,
 kind VARCHAR(8) NOT NULL,
 entity_id INT UNSIGNED NOT NULL,
 UNIQUE KEY entity_name(kind,entity_id)
) ENGINE=InnoDB;
DELIMITER //
BEGIN NOT ATOMIC
 IF (SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()
     AND TABLE_NAME IN ('character_data','character_inventory','takp_bot_data','takp_bot_name_registry')
     AND ENGINE='InnoDB') <> 4 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Bot name reservations require character_data, character_inventory and bot tables to use InnoDB';
 END IF;
 IF EXISTS (
  SELECT shared_name FROM (
   SELECT CONVERT(name USING utf8mb4) COLLATE utf8mb4_general_ci AS shared_name FROM character_data WHERE name<>''
   UNION ALL
   SELECT CONVERT(name USING utf8mb4) COLLATE utf8mb4_general_ci FROM takp_bot_data
  ) AS names GROUP BY shared_name HAVING COUNT(*) > 1
 ) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Character/bot name collision: resolve conflicting names before migration 007';
 END IF;
 IF EXISTS (
  SELECT 1 FROM takp_bot_name_registry AS r LEFT JOIN (
   SELECT CONVERT(name USING utf8mb4) COLLATE utf8mb4_general_ci AS shared_name,'player' AS kind,id FROM character_data WHERE name<>''
   UNION ALL
   SELECT CONVERT(name USING utf8mb4) COLLATE utf8mb4_general_ci,'bot',id FROM takp_bot_data
  ) AS names ON r.kind=names.kind AND r.entity_id=names.id
  WHERE names.id IS NULL OR CONVERT(r.name USING utf8mb4) COLLATE utf8mb4_general_ci <> names.shared_name
 ) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Stale bot name reservation: repair inconsistent registry entries before migration 007';
 END IF;
END//
DELIMITER ;
-- Ensure an existing installation also reserves names without regard to case,
-- even when its database default uses a binary/case-sensitive collation.
ALTER TABLE takp_bot_name_registry MODIFY name VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL;
INSERT INTO takp_bot_name_registry(name,kind,entity_id)
 SELECT name,'player',id FROM character_data WHERE name<>''
 ON DUPLICATE KEY UPDATE name=IF(kind=VALUES(kind) AND entity_id=VALUES(entity_id),VALUES(name),NULL);
INSERT INTO takp_bot_name_registry(name,kind,entity_id)
 SELECT name,'bot',id FROM takp_bot_data
 ON DUPLICATE KEY UPDATE name=IF(kind=VALUES(kind) AND entity_id=VALUES(entity_id),VALUES(name),NULL);
DELIMITER //
CREATE OR REPLACE TRIGGER takp_bot_player_name_insert AFTER INSERT ON character_data FOR EACH ROW
BEGIN
 IF NEW.name<>'' THEN INSERT INTO takp_bot_name_registry VALUES(NEW.name,'player',NEW.id); END IF;
END//
CREATE OR REPLACE TRIGGER takp_bot_player_name_update AFTER UPDATE ON character_data FOR EACH ROW
BEGIN
 IF NOT (NEW.name<=>OLD.name) THEN
  DELETE FROM takp_bot_name_registry WHERE kind='player' AND entity_id=OLD.id;
  IF NEW.name<>'' THEN INSERT INTO takp_bot_name_registry VALUES(NEW.name,'player',NEW.id); END IF;
 END IF;
END//
CREATE OR REPLACE TRIGGER takp_bot_player_name_delete AFTER DELETE ON character_data FOR EACH ROW
BEGIN DELETE FROM takp_bot_name_registry WHERE kind='player' AND entity_id=OLD.id; END//
CREATE OR REPLACE TRIGGER takp_bot_name_insert AFTER INSERT ON takp_bot_data FOR EACH ROW
BEGIN INSERT INTO takp_bot_name_registry VALUES(NEW.name,'bot',NEW.id); END//
CREATE OR REPLACE TRIGGER takp_bot_name_update AFTER UPDATE ON takp_bot_data FOR EACH ROW
BEGIN
 IF NOT (NEW.name<=>OLD.name) THEN
  DELETE FROM takp_bot_name_registry WHERE kind='bot' AND entity_id=OLD.id;
  INSERT INTO takp_bot_name_registry VALUES(NEW.name,'bot',NEW.id);
 END IF;
END//
CREATE OR REPLACE TRIGGER takp_bot_name_delete AFTER DELETE ON takp_bot_data FOR EACH ROW
BEGIN DELETE FROM takp_bot_name_registry WHERE kind='bot' AND entity_id=OLD.id; END//
DELIMITER ;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(7);


-- 008_bot_groups.sql
CREATE TABLE IF NOT EXISTS takp_bot_saved_groups (
 owner_character_id INT UNSIGNED NOT NULL,
 name VARCHAR(32) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
 bot_id INT UNSIGNED NOT NULL,
 PRIMARY KEY(owner_character_id,name,bot_id), KEY bot_member(bot_id)
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(8);


-- 009_bot_formation.sql
CREATE TABLE IF NOT EXISTS takp_bot_owner_settings (
 owner_character_id INT UNSIGNED NOT NULL PRIMARY KEY,
 formation_enabled TINYINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(9);


-- 010_bot_formation_modes.sql
ALTER TABLE takp_bot_owner_settings ADD COLUMN IF NOT EXISTS formation_gather TINYINT UNSIGNED NOT NULL DEFAULT 0;
ALTER TABLE takp_bot_owner_settings ADD COLUMN IF NOT EXISTS formation_line TINYINT UNSIGNED NOT NULL DEFAULT 0;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(10);


-- 011_bot_keep_pace.sql
ALTER TABLE takp_bot_owner_settings ADD COLUMN IF NOT EXISTS keep_pace TINYINT UNSIGNED NOT NULL DEFAULT 0;
INSERT IGNORE INTO takp_bot_schema(version) VALUES(11);

