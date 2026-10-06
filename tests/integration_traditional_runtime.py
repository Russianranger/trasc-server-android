"""Qualify real Traditional deployment, PEQ, local UDP login and zone startup.

Runs offline inside the native ARM64 Traditional image, using the app-built
nine executables and immutable public fixtures. No server or SQL mocks and no
proprietary client files are involved; device gameplay remains acceptance work.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, '/opt/trasc')
from engine import Engine, CLIENT_FILES, atomic_json
import traditional_build
import traditional_content
import traditional_runtime


PEQ_SHA256 = 'ac8649f23d2c3aea2cade138dfe10d46d1b21ad1a80d08ca95f5434fab7f218d'
QUESTS_SHA256 = 'a964618fecea89053265c8f21fabbb7404a0261d43662f4171f09ba0cca1c7f7'
MAP_SHA256 = '794b618d86852b47bd593424129aaf34eee326e5e3fec7290aeeb0e32bc41d20'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
FIXTURE_USER = 'integrationplayer'
FIXTURE_PASSWORD = 'qualification-password'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(root):
    return {str(path.relative_to(root)): sha256(path)
            for path in root.rglob('*') if path.is_file() and not path.is_symlink()}


def rows(engine, query):
    # The real CLI includes column headings; do not substitute a mock that
    # accidentally hides the server adapter's handling of the actual output.
    return engine.mysql(query).splitlines()[1:]


def login_cli(engine, evidence, label, *arguments, network_client=False):
    environment = dict(os.environ)
    if network_client:
        config = json.loads((engine.work / 'server/login.json').read_text())
        if config['general']['eqemu_loginserver_address'] != '127.0.0.1:5999':
            raise RuntimeError('The protocol client must target the isolated local login service')
        # The upstream arbitrary-credential client reads its configured address
        # only with LSPX. Apply this to the separate CLI process exclusively;
        # the live login service must continue authenticating the local source.
        environment['LSPX'] = '1'
    completed = subprocess.run(
        [str(engine.work / 'server/bin/loginserver'), *arguments],
        cwd=engine.work / 'server', stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=45, env=environment,
    )
    output = ANSI.sub('', completed.stdout + completed.stderr)
    (evidence / ('login-' + label + '.log')).write_text(output)
    if completed.returncode:
        raise RuntimeError('Real login CLI failed: ' + label + '\n' + output[-4000:])
    return output


def service_logs(engine):
    logs = list((engine.work / 'logs').glob('*.log'))
    logs += list((engine.work / 'server/logs').glob('*.log'))
    return '\n'.join(ANSI.sub('', path.read_text(errors='replace')) for path in logs)


def udp_login(engine, evidence, label, username=FIXTURE_USER, password=FIXTURE_PASSWORD):
    before = service_logs(engine)
    output = login_cli(engine, evidence, label, 'login-user:check-external-credentials',
                       username, password, network_client=True)
    found = re.findall(r'Credentials were (accepted|not accepted)\b', output)
    if len(found) != 1 or 'Deadline exceeded' in output:
        raise RuntimeError('Real local UDP credential client failed its protocol exchange: ' + output[-2000:])
    accepted = found[0] == 'accepted'
    if accepted:
        marker = 'account name [' + username + '] login server [local]'
        wait_for_log(engine, lambda text: text.count(marker) > before.count(marker),
                     'fresh successful local UDP authentication for ' + username)
    else:
        attempt = 'Attempting password based login [' + username + '] login [local]'
        failed = 'Successful login [false]'
        wait_for_log(engine, lambda text: (text.count(attempt) > before.count(attempt)
                                          and text.count(failed) > before.count(failed)),
                     'fresh local UDP password rejection for ' + username)
    return accepted


def wait_for_log(engine, predicate, description, seconds=120):
    deadline = time.monotonic() + seconds
    latest = ''
    while time.monotonic() < deadline:
        failed = [name for name, process in engine.processes.items()
                  if process.poll() is not None]
        if failed:
            raise RuntimeError('Traditional processes exited: ' + ', '.join(failed))
        latest = service_logs(engine)
        if predicate(latest):
            return latest
        time.sleep(0.5)
    raise RuntimeError('Timed out waiting for ' + description + '\n' + latest[-10000:])


def make_assets(engine):
    source = engine.source_root()
    archive = engine.work / 'incoming/server-assets.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for directory in ('utils/patches', 'loginserver/login_util'):
            for file in (source / directory).glob('*.conf'):
                target.write(file, 'EQEmu/' + directory + '/' + file.name)
    return archive.name


def qualify(args):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('Traditional runtime integration requires native ARM64')
    if 'LSPX' in os.environ:
        raise RuntimeError('The live fixture login service must use the local account source')
    for fixture, expected in ((args.database_zip, PEQ_SHA256),
                              (args.quests_zip, QUESTS_SHA256), (args.map, MAP_SHA256)):
        if sha256(fixture) != expected:
            raise RuntimeError('Immutable Traditional fixture hash mismatch: ' + fixture.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    evidence = args.output.parent
    report = {'format': 1, 'profile': 'traditional', 'architecture': 'arm64',
              'result': 'running', 'checks': {},
              'fixtures': {'peq_sha256': PEQ_SHA256, 'quests_sha256': QUESTS_SHA256,
                           'poknowledge_map_sha256': MAP_SHA256}}
    engine = Engine(args.work, 'traditional')
    custom = Engine(args.custom_work, 'custom')
    try:
        # Preserve original compilation evidence and give integration its own
        # credentials, DB files and workspace; copying uses no hard links.
        shutil.copytree(args.build_work / 'sources/current', engine.work / 'sources/current')
        shutil.copytree(args.build_work / 'server/bin.staged', engine.work / 'server/bin.staged')
        engine.config['workers'] = 1
        engine.config['ip'] = '127.0.0.1'
        engine.save()
        for relative, value in (('server/quests/custom-preserved.pl', b'custom quests\n'),
                                ('server/bin/custom-preserved', b'custom binaries\n'),
                                ('client/game/custom-preserved', b'custom client\n')):
            path = custom.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        custom_before = snapshot(custom.work)
        state = engine.state()['traditional']
        assert state['build']['staged_valid'], state
        assert not state['deployment']['deploy_allowed'], state
        report['checks']['preserved_065_067_staged_build_accepted'] = True

        archive = engine.work / 'incoming/peq.zip'
        shutil.copy2(args.database_zip, archive)
        bundles = [item for item in engine.database_candidates() if item['kind'] == 'peq_bundle']
        assert len(bundles) == 1 and len(bundles[0]['selections']) == 5
        engine.dispatch('import_database', {'selection': bundles[0]['id']})
        assert rows(engine, 'SELECT version,bots_version,custom_version FROM db_version;') == ['9328\t0\t0']
        item_count = int(rows(engine, 'SELECT COUNT(*) FROM items;')[0])
        spell_count = int(rows(engine, 'SELECT COUNT(*) FROM spells_new;')[0])
        assert item_count > 10000 and spell_count > 10000
        report['checks']['complete_user_equivalent_peq_seed_imported'] = {
            'items': item_count, 'spells': spell_count, 'schema': [9328, 0, 0]}

        quests = engine.work / 'incoming/quests.zip'
        shutil.copy2(args.quests_zip, quests)
        engine.dispatch('import_content', {'kind': 'quests', 'file': quests.name})
        components = traditional_content.components(engine)
        for kind in ('plugins', 'lua_modules'):
            assert components[kind]['imported'] and components[kind]['origin'] == 'quests', components
            assert components[kind]['path'] == 'server/quests/' + kind
        engine.dispatch('import_content', {'kind': 'assets', 'file': make_assets(engine)})
        maps = engine.work / 'incoming/maps.zip'
        with zipfile.ZipFile(maps, 'w', zipfile.ZIP_DEFLATED) as target:
            target.write(args.map, 'maps/base/poknowledge.map')
        engine.dispatch('import_maps', {'file': maps.name})
        assert engine.state()['traditional']['deployment']['deploy_allowed']
        report['checks']['quests_helpers_and_exact_server_assets_imported'] = True

        binaries_before = json.loads((engine.work / 'server/bin.staged/verification.json').read_text())['binaries']
        deployed = engine.dispatch('deploy', {})
        assert deployed['deployed'] and deployed['database_version'] == 9328
        assert (engine.work / deployed['database_backup']).stat().st_size > 0
        assert engine.state()['traditional']['deployment']['start_allowed']
        assert json.loads((engine.work / 'server/bin/verification.json').read_text())['binaries'] == binaries_before
        config = json.loads((engine.work / 'server/eqemu_config.json').read_text())['server']
        assert config['database']['db'] == config['content_database']['db'] == 'peq'
        assert config['directories']['plugins'] == 'quests/plugins'
        assert config['directories']['lua_modules'] == 'quests/lua_modules'
        assert config['directories']['patches'] == 'assets/patches'
        assert config['directories']['opcodes'] == 'assets/opcodes'
        assert config['auto_database_updates'] is False
        login = json.loads((engine.work / 'server/login.json').read_text())
        assert login['general']['default_loginserver_name'] == 'local'
        assert login['database']['db'] == 'peq' and login['security']['mode'] == 14
        assert login['web_api']['enabled'] is False
        report['checks']['backed_up_deployment_and_local_config'] = True

        # Explicit, synthetic CI credentials. None belong to a user or survive
        # in an online runtime; the downloaded rootfs has no integration DB.
        login_cli(engine, evidence, 'create', 'login-user:create', FIXTURE_USER, FIXTURE_PASSWORD)
        correct = login_cli(engine, evidence, 'valid-password', 'login-user:check-credentials',
                            FIXTURE_USER, FIXTURE_PASSWORD)
        wrong = login_cli(engine, evidence, 'wrong-password', 'login-user:check-credentials',
                          FIXTURE_USER, 'deliberately-wrong-fixture-password')
        assert re.search(r'Credentials were accepted\b', correct), correct
        assert 'Credentials were not accepted' in wrong, wrong
        account = rows(engine, "SELECT id,source_loginserver FROM login_accounts WHERE account_name='integrationplayer';")
        assert len(account) == 1 and account[0].split('\t')[1] == 'local', account
        account_id = account[0].split('\t')[0]
        report['checks']['real_argon2_account_accept_and_reject'] = True

        exported = engine.dispatch('export_client', {})
        with zipfile.ZipFile(engine.work / exported['file']) as bundle:
            for filename in CLIENT_FILES:
                data = bundle.read(filename)
                assert data and data == bundle.read('Resources/' + filename)
                assert hashlib.sha256(data).hexdigest() == exported['sha256'][filename]
        report['checks']['real_four_file_database_export'] = exported['sha256']

        # One real static PoK zone exercises PEQ zone tables, both quest engines,
        # the imported geometry and the configured launcher binary path.
        engine.mysql("INSERT INTO launcher_zones (launcher,zone,port) VALUES ('traditional','poknowledge',7000) ON DUPLICATE KEY UPDATE port=VALUES(port);")
        started = engine.dispatch('start', {})
        assert started['endpoint'] == '127.0.0.1:5999'
        wait_for_log(engine, lambda text: 'short_name [Traditional] successfully authenticated' in text,
                     'world registration with local login')
        wait_for_log(engine, lambda text: 'Zone server [poknowledge] listening on port [7000]' in text,
                     'real static PoK zone startup', seconds=240)
        shared = [path for path in (engine.work / 'server/shared').iterdir()
                  if path.is_file() and path.stat().st_size]
        assert len(shared) >= 2, shared
        assert udp_login(engine, evidence, 'udp-valid'), 'Real local UDP encrypted login was rejected'
        login_cli(engine, evidence, 'change-fixture', 'login-user:update-credentials',
                  FIXTURE_USER, 'deliberately-wrong-fixture-password')
        assert not udp_login(engine, evidence, 'udp-rejected'), 'Wrong password was accepted by UDP login'
        login_cli(engine, evidence, 'restore-fixture', 'login-user:update-credentials',
                  FIXTURE_USER, FIXTURE_PASSWORD)
        assert udp_login(engine, evidence, 'udp-restored')
        report['checks']['real_udp_session_des_login_accept_and_reject'] = {
            'accepted': True, 'wrong_password_rejected': True, 'restored_password_accepted': True,
            'endpoint': '127.0.0.1:5999', 'source': 'local'}
        assert rows(engine, "SELECT id FROM login_accounts WHERE account_name='integrationautocreate';") == []
        assert udp_login(engine, evidence, 'udp-autocreate', 'integrationautocreate', 'new-fixture-password')
        created = rows(engine, "SELECT id,source_loginserver FROM login_accounts WHERE account_name='integrationautocreate';")
        assert len(created) == 1 and created[0].split('\t')[1] == 'local', created
        report['checks']['first_udp_login_creates_local_account'] = True
        report['checks']['world_and_static_zone_running'] = True
        report['checks']['real_shared_memory_generated'] = {path.name: path.stat().st_size for path in shared}
        engine.dispatch('stop', {})
        assert not engine.server_running()

        # A second activation plus rollback tests actual qualified directories,
        # their receipts and DB backups rather than substituting dummy ELF files.
        first_receipt = json.loads((engine.work / 'server/bin/deployment.json').read_text())
        shutil.copytree(engine.work / 'server/bin', engine.work / 'server/bin.staged')
        engine.dispatch('deploy', {})
        second_receipt = json.loads((engine.work / 'server/bin/deployment.json').read_text())
        assert first_receipt['transaction'] != second_receipt['transaction']
        assert engine.state()['traditional']['deployment']['rollback_allowed']
        engine.dispatch('rollback', {})
        assert json.loads((engine.work / 'server/bin/deployment.json').read_text())['transaction'] == first_receipt['transaction']
        assert rows(engine, "SELECT id FROM login_accounts WHERE account_name='integrationplayer';") == [account_id]
        report['checks']['qualified_redeployment_and_binary_rollback_preserve_account'] = True
        engine.dispatch('start', {})
        assert udp_login(engine, evidence, 'udp-restarted')
        engine.dispatch('stop', {})
        assert not engine.server_running()
        report['checks']['same_database_stop_restart_login'] = True
        assert snapshot(custom.work) == custom_before, 'Traditional modified the Custom workspace'
        assert custom.config['database'] == 'triune' and engine.config['database'] == 'peq'
        report['checks']['custom_files_and_configuration_unchanged'] = True
        report['result'] = 'passed'
    except BaseException as error:
        report['result'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        engine.shutdown()
        custom.shutdown()
        atomic_json(args.output, report)
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--build-work', type=Path, required=True)
    parser.add_argument('--custom-work', type=Path, required=True)
    parser.add_argument('--database-zip', type=Path, required=True)
    parser.add_argument('--quests-zip', type=Path, required=True)
    parser.add_argument('--map', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    qualify(parser.parse_args())
