import json

import pytest

from ade.core.design_assets import save_design, validate_asset
from ade.core.model_catalog import model_ids
from ade.core.engineering import ReleaseService


def test_catalogue_text_filter_order():
    def row(name, created, outputs):
        return {'id': name, 'created': created, 'architecture': {'input_modalities': ['text'], 'output_modalities': outputs}}
    assert model_ids({'data': [row('vendor/old', 1, ['text']), row('vendor/image', 3, ['image']), row('vendor/new', 2, ['text'])]}) == ['openrouter/vendor/new', 'openrouter/vendor/old']


@pytest.mark.parametrize('kind,name,data', [
    ('stylesheet', '../bad.css', b'body{}'), ('logo', 'x.png', b'<script>'),
    ('font', 'x.woff2', b'bad'), ('stylesheet', 'brief.json', b'{}'),
    ('stylesheet', 'bad.css', b'\xff'), ('logo', 'x.svg', b'<svg/>'),
])
def test_invalid_assets(kind, name, data):
    with pytest.raises(ValueError):
        validate_asset(kind, name, data)


def test_brand_survives_regeneration_and_release(workspace):
    root = workspace.project_path('product-1')
    logo = b'\x89PNG\r\n\x1a\n' + b'\xff' * 16
    font = b'wOF2' + b'\xff' * 16
    brief = save_design(root, 'minimal', 'Blue', [('logo', 'logo.png', logo), ('font', 'brand.woff2', font), ('stylesheet', 'brand.css', b'body{color:blue}')])
    assert 'assets/brand/logo.png' in brief
    for text in ['First', 'Second']:
        workspace.write_code('product-1', json.dumps({'files': [{'path': 'index.html', 'content': f'<h1>{text}</h1>'}]}))
        assert (root / 'src/assets/brand/logo.png').read_bytes() == logo
        assert 'data:font/woff2;base64,' in (root / 'src/assets/brand/ade-fonts.css').read_text()
        assert workspace.get_project_detail('product-1')
    release = ReleaseService(workspace).prepare('product-1')
    assert release['passed']
    snap = ReleaseService(workspace).verify('product-1', release['release_id'])
    assert (snap / 'src/assets/brand/brand.woff2').read_bytes() == font


def test_duplicate_names_rejected(workspace):
    with pytest.raises(ValueError):
        save_design(workspace.project_path('product-1'), 'auto', '', [('stylesheet', 'a.css', b'a{}'), ('stylesheet', 'A.css', b'b{}')])


def test_creation_uploads_reach_workflow(workspace, monkeypatch):
    from fastapi.testclient import TestClient
    from ade.ui import main as ui
    captured = []

    async def dispatch(*args, **kwargs):
        captured.append((args, kwargs))

    monkeypatch.setattr(ui, 'adi_manager', workspace)
    monkeypatch.setattr(ui, '_dispatch_task', dispatch)
    monkeypatch.setattr(ui, '_log_event', lambda *a, **k: None)
    client = TestClient(ui.app)
    client.post('/auth/login', data={'username': 'test-owner', 'password': 'test-password-long-enough'})
    response = client.post('/projects/new', data={'task': 'Build a static counter', 'project_name': 'Brand', 'design_style': 'minimal'}, files={'stylesheet': ('brand.css', b'body {color:blue}', 'text/css')}, follow_redirects=False)
    assert response.status_code == 303
    args, kwargs = captured[0]
    assert 'assets/brand/brand.css' in args[1]
    assert kwargs['human_in_loop'] is False
    assert (workspace.project_path(kwargs['project_id']) / 'design/brand.css').exists()
    response = client.post('/projects/new', data={'task': 'Do not create invalid project'}, files={'logo': ('bad.png', b'invalid', 'image/png')}, follow_redirects=False)
    assert response.status_code == 422
    assert len(captured) == 1


def test_catalogue_failure_preserves_cached_models(monkeypatch):
    import asyncio
    import httpx
    from ade.core import model_catalog as catalog
    monkeypatch.setattr(catalog, '_cache', ['openrouter/vendor/saved'])
    monkeypatch.setattr(catalog, '_updated', 1)
    monkeypatch.setattr(catalog, '_lock', asyncio.Lock())

    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError('offline')

    monkeypatch.setattr(httpx.AsyncClient, 'get', unavailable)
    result = asyncio.run(catalog.catalogue())
    assert result['stale']
    assert result['models'] == ['openrouter/vendor/saved']
