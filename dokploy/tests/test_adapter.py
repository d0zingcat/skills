"""Exercise real HTTP encoding and failure behavior against a local server."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import threading
import tempfile
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
        self.config_dir = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'DOKPLOY_CONFIG': str(Path(self.config_dir.name) / 'config.json'), 'DOKPLOY_URL': f'http://127.0.0.1:{self.server.server_port}', 'DOKPLOY_API_KEY': 'test-key', 'DOKPLOY_CUSTOM_HEADERS': '{}'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.config_dir.cleanup()

    def test_saved_connection_and_environment_override(self):
        value = {'DOKPLOY_URL': os.environ['DOKPLOY_URL'], 'DOKPLOY_API_KEY': 'saved-key'}
        adapter.save_config(value)
        self.assertEqual(adapter.config_path().stat().st_mode & 0o777, 0o600)
        del os.environ['DOKPLOY_URL']
        del os.environ['DOKPLOY_API_KEY']
        adapter.invoke({'method': 'GET', 'path': '/project.all'}, {})
        self.assertEqual(self.server.seen[-1][1], 'saved-key')
        os.environ['DOKPLOY_API_KEY'] = 'override-key'
        adapter.invoke({'method': 'GET', 'path': '/project.all'}, {})
        self.assertEqual(self.server.seen[-1][1], 'override-key')
        os.environ['DOKPLOY_API_KEY'] = ''
        with self.assertRaises(ValueError):
            adapter.invoke({'method': 'GET', 'path': '/project.all'}, {})
        self.assertEqual(len(self.server.seen), 2)

    def test_invalid_update_preserves_saved_connection(self):
        value = {'DOKPLOY_URL': os.environ['DOKPLOY_URL'], 'DOKPLOY_API_KEY': 'saved-key'}
        adapter.save_config(value)
        with self.assertRaises(ValueError):
            adapter.save_config({**value, 'DOKPLOY_CUSTOM_HEADERS': {'x-api-key': 'forbidden'}})
        self.assertEqual(adapter.load_config(), value)
        adapter.save_config({**value, 'DOKPLOY_API_KEY': 'replacement'})
        self.assertEqual(adapter.config_path().stat().st_mode & 0o777, 0o600)

    def test_cli_setup_status_and_missing_config(self):
        env = {k: v for k, v in os.environ.items() if k not in adapter.CONFIG_FIELDS}
        command = [sys.executable, str(Path(adapter.__file__))]
        result = subprocess.run(command + ['config-status'], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('configure', result.stderr)
        value = {'DOKPLOY_URL': os.environ['DOKPLOY_URL'], 'DOKPLOY_API_KEY': 'private-test-key',
                 'DOKPLOY_CUSTOM_HEADERS': {'proxy-secret': 'private-header'}}
        result = subprocess.run(command + ['configure', '--input', '-'], input=json.dumps(value),
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command + ['config-status'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('private-test-key', result.stdout + result.stderr)
        self.assertNotIn('private-header', result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['environment_overrides'], [])
        result = subprocess.run(command + ['configure'], input='', env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires a terminal', result.stderr)

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
