"""Read-only local Custom world entry checks and combined repair status."""
import ipaddress

import client_compatibility
import client_connection
import client_dll
import client_spellbook


def decorate(engine, result):
    result['requirements'] = client_compatibility.requirements(engine)
    if result['requirements'].get('known_deployed') and result['requirements'].get('required_spellbook_slots') == 720:
        result['can_apply'] = False
        result['warning'] = 'The verified deployed server uses a 720-slot spellbook. Deploy the matching updated server before applying the 1,440-slot client patch.'
    try:
        result['dll'] = client_dll.compiler_status(engine)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result['dll'] = {'source': {'available': False, 'error': str(error)},
                         'freshness': {'installed': {'state': 'unknown', 'reason': str(error)}}}
    return result


def status(engine, args=None):
    return decorate(engine, client_spellbook.status(engine, args))


def preflight(engine, args=None):
    args = args or {}
    result = {'profile': engine.profile, 'allowed': True, 'requires_confirmation': False,
              'message': '', 'warnings': []}
    def warn(message):
        result.update(requires_confirmation=True, message=message)
        result['warnings'].append(message)
    if engine.profile != 'custom' or args.get('mode', 'client') != 'client':
        return result
    requirements = client_compatibility.requirements(engine)
    result['requirements'] = requirements
    try:
        host = client_connection.status(engine)['host']
        address = host.get('host', '')
        local = address.lower() == 'localhost' or ipaddress.ip_address(address).is_loopback
    except (OSError, ValueError, KeyError, AttributeError):
        local = False
    if not local or not requirements['known_deployed']:
        result['warnings'].append('World entry compatibility is not established for this connection; selected source alone does not identify the deployed server.')
        return result
    executable = client_spellbook.status(engine)
    result['exe_patched'] = executable['patched']
    slots = requirements['required_spellbook_slots']
    if slots == 1440:
        if not executable['patched']:
            warn('This local Custom server uses a 1,440-slot spellbook, but the executable has not been verified with that layout. Entering the world may freeze. You can continue, or stop the server/client and apply the 1,440-slot patch and matching DLL from Client.')
        elif not args.get('native_dinput8', True):
            warn('Native dinput8.dll is disabled for this 1,440-slot Custom server. Client features or world entry may not work as expected. You can continue, or enable the matching DLL in Client settings.')
        else:
            dll = client_dll.compiler_status(engine)
            installed = dll.get('freshness', {}).get('installed', {})
            result['dll_state'] = installed.get('state', 'unknown')
            paired_with_deployed = (result['dll_state'] == 'stale'
                and installed.get('hash_verified') is True
                and installed.get('source_identity_verified') is True
                and installed.get('source_commit') is not None
                and installed['source_commit'] == requirements.get('deployed_source_commit'))
            if result['dll_state'] == 'current':
                result['dll_evidence'] = 'selected_source_current'
            elif paired_with_deployed:
                # Refreshing source does not deploy a new server. Keep the
                # proven installed client/server pair usable while the newly
                # selected checkout is waiting to be built and deployed.
                result['dll_evidence'] = 'verified_deployed_source_receipt'
                result['dll_source_commit'] = installed['source_commit']
                result['warnings'].append('The installed DLL is verified against the deployed server revision. Selected source has changed; rebuild the DLL when deploying that source.')
            else:
                warn('The installed Custom client DLL has not been verified against the selected source. Entering this updated server may freeze. You can continue, or use Client → Compile dinput8.dll → Deploy staged DLL to prepare the matching DLL.')
    elif slots == 720 and executable['patched']:
        warn('This verified local server uses a 720-slot spellbook and the client has the 1,440-slot patch. Entering the world may freeze. You can continue, or use matching server/client versions.')
    return result
