#!/usr/bin/env python3
"""Search, describe, and invoke Dokploy endpoints without an MCP server."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

CATALOG = Path(__file__).resolve().parents[1] / 'assets/endpoints.json'
CONFIG_FIELDS = ('DOKPLOY_URL', 'DOKPLOY_API_KEY', 'DOKPLOY_CUSTOM_HEADERS', 'DOKPLOY_TIMEOUT')


def config_path():
    return Path(os.environ.get('DOKPLOY_CONFIG', str(Path.home() / '.config/dokploy/config.json'))).expanduser()


def load_config():
    path = config_path()
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) - set(CONFIG_FIELDS):
        raise ValueError('Configuration must be an object containing only supported DOKPLOY_* fields')
    return value


def connection_config():
    value = load_config()
    return {**value, **{k: os.environ[k] for k in CONFIG_FIELDS if k in os.environ}}


def validate_connection(config):
    url = config.get('DOKPLOY_URL', '')
    key = config.get('DOKPLOY_API_KEY', '')
    if not isinstance(url, str) or not isinstance(key, str):
        raise ValueError('Dokploy URL and API key must be strings')
    url = url.rstrip('/')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('DOKPLOY_URL must be an HTTP(S) instance base URL without credentials, query, or fragment; run configure')
    if parsed.path.rstrip('/').endswith('/api'):
        raise ValueError('DOKPLOY_URL must not include /api')
    if not key.strip():
        raise ValueError('DOKPLOY_API_KEY is required; run configure')
    custom = config.get('DOKPLOY_CUSTOM_HEADERS', {})
    if isinstance(custom, str):
        custom = json.loads(custom)
    if not isinstance(custom, dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) for k, v in custom.items()):
        raise ValueError('DOKPLOY_CUSTOM_HEADERS must be an object of string headers')
    if any(k.lower() in ('x-api-key', 'content-type', 'accept') for k in custom):
        raise ValueError('Custom headers cannot override authentication or content headers')
    try:
        timeout = float(config.get('DOKPLOY_TIMEOUT', 30000)) / 1000
    except (ValueError, TypeError):
        raise ValueError('DOKPLOY_TIMEOUT must be a positive number of milliseconds') from None
    if not 0 < timeout < float('inf'):
        raise ValueError('DOKPLOY_TIMEOUT must be a positive number of milliseconds')
    return url, key, custom, timeout


def save_config(value):
    if not isinstance(value, dict) or set(value) - set(CONFIG_FIELDS):
        raise ValueError('Configuration must be an object containing only supported DOKPLOY_* fields')
    validate_connection(value)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Atomic replacement never exposes a partially written credential file.
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.dokploy-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
SECRET_FIELDS = ('env buildArgs composeFile dockerCompose environment buildSecrets previewBuildSecrets password currentPassword appPassword databasePassword databaseRootPassword redisPassword mariadbPassword mongoPassword mysqlPassword postgresPassword registryPassword token accessToken appToken apiToken botToken refreshToken secret clientSecret apiKey secretAccessKey accessKey licenseKey userKey privateKey privateKeyPass encPrivateKey encPrivateKeyPass sshKey sshPrivateKey customGitSSHKey dockerAuth').lower().split()


def redact(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if v is not None and any(k.lower().endswith(s) for s in SECRET_FIELDS) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def reject_markers(value):
    if isinstance(value, (dict, list)):
        for v in value.values() if isinstance(value, dict) else value:
            reject_markers(v)
    elif value == '[REDACTED]':
        raise ValueError('Refusing to write a redaction placeholder')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward API credentials to a redirect target.


def invoke(operation, payload):
    url, key, custom, timeout = validate_connection(connection_config())
    headers = {**custom, 'x-api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
    target = url + '/api' + operation['path']
    body = None
    if operation['method'] == 'GET':
        # Match scalar query encoding; refuse ambiguous structured parameters.
        if any(isinstance(v, (dict, list)) for v in payload.values()):
            raise ValueError('Structured GET parameters are not supported by this adapter')
        query = {k: str(v).lower() if isinstance(v, bool) else v for k, v in payload.items() if v is not None}
        target += ('?' + urllib.parse.urlencode(query)) if query else ''
    else:
        reject_markers(payload)
        body = json.dumps(payload).encode()
    request = urllib.request.Request(target, data=body, headers=headers, method=operation['method'])
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read().decode()
            data = json.loads(raw) if raw else None
            return {'success': True, 'data': redact(data)}
    except urllib.error.HTTPError as error:
        # Error bodies can contain echoed credentials or arbitrary secret-bearing text.
        return {'success': False, 'status': error.code, 'error': 'Dokploy HTTP request failed; response body withheld'}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {'success': False, 'error': 'Network failure or timeout; mutation outcome may be unknown. Inspect state before retrying.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    configure = commands.add_parser('configure', help='Save connection settings locally (API key input is hidden)')
    configure.add_argument('--input', help='JSON file, or - for stdin; replaces saved settings')
    commands.add_parser('config-status', help='Check connection configuration without displaying secrets')
    search = commands.add_parser('search')
    search.add_argument('query', nargs='?', default='')
    search.add_argument('--tag')
    search.add_argument('--limit', type=int, default=20)
    describe = commands.add_parser('describe')
    describe.add_argument('operation')
    call = commands.add_parser('call')
    call.add_argument('operation')
    call.add_argument('--input', default='-', help='JSON file, or - for stdin; avoid secrets in command arguments')
    args = parser.parse_args()
    if args.command == 'configure':
        if args.input:
            value = json.load(sys.stdin) if args.input == '-' else json.loads(Path(args.input).read_text())
        else:
            if not sys.stdin.isatty():
                raise ValueError('Interactive configure requires a terminal; use --input - for secure JSON stdin')
            value = {'DOKPLOY_URL': input('Dokploy base URL (without /api): ').strip(),
                     'DOKPLOY_API_KEY': getpass.getpass('Dokploy API key: '),
                     'DOKPLOY_CUSTOM_HEADERS': json.loads(getpass.getpass('Custom headers as JSON (optional; Enter for {}): ') or '{}')}
        save_config(value)
        print(json.dumps({'success': True, 'config_file': str(config_path())}))
        return 0
    if args.command == 'config-status':
        validate_connection(connection_config())
        print(json.dumps({'success': True, 'config_file': str(config_path()),
                          'environment_overrides': [k for k in CONFIG_FIELDS if k in os.environ]}))
        return 0
    catalog = json.loads(CATALOG.read_text())
    operations = catalog['operations']
    if args.command == 'search':
        matches = [{'operation': name, 'method': op['method'], 'tags': op['tags']} for name, op in operations.items()
                   if args.query.lower() in (name + ' ' + op['description']).lower() and (not args.tag or args.tag in op['tags'])]
        print(json.dumps({'total': len(matches), 'matches': matches[:max(0, args.limit)]}, indent=2))
        return 0
    if args.operation not in operations:
        raise ValueError('Unknown operation; use search to find an exact name')
    op = operations[args.operation]
    if args.command == 'describe':
        result = {'operation': args.operation, **op}
        # Include referenced definitions only, never the entire catalog.
        definitions = {}
        def refs(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    ref = value['$ref']
                    if ref not in definitions:
                        node = catalog
                        for part in ref.removeprefix('#/').split('/'):
                            node = node[part.replace('~1', '/').replace('~0', '~')]
                        definitions[ref] = node
                        refs(node)
                for child in value.values():
                    refs(child)
            elif isinstance(value, list):
                for child in value:
                    refs(child)
        refs(op['input'])
        if definitions:
            result['definitions'] = definitions
        print(json.dumps(result, indent=2))
        return 0
    payload = json.load(sys.stdin) if args.input == '-' else json.loads(Path(args.input).read_text())
    if not isinstance(payload, dict):
        raise ValueError('Input must be a JSON object')
    missing = set(op['input'].get('required', [])) - payload.keys()
    if missing:
        raise ValueError('Missing required fields: ' + ', '.join(sorted(missing)))
    # Full nested schema validation remains with the Dokploy API.
    result = invoke(op, payload)
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, EOFError) as error:
        # Do not print arbitrary input or environment values in error messages.
        message = 'Invalid JSON input or configuration' if isinstance(error, json.JSONDecodeError) else ('Unable to read or write local configuration/input' if isinstance(error, OSError) else str(error))
        print(json.dumps({'success': False, 'error': message}), file=sys.stderr)
        sys.exit(1)
