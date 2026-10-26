"""Offline regression tests never operate on a server's ADI projects or API keys."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix='ade-suite-'))
os.environ['ROOT_DIR'] = str(TEST_ROOT)
os.environ['APP_ENV'] = 'development'
os.environ['ADMIN_USERNAME'] = 'test-owner'
os.environ['ADMIN_PASSWORD'] = 'test-password-long-enough'
os.environ['SESSION_SECRET'] = 'test-secret-with-at-least-32-characters'
os.environ['OPENROUTER_API_KEY'] = ''
os.environ['XAI_API_KEY'] = ''
# Prevent optional service checks from accidentally reaching a real installation.
os.environ['POSTGRES_URL'] = 'postgresql://test:test@127.0.0.1:1/test?connect_timeout=1'
os.environ['QDRANT_URL'] = 'http://127.0.0.1:1'


@pytest.fixture(autouse=True)
def legacy_fixtures(request):
    if request.module.__name__ not in ('test_revision_flow', 'test_delete_project', 'test_reflection'):
        yield
        return
    from ade.core.adi_manager import ADIManager
    manager = ADIManager()
    fixtures = ['658fbae8-5606-42f6-858a-5b2cdd0d33be',
                '203941da-7cd3-430d-b26a-f8bf9fe3b178', 'test-bootstrap-001']
    for project_id in fixtures:
        shutil.rmtree(manager.project_path(project_id), ignore_errors=True)
        manager.bootstrap(project_id, 'Fixture ' + project_id, 'test idea', enable_isolation=False)
        manager.write_spec(project_id, '# Spec\nDetails')
        manager.write_tz(project_id, '# TZ\nDetails')
        if project_id.startswith('2039'):
            data = manager._read_manifest(project_id)
            data['revision_count'] = 1
            manager._write_manifest(project_id, data)
        else:
            data = manager._read_manifest(project_id)
            data['revision_count'] = 1
            manager._write_manifest(project_id, data)
            manager.save_revision_record(project_id, feedback='test', old_tz='', new_tz='# TZ',
                old_spec='', new_spec='# Spec', tz_sections=[], spec_sections=[], summary={})
            data = manager._read_manifest(project_id)
            data['pending_revision_id'] = None
            data['status'] = 'completed'
            manager._write_manifest(project_id, data)
    yield


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


def pytest_addoption(parser):
    parser.addoption('--run-docker', action='store_true', help='Run disposable Docker integration tests')


def pytest_configure(config):
    config.addinivalue_line('markers', 'docker: requires a local Docker daemon and pre-pulled workspace image')


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-docker'):
        for item in items:
            if item.get_closest_marker('docker'):
                item.add_marker(pytest.mark.skip(reason='Use --run-docker for Docker integration'))


@pytest.fixture(autouse=True)
def docker_policy(request, monkeypatch):
    from ade.tools.docker_tool import DockerTool
    if not request.node.get_closest_marker('docker'):
        monkeypatch.setattr(DockerTool, 'is_available', lambda self: False)
        return


@pytest.fixture(autouse=True)
def docker_proxy_network(request):
    if not request.node.get_closest_marker('docker'):
        yield
        return
    import subprocess
    import uuid
    from ade.core.config import get_config
    config = get_config()
    previous = config.workspace_proxy_network
    name = 'ade-test-' + uuid.uuid4().hex[:12]
    subprocess.run(['docker', 'network', 'create', name], check=True, capture_output=True)
    config.workspace_proxy_network = name
    try:
        yield
    finally:
        config.workspace_proxy_network = previous
        subprocess.run(['docker', 'network', 'rm', name], check=False, capture_output=True)
