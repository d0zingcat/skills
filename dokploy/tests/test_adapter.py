"""Exercise real HTTP encoding and failure behavior against a local server."""
import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('adapter', Path(__file__).resolve().parents[1] / 'scripts/dokploy.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.seen.append((self.path, self.headers.get('x-api-key'), None))
        if self.path.startswith('/api/redirect'):
            self.send_response(302)
            self.send_header('Location', '/api/leaked')
            self.end_headers()
            return
        if self.path.startswith('/api/error'):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'secret-error-body')
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'nested': {'databasePassword': 'secret'}, 'name': 'service'}).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.seen.append((self.path, self.headers.get('x-api-key'), body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"accepted":true}')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.server.seen = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = patch.dict(os.environ, {'DOKPLOY_URL': f'http://127.0.0.1:{self.server.server_port}', 'DOKPLOY_API_KEY': 'test-key', 'DOKPLOY_CUSTOM_HEADERS': '{}'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_get_query_auth_and_nested_redaction(self):
        result = adapter.invoke({'method': 'GET', 'path': '/project.one'}, {'projectId': 'a b', 'enabled': True})
        self.assertEqual(self.server.seen[0], ('/api/project.one?projectId=a+b&enabled=true', 'test-key', None))
        self.assertEqual(result['data']['nested']['databasePassword'], '[REDACTED]')
        self.assertEqual(result['data']['name'], 'service')

    def test_post_json_and_marker_rejection(self):
        adapter.invoke({'method': 'POST', 'path': '/application.create'}, {'name': 'app', 'serverId': None})
        self.assertEqual(self.server.seen[0][2], {'name': 'app', 'serverId': None})
        with self.assertRaises(ValueError):
            adapter.invoke({'method': 'POST', 'path': '/application.update'}, {'env': '[REDACTED]'})
        self.assertEqual(len(self.server.seen), 1)

    def test_redirect_and_http_error_do_not_leak_or_retry(self):
        result = adapter.invoke({'method': 'GET', 'path': '/redirect'}, {})
        self.assertFalse(result['success'])
        self.assertEqual(len(self.server.seen), 1)
        result = adapter.invoke({'method': 'GET', 'path': '/error'}, {})
        self.assertEqual(result['status'], 401)
        self.assertNotIn('secret-error-body', json.dumps(result))
        self.assertEqual(len(self.server.seen), 2)

    def test_catalog_has_every_generated_operation(self):
        catalog = json.loads(adapter.CATALOG.read_text())
        self.assertEqual(len(catalog['operations']), 604)
        self.assertEqual(catalog['operations']['application-create']['input']['required'], ['name', 'environmentId'])


if __name__ == '__main__':
    unittest.main()
