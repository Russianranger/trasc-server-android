"""Real MariaDB player migration: newer schema/content, binary and Unicode data."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile
sys.path.insert(0,'/opt/trasc')
from engine import Engine
import player_data

with tempfile.TemporaryDirectory(prefix='players-',dir='/work') as temp:
    root=Path(temp); engine=Engine(root)
    try:
        seed='''CREATE TABLE account(id int PRIMARY KEY, name varchar(64), password varchar(128));
CREATE TABLE login_accounts(id int PRIMARY KEY, account_name varchar(64));
CREATE TABLE character_data(id int PRIMARY KEY, account_id int, name varchar(64), platinum bigint, note text, raw_data varbinary(64), optional_text text);
CREATE TABLE inventory(character_id int, slot_id int, item_id int, PRIMARY KEY(character_id,slot_id));
CREATE TABLE character_data_extra(character_id int PRIMARY KEY, progress decimal(12,3));
CREATE TABLE rule_sets(ruleset_id int PRIMARY KEY,name varchar(64));
CREATE TABLE rule_values(ruleset_id int,rule_name varchar(64),rule_value varchar(64));
CREATE TABLE variables(varname varchar(64),value varchar(64));
CREATE TABLE launcher(name varchar(64));
CREATE TABLE spells_new(id int PRIMARY KEY,name varchar(64));
INSERT INTO spells_new VALUES(26,'New world spell');
'''
        initial=seed+'''INSERT INTO account VALUES(0,'zero-account','test-hash'),(12,'fixture-account','hash-unchanged');
INSERT INTO login_accounts VALUES(12,'fixture-login');
INSERT INTO character_data VALUES(77,12,'Zöe',123456789,'tab\tline\nquote\' \\ end',X'00FF010A',NULL);
INSERT INTO inventory VALUES(77,23,12345);
INSERT INTO character_data_extra VALUES(77,123.456);
'''
        # Avoid SQL literal escaping ambiguity in the fixture itself.
        initial=seed+"INSERT INTO account VALUES(0,'zero-account','test-hash'),(12,'fixture-account','hash-unchanged'); INSERT INTO login_accounts VALUES(12,'fixture-login'); INSERT INTO character_data VALUES(77,12,CONVERT(X'5AC3B665' USING utf8mb4),123456789,CONVERT(X'746162096C696E650A71756F746527205C20656E64' USING utf8mb4),X'00FF010A',NULL); INSERT INTO inventory VALUES(77,23,12345); INSERT INTO character_data_extra VALUES(77,123.456);"
        (root/'incoming/initial.sql').write_text(initial)
        engine.import_database({'selection':'incoming/initial.sql'})
        before=engine.mysql('SELECT id,account_id,HEX(name),platinum,HEX(note),HEX(raw_data),optional_text FROM character_data;')
        exported=player_data.export_players(engine,{})
        assert exported['accounts']==2 and exported['characters']==1
        newer=seed.replace('optional_text text','optional_text text, new_flag int NOT NULL DEFAULT 7').replace('New world spell','Updated world spell')
        (root/'incoming/newer.sql').write_text(newer)
        updated=engine.import_database({'selection':'incoming/newer.sql','replace':True})
        assert updated['player_backup'] and (root/updated['player_backup']).is_file()
        preview=player_data.preview_players(engine,{'file':exported['file']})
        assert preview['compatible'] and any('new_flag' in x for x in preview['changes'])
        restored=player_data.restore_players(engine,{'file':exported['file'],'sha256':preview['sha256'],'replace':True})
        assert (root/restored['database_backup']).is_file()
        assert engine.mysql('SELECT id,account_id,HEX(name),platinum,HEX(note),HEX(raw_data),optional_text FROM character_data;')==before
        assert engine.mysql('SELECT new_flag FROM character_data;').splitlines()[1]=='7'
        assert engine.mysql('SELECT id FROM account ORDER BY id;').splitlines()[1:]==['0','12']
        assert engine.mysql('SELECT progress FROM character_data_extra;').splitlines()[1]=='123.456'
        assert engine.mysql('SELECT item_id FROM inventory;').splitlines()[1]=='12345'
        assert engine.mysql('SELECT name FROM spells_new;').splitlines()[1]=='Updated world spell'
        print('PASS: real player snapshot survives new schema/defaults; account IDs, Unicode, binary, NULL, money, inventory and custom progression round-trip; newer world content remains',flush=True)
        damaged=root/'incoming/damaged.zip'
        with zipfile.ZipFile(root/exported['file']) as src, zipfile.ZipFile(damaged,'w') as out:
            for entry in src.infolist():
                data=src.read(entry.filename)
                if entry.filename=='tables/character_data.tsv': data=data.replace(b'H3737',b'H3738')
                out.writestr(entry.filename,data)
        proof=player_data.preview_players(engine,{'file':'incoming/damaged.zip'})
        try:
            player_data.restore_players(engine,{'file':proof['file'],'sha256':proof['sha256'],'replace':True})
            raise AssertionError('Damaged snapshot was accepted')
        except ValueError as error: assert 'checksum' in str(error)
        assert engine.mysql('SELECT id,account_id,HEX(name),platinum,HEX(note),HEX(raw_data),optional_text FROM character_data;')==before
        engine.mysql('ALTER TABLE character_data DROP COLUMN note;')
        blocked=player_data.preview_players(engine,{'file':exported['file']})
        assert not blocked['compatible'] and any('note' in x for x in blocked['problems'])
        print('PASS: corrupt snapshot never changes live player rows; removed-column migration is blocked before replacement',flush=True)
    except Exception:
        log=root/'logs/operation.log'
        if log.exists(): print(log.read_text()[-6000:],file=sys.stderr)
        raise
    finally: engine.shutdown()
