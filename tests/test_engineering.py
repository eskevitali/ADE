from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ade.core.artifacts import ArtifactError, parse_source_files
from ade.core.config import ADEConfig
from ade.core.deployer import DeployerService
from ade.core.engineering import ReleaseService
from ade.memory.lessons import LessonStore


def bundle(files):
    return json.dumps({'files': [{'path': path, 'content': body} for path, body in files.items()]})


@pytest.mark.parametrize('path', ['../outside.py', '/tmp/x.py', 'a/../../x.py',
                                 'x\\y.py', '.env', 'pkg/.git/config', 'a//b.py',
                                 'def main():', 'x\ny.py'])
def test_unsafe_model_paths_are_rejected(path):
    with pytest.raises(ArtifactError):
        parse_source_files(bundle({path: 'print(1)'}))


def test_fenced_python_does_not_consume_first_source_line():
    assert parse_source_files('```python\ndef hello():\n    return 1\n```') == [
        ('main.py', 'def hello():\n    return 1\n')]


def test_complete_tree_replacement_and_rejection_are_safe(workspace):
    workspace.write_code('product-1', bundle({'pkg/main.py': 'x=1', 'obsolete.py': 'x=2'}))
    root = workspace.project_path('product-1') / 'src'
    assert (root / 'pkg/main.py').exists()
    with pytest.raises(ArtifactError):
        workspace.write_code('product-1', bundle({'good.py': 'ok=1', '../bad.py': 'bad=1'}))
    assert (root / 'obsolete.py').exists()
    assert not (root / 'good.py').exists()
    workspace.write_code('product-1', bundle({'main.py': 'x=3'}))
    assert not (root / 'obsolete.py').exists()
    assert not (root / 'pkg').exists()
    assert workspace.get_project_detail('product-1')['src_files'][0]['name'] == 'main.py'


def test_duplicate_source_files_are_rejected():
    with pytest.raises(ArtifactError):
        parse_source_files('{"files": [{"path":"x.py","content":"a"}, {"path":"x.py","content":"b"}]}')


def test_source_symlink_cannot_overwrite_external_files(workspace, tmp_path):
    root = workspace.project_path('product-1')
    (root / 'src').rmdir()
    external = tmp_path / 'outside'
    external.mkdir()
    (root / 'src').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError):
        workspace.write_code('product-1', 'x=1')
    assert not (external / 'main.py').exists()


@pytest.mark.parametrize('project_id', ['../escape', '/tmp/escape', 'a/b', '..'])
def test_project_paths_cannot_escape(workspace, project_id):
    with pytest.raises(ValueError):
        workspace.project_path(project_id)


def test_snapshots_are_stable_and_detect_tampering(workspace):
    workspace.write_code('product-1', bundle({'index.html': '<h1>Hello</h1>'}))
    service = ReleaseService(workspace)
    first = service.prepare('product-1')
    assert first['passed']
    assert service.prepare('product-1')['release_id'] == first['release_id']
    snapshot = service.verify('product-1', first['release_id'])
    (workspace.project_path('product-1') / 'src/index.html').write_text('<h1>Changed</h1>')
    assert (snapshot / 'src/index.html').read_text() == '<h1>Hello</h1>\n'
    second = service.prepare('product-1')
    assert first['release_id'] != second['release_id']
    (snapshot / 'src/index.html').write_text('tampered')
    with pytest.raises(ValueError, match='integrity'):
        service.verify('product-1', first['release_id'])


def test_python_without_tests_cannot_deploy(workspace):
    workspace.write_code('product-1', 'print("hello")')
    service = DeployerService(adi_manager=workspace)
    with patch.object(service, '_compose_up') as compose:
        result = service.deploy('product-1', use_agent=False)
    assert result['message'] == 'quality_gate_failed'
    compose.assert_not_called()


def test_invalid_python_does_not_execute_and_blocks_sandbox(workspace, tmp_path):
    marker = tmp_path / 'executed'
    workspace.write_code('product-1', bundle({'main.py': 'def broken(:',
        'test_main.py': f'open({str(marker)!r}, "w").write("bad")'}))
    service = ReleaseService(workspace)
    with patch.object(service, '_sandbox_tests') as sandbox:
        report = service.prepare('product-1')
    assert not report['passed']
    sandbox.assert_not_called()
    assert not marker.exists()


def test_sandbox_failure_blocks_release(workspace):
    workspace.write_code('product-1', bundle({'main.py': 'x=1', 'test_main.py': 'import unittest'}))
    service = ReleaseService(workspace)
    with patch.object(service, '_sandbox_tests', return_value={
            'name': 'sandbox_tests', 'passed': False, 'detail': 'Docker unavailable'}):
        assert not service.prepare('product-1')['passed']


def test_runtime_reads_release_and_is_hardened(workspace):
    workspace.write_code('product-1', bundle({'index.html': '<h1>Hi</h1>'}))
    release = ReleaseService(workspace)
    report = release.prepare('product-1')
    snapshot = release.verify('product-1', report['release_id'])
    service = DeployerService(adi_manager=workspace)
    path = service._ensure_compose('product-1', 'Product', snapshot=snapshot)
    import yaml
    compose = yaml.safe_load(path.read_text())
    runtime = compose['services']['workspace']
    assert runtime['read_only'] is True
    assert runtime['user'] == '65534:65534'
    assert runtime['cap_drop'] == ['ALL']
    assert 'ports' not in runtime
    assert any(report['release_id'] in mount and mount.endswith(':ro') for mount in runtime['volumes'])


