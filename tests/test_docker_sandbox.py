"""Real generated-code tests; opt in with --run-docker on a Docker host."""
import json
import pytest
from ade.core.engineering import ReleaseService


@pytest.mark.docker
def test_generated_tests_have_no_root_network_or_writable_source(workspace):
    code = '''import os, socket, unittest
class SandboxTests(unittest.TestCase):
    def test_isolation(self):
        self.assertNotEqual(os.getuid(), 0)
        self.assertEqual(os.getenv("ADMIN_PASSWORD"), None)
        with self.assertRaises(OSError):
            open("/workspace/host-owned.txt", "w")
        with self.assertRaises(OSError):
            socket.create_connection(("1.1.1.1", 443), timeout=1)
'''
    files = [{'path': 'main.py', 'content': 'print("product")'},
             {'path': 'test_sandbox.py', 'content': code}]
    workspace.write_code('product-1', json.dumps({'files': files}))
    report = ReleaseService(workspace).prepare('product-1')
    assert report['passed'], report
    assert not (workspace.project_path('product-1') / 'src/host-owned.txt').exists()


@pytest.mark.docker
def test_zero_discovered_tests_are_not_success(workspace):
    workspace.write_code('product-1', json.dumps({'files': [
        {'path': 'main.py', 'content': 'print("product")'},
        {'path': 'test_empty.py', 'content': 'import unittest'},
    ]}))
    report = ReleaseService(workspace).prepare('product-1')
    assert not report['passed']
    assert report['checks'][-1]['exit_code'] == 2
