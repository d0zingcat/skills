#!/usr/bin/env python3
"""Generate the compact endpoint catalog from an official MCP checkout."""
import json
import re
import sys
from pathlib import Path

source = Path(sys.argv[1])
spec = json.loads((source / 'src/generated/openapi.json').read_text())
tools = (source / 'src/generated/tools.ts').read_text()
names = set(re.findall(r'    name: "([^"]+)",', tools))
operations = {}
for path, methods in spec['paths'].items():
    for method, operation in methods.items():
        name = operation.get('operationId')
        if name not in names:
            continue
        schema = operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema')
        if schema is None:
            params = operation.get('parameters', [])
            schema = {'type': 'object', 'properties': {p['name']: p['schema'] for p in params},
                      'required': [p['name'] for p in params if p.get('required')]}
        operations[name] = {'method': method.upper(), 'path': path, 'tags': operation.get('tags', []),
                            'description': operation.get('summary') or operation.get('description', ''), 'input': schema}
assert set(operations) == names, 'Generated tools and OpenAPI operations differ'
import subprocess
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
catalog = {'source': 'https://github.com/Dokploy/mcp', 'revision': revision,
           'package_version': json.loads((source / 'package.json').read_text())['version'],
           'operations': operations, 'components': spec.get('components', {})}
target = Path(__file__).resolve().parents[1] / 'assets/endpoints.json'
target.write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + '\n')
print(f'Generated {len(operations)} endpoints at {target}')