def test_failed_readiness_rolls_back_previous_release(workspace):
    workspace.write_code('product-1', bundle({'index.html': '<h1>Hi</h1>'}))
    data = workspace._read_manifest('product-1')
    data['active_release_id'] = 'a' * 64
    workspace._write_manifest('product-1', data)
    service = DeployerService(adi_manager=workspace)
    with patch.object(service, '_activate', side_effect=[
            {'status': 'error', 'detail': 'not ready'}, {'status': 'ok', 'mode': 'web_static'}]) as activate:
        result = service.deploy('product-1')
    assert result['status'] == 'error'
    assert result['rollback']['status'] == 'ok'
    assert activate.call_args_list[1].args == ('product-1', 'a' * 64)
    assert workspace._read_manifest('product-1')['active_release_id'] == 'a' * 64


def test_no_unapproved_lessons_in_context(tmp_path):
    path = tmp_path / 'lessons.sqlite3'
    store = LessonStore(path)
    lesson = store.propose('Python deployment', 'Test Python before deployment', {'release_id': 'example'})
    assert store.relevant('Python deployment') == []
    assert store.approve(lesson, 'owner')
    reopened = LessonStore(path)
    assert reopened.relevant('Python deployment')[0]['id'] == lesson
    assert not reopened.approve(lesson, 'another-owner')


def test_production_requires_explicit_secrets(monkeypatch):
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    with pytest.raises(ValueError):
        ADEConfig(_env_file=None, app_env='production', admin_username='owner',
                  admin_password='long-password-at-least-16')
    with pytest.raises(ValueError):
        ADEConfig(_env_file=None, app_env='production', admin_username='owner',
                  admin_password='short', session_secret='s' * 48)


def test_recovery_uses_detailed_diagnostics():
    from ade.workflows.recovery import FailureContext, RecoveryAction, classify_failure_heuristic
    decision = classify_failure_heuristic(FailureContext('deploy', 'deploy', 'deploy_failed',
        1, 3, deploy_error='empty compose file'))
    assert decision.action == RecoveryAction.RETRY_DEPLOY


def test_recovery_survives_missing_model_keys():
    from ade.workflows.recovery import FailureContext, RecoveryAction, analyze_failure_with_tester
    from ade.core.agent_team import AgentTeam
    with patch('ade.workflows.recovery.get_llm', side_effect=ValueError('No keys')):
        decision = analyze_failure_with_tester(AgentTeam.default(),
            FailureContext('deploy', 'deploy', 'unknown failure', 1, 3))
    assert decision.action == RecoveryAction.FIX_CODE


def test_api_verification_ui_and_untrusted_content(workspace, monkeypatch):
    import ade.ui.main as ui
    from fastapi.testclient import TestClient
    monkeypatch.setattr(ui, 'adi_manager', workspace)
    monkeypatch.setattr(ui, 'deployer_service', DeployerService(adi_manager=workspace))
    workspace.write_code('product-1', bundle({'index.html': '<h1>Product</h1>'}))
    client = TestClient(ui.app)
    assert client.post('/api/projects/product-1/verify').status_code == 401
    client.post('/auth/login', data={'username': 'test-owner',
                                    'password': 'test-password-long-enough'})
    response = client.post('/api/projects/product-1/verify')
    assert response.status_code == 200
    assert response.json()['passed'] is True
    assert client.get('/api/projects/product-1/engineering').json()['quality_status'] == 'passed'
    page = client.get('/projects/product-1')
    assert page.status_code == 200
    assert 'engineering-panel' in page.text
    preview = client.get('/preview/product-1')
    csp = preview.headers['content-security-policy']
    assert 'sandbox allow-scripts' in csp
    assert 'allow-same-origin' not in csp
    assert "connect-src 'none'" in csp
    assert preview.url.path.endswith('/')
    root = workspace.project_path('product-1')
    assets = root / 'src' / 'assets'
    assets.mkdir()
    (assets / 'brand.css').write_text('body { color: red; }')
    asset = client.get('/preview/product-1/assets/brand.css')
    assert asset.status_code == 200
    assert asset.text == 'body { color: red; }'
    assert 'text/css' in asset.headers['content-type']
    assert '/preview/product-1/' in csp
    (assets / 'secret.css').symlink_to(root / 'spec' / 'SPEC.md')
    assert client.get('/preview/product-1/assets/secret.css').status_code == 404
    assert client.get('/preview/product-1/%2e%2e/spec/SPEC.md').status_code == 404
    anonymous = TestClient(ui.app).get('/preview/product-1/assets/brand.css', follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers['location'].startswith('/login?')


def test_proxy_does_not_expose_owner_session_or_accept_app_cookies(workspace, monkeypatch):
    import ade.ui.main as ui
    import httpx
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    monkeypatch.setattr(ui, 'adi_manager', workspace)
    monkeypatch.setattr(ui.deployer_service, 'workspace_upstream',
                        lambda _: {'host': 'workspace', 'port': 8000})
    upstream = AsyncMock()
    upstream.request.return_value = httpx.Response(200, text='<h1>App</h1>',
        headers={'set-cookie': 'session=forged', 'content-type': 'text/html'})
    factory = AsyncMock()
    factory.__aenter__.return_value = upstream
    with patch('httpx.AsyncClient', return_value=factory):
        client = TestClient(ui.app)
        client.post('/auth/login', data={'username': 'test-owner',
                                        'password': 'test-password-long-enough'})
        response = client.get('/run/product-1/')
    assert 'cookie' not in upstream.request.call_args.kwargs['headers']
    assert 'forged' not in response.headers.get('set-cookie', '')
    assert 'sandbox' in response.headers['content-security-policy']
