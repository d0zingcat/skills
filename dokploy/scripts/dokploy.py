#!/usr/bin/env python3
"""Search, describe, and invoke Dokploy endpoints without an MCP server."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

CATALOG = Path(__file__).resolve().parents[1] / 'assets/endpoints.json'
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
    url = os.environ.get('DOKPLOY_URL', '').rstrip('/')
    key = os.environ.get('DOKPLOY_API_KEY', '')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('DOKPLOY_URL must be an HTTP(S) instance base URL without credentials, query, or fragment')
    if parsed.path.rstrip('/').endswith('/api'):
        raise ValueError('DOKPLOY_URL must not include /api')
    if not key:
        raise ValueError('DOKPLOY_API_KEY is required')
    custom = json.loads(os.environ.get('DOKPLOY_CUSTOM_HEADERS', '{}'))
    if not isinstance(custom, dict) or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) for k, v in custom.items()):
        raise ValueError('DOKPLOY_CUSTOM_HEADERS must be an object of string headers')
    if any(k.lower() in ('x-api-key', 'content-type', 'accept') for k in custom):
        raise ValueError('Custom headers cannot override authentication or content headers')
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
        with urllib.request.build_opener(NoRedirect).open(request, timeout=float(os.environ.get('DOKPLOY_TIMEOUT', '30000')) / 1000) as response:
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
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        # Do not print arbitrary input or environment values in error messages.
        print(json.dumps({'success': False, 'error': str(error) if not isinstance(error, json.JSONDecodeError) else 'Invalid JSON input or configuration'}), file=sys.stderr)
        sys.exit(1)
