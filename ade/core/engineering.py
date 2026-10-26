"""Evidence-based releases. Generated code runs only inside a bounded Docker sandbox."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import selectors
import time
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ade import __version__
from ade.core.artifacts import validate_relative_path
from ade.core.config import get_config
from ade.tools.docker_paths import resolve_docker_bind_source


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def project_lock(root: Path):
    import fcntl
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.engineering.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


TEST_RUNNER = '''import sys, unittest
suite = unittest.defaultTestLoader.discover(".", pattern="test_*.py")
count = suite.countTestCases()
if not count:
    print("No tests discovered")
    sys.exit(2)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
'''


class ReleaseService:
    """Snapshot inputs, verify sources, and retain reports bound to their exact hashes."""

    def __init__(self, adi_manager) -> None:
        self.adi = adi_manager

    def _inputs(self, root: Path) -> dict[str, bytes]:
        inputs: dict[str, bytes] = {}
        for folder in ('src', 'spec', 'review'):
            directory = root / folder
            if directory.is_symlink():
                raise ValueError(f'Symlink is forbidden: {folder}')
            for file in sorted(directory.rglob('*')) if directory.exists() else []:
                if file.is_symlink():
                    raise ValueError('Symlink is forbidden in release inputs')
                if file.name in ("VERIFICATION.json", "DEPLOY.md") and folder == "review":
                    continue
                if file.is_file():
                    name = file.relative_to(root).as_posix()
                    validate_relative_path(name)
                    if file.stat().st_size > (30_000_000 if name.startswith('src/assets/brand/') else 2_000_000):
                        raise ValueError('Release input is too large')
                    inputs[name] = file.read_bytes()
        if sum(map(len, inputs.values())) > 50_000_000 or len(inputs) > 500:
            raise ValueError('Release input limit exceeded')
        return inputs

    def _sandbox_tests(self, snapshot: Path) -> dict[str, Any]:
        config = get_config()
        container = 'ade-test-' + uuid.uuid4().hex
        source = resolve_docker_bind_source(snapshot / 'src')
        command = [
            'docker', 'run', '--rm', '--name', container, '--pull=never',
            '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges:true', '--pids-limit=64',
            '--memory=256m', '--cpus=1', '--user=65534:65534',
            '--tmpfs=/tmp:rw,noexec,nosuid,size=32m',
            '--mount', f'type=bind,source={source},target=/workspace,readonly',
            '--workdir=/workspace', '--env=PYTHONDONTWRITEBYTECODE=1',
            config.workspace_image, 'python', '-B', '-c', TEST_RUNNER,
        ]
        try:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
                output = bytearray()
                total = 0
                deadline = time.monotonic() + config.sandbox_timeout
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    try:
                        while selector.get_map():
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(command, config.sandbox_timeout)
                            for key, _ in selector.select(timeout=0.1):
                                chunk = os.read(key.fd, 8192)
                                if not chunk:
                                    selector.unregister(key.fd)
                                    continue
                                total += len(chunk)
                                output.extend(chunk)
                                del output[:-8000]
                                if total > 1_000_000:
                                    raise ValueError('Sandbox output exceeded 1 MB')
                        exit_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
            return {'name': 'sandbox_tests', 'passed': exit_code == 0,
                    'exit_code': exit_code, 'detail': output.decode('utf-8', errors='replace')}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {'name': 'sandbox_tests', 'passed': False,
                    'detail': f'Sandbox unavailable or timed out: {type(exc).__name__}'}
        finally:
            try:
                subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def prepare(self, project_id: str) -> dict[str, Any]:
        root = self.adi.project_path(project_id)
        if not self.adi.get_project(project_id):
            raise ValueError('Project not found')
        with project_lock(root):
            return self._prepare_locked(project_id, root)

    def _prepare_locked(self, project_id: str, root: Path) -> dict[str, Any]:
        inputs = self._inputs(root)
        hashes = {name: hashlib.sha256(body).hexdigest() for name, body in inputs.items()}
        config = get_config()
        identity = {'schema_version': 1, 'files': hashes, 'ade_version': __version__,
                    'workspace_image': config.workspace_image, 'test_policy': 'unittest-sandbox-v1'}
        release_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        releases = root / 'releases'
        if releases.is_symlink():
            raise ValueError('Release directory symlink is forbidden')
        releases.mkdir(exist_ok=True)
        target = releases / release_id
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix='.release-', dir=releases) as temporary:
                staged = Path(temporary) / 'snapshot'
                staged.mkdir()
                for name, body in inputs.items():
                    file = staged / name
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_bytes(body)
                atomic_json(staged / 'release.json', {**identity, 'id': release_id})
                staged.rename(target)
        self.verify(project_id, release_id)
        checks: list[dict[str, Any]] = []
        source = [name for name in inputs if name.startswith('src/')]
        checks.append({'name': 'source_files', 'passed': bool(source), 'detail': str(len(source))})
        checks.append({'name': 'specification', 'passed': bool(inputs.get('spec/SPEC.md', b'').strip())})
        python_files = [name for name in source if name.endswith('.py')]
        for name in python_files:
            try:
                ast.parse(inputs[name], filename=name)
                checks.append({'name': 'syntax:' + name, 'passed': True})
            except (SyntaxError, ValueError) as exc:
                checks.append({'name': 'syntax:' + name, 'passed': False,
                               'detail': f'{type(exc).__name__} at line {getattr(exc, "lineno", "?")}'})
        if python_files:
            has_tests = any(Path(n).name.startswith('test_') for n in python_files)
            checks.append({'name': 'tests_present', 'passed': has_tests})
            if has_tests and all(c['passed'] for c in checks):
                checks.append(self._sandbox_tests(target))
        elif any(name in source for name in ('src/index.html', 'src/app.html')):
            checks.append({'name': 'static_entrypoint', 'passed': True,
                           'detail': 'Static publication only; functional browser tests are not implemented'})
        else:
            checks.append({'name': 'supported_runtime', 'passed': False,
                           'detail': 'Supported releases: Python with unittest tests, or static HTML'})
        # A mockup or a simulator is never evidence that the requested product exists.
        mode = 'python' if python_files else 'static'
        report = {'schema_version': 1, 'release_id': release_id, 'project_id': project_id,
                  'created_at': datetime.now(UTC).isoformat(), 'runtime': mode,
                  'passed': all(c['passed'] for c in checks), 'checks': checks}
        atomic_json(target / 'verification.json', report)
        atomic_json(root / 'review' / 'VERIFICATION.json', report)
        manifest = self.adi._read_manifest(project_id)
        manifest['candidate_release_id'] = release_id
        manifest['quality_status'] = 'passed' if report['passed'] else 'failed'
        self.adi._write_manifest(project_id, manifest)
        return report

    def verify(self, project_id: str, release_id: str) -> Path:
        if len(release_id) != 64 or any(c not in '0123456789abcdef' for c in release_id):
            raise ValueError('Invalid release ID')
        target = self.adi.project_path(project_id) / 'releases' / release_id
        if target.parent.is_symlink() or target.is_symlink():
            raise ValueError('Release symlink is forbidden')
        manifest = json.loads((target / 'release.json').read_text())
        identity = {k: v for k, v in manifest.items() if k != 'id'}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if digest != release_id or manifest['id'] != release_id:
            raise ValueError('Release identity mismatch')
        actual = self._inputs(target)
        if {n: hashlib.sha256(b).hexdigest() for n, b in actual.items()} != manifest['files']:
            raise ValueError('Release integrity check failed')
        return target

    def list_releases(self, project_id: str) -> list[dict]:
        directory = self.adi.project_path(project_id) / 'releases'
        result = []
        for path in sorted(directory.glob('*/verification.json')):
            report = json.loads(path.read_text())
            result.append(report)
        return sorted(result, key=lambda item: item['created_at'], reverse=True)
