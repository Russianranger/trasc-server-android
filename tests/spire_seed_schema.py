"""Check the real published seed's DDL without importing its player data."""
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from engine import Engine
import spire

with zipfile.ZipFile(sys.argv[1]) as archive:
    with archive.open('release-peq.sql') as source:
        definitions={}; collecting=None; lines=[]
        for raw in source:
            line=raw.decode('utf-8',errors='replace')
            match=re.match(r'CREATE TABLE `([^`]+)`',line)
            if match and match[1] in spire.CATALOG: collecting=match[1];lines=[]
            if collecting:
                lines.append(line)
                if line.rstrip().endswith(';'):
                    definitions[collecting]=''.join(lines);collecting=None
assert set(definitions)==set(spire.CATALOG),set(spire.CATALOG)-set(definitions)
with tempfile.TemporaryDirectory(prefix='spire-schema-') as temp:
    engine=Engine(temp);engine.config['database']='spire_schema_test';engine.config['database_imported']=True
    engine.mysql_options.write_text('[client]\nuser=root\npassword=test\nprotocol=tcp\nhost=127.0.0.1\nport='+os.environ['TRASC_TEST_MYSQL_PORT']+'\ndefault-character-set=utf8mb4\n')
    engine.ensure_db=lambda:None
    try:
        engine.mysql('CREATE DATABASE spire_schema_test;',database=False)
        engine.mysql('SET FOREIGN_KEY_CHECKS=0;'+''.join(definitions.values()))
        for table in spire.CATALOG:
            s=spire.schema(engine,table)
            print(table,s['engine'],s['key'],s['read_only'],flush=True)
            assert not s['read_only'],(table,s['read_only'])
            assert spire.search(engine,{'table':table})['records']==[]
        print('PASS: real published seed schemas support all twelve content editors',flush=True)
    finally:
        engine.mysql('DROP DATABASE IF EXISTS spire_schema_test;',database=False)
        engine.shutdown()
