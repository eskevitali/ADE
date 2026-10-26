"""All engineering tests use isolated project and memory directories."""
import pytest
from ade.core.config import get_config


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv('ROOT_DIR', str(tmp_path))
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('ADMIN_USERNAME', 'test-owner')
    monkeypatch.setenv('ADMIN_PASSWORD', 'test-password-long-enough')
    monkeypatch.setenv('SESSION_SECRET', 'test-secret-with-at-least-32-characters')
    get_config.cache_clear()
    from ade.core.adi_manager import ADIManager
    manager = ADIManager()
    manager.bootstrap('product-1', 'Product', 'Test product', enable_isolation=False)
    manager.write_spec('product-1', '# Spec\nA tested product')
    yield manager
    get_config.cache_clear()
