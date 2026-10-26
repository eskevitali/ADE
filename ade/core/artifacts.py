"""Parse model output into bounded, validated source files without executing it."""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

MAX_FILES = 200
MAX_BYTES = 2_000_000
FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
EXTENSIONS = {
    'python': '.py', 'py': '.py', 'javascript': '.js', 'js': '.js',
    'typescript': '.ts', 'ts': '.ts', 'tsx': '.tsx', 'jsx': '.jsx',
    'html': '.html', 'css': '.css', 'json': '.json', 'yaml': '.yml',
    'yml': '.yml', 'toml': '.toml', 'markdown': '.md', 'md': '.md',
    'kotlin': '.kt', 'swift': '.swift', 'java': '.java', 'bash': '.sh', 'sh': '.sh',
}


class ArtifactError(ValueError):
    """Model output does not satisfy the source artifact contract."""


def validate_relative_path(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 240:
        raise ArtifactError('Invalid artifact path')
    if '\\' in name or name.startswith('/') or any(c in name for c in '\n\r\x00'):
        raise ArtifactError(f'Unsafe artifact path: {name!r}')
    parts = name.split('/')
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts):
        raise ArtifactError(f'Unsafe artifact path: {name!r}')
    if not re.fullmatch(r'[A-Za-z0-9_/-]+(?:\.[A-Za-z0-9_.-]+)*', name):
        raise ArtifactError(f'Invalid artifact filename: {name!r}')
    return str(PurePosixPath(name))


def parse_source_files(content: str) -> list[tuple[str, str]]:
    if len(content.encode()) > MAX_BYTES:
        raise ArtifactError('Source response exceeds 2 MB')
    text = content.strip()
    if text.startswith('```json\n') and text.endswith('```'):
        text = text[8:-3].strip()
    files: list[tuple[str, str]] = []
    if text.startswith('{'):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ArtifactError('Invalid source JSON') from exc
        if not isinstance(data, dict) or not isinstance(data.get('files'), list):
            raise ArtifactError('Expected {"files": [{"path": ..., "content": ...}]}')
        for entry in data['files']:
            if not isinstance(entry, dict) or set(entry) != {'path', 'content'}:
                raise ArtifactError('Each source entry must contain path and content')
            if not isinstance(entry['content'], str):
                raise ArtifactError('File content must be text')
            files.append((validate_relative_path(entry['path']), entry['content']))
    else:
        for index, match in enumerate(FENCE.finditer(content)):
            header, body = match.groups()
            tokens = header.strip().split()
            if len(tokens) > 2:
                raise ArtifactError('Use a language and relative filename in each fence header')
            language = tokens[0].lower() if tokens else 'python'
            if len(tokens) == 2:
                name = tokens[1]
            elif tokens and ('.' in tokens[0] or '/' in tokens[0]):
                name = tokens[0]
            else:
                extension = EXTENSIONS.get(language)
                if extension is None:
                    raise ArtifactError('A relative filename is required')
                name = ('main' if index == 0 else f'module_{index + 1}') + extension
            files.append((validate_relative_path(name), body))
        if not files:
            # Legacy plain Python is accepted only if it parses as Python.
            try:
                compile(content, 'main.py', 'exec')
            except SyntaxError as exc:
                raise ArtifactError('Expected structured files or valid Python source') from exc
            files = [('main.py', content)]
    if not files or len(files) > MAX_FILES:
        raise ArtifactError('Source must contain between 1 and 200 files')
    names = [name for name, _ in files]
    if len(set(names)) != len(names):
        raise ArtifactError('Duplicate source paths')
    for name in names:
        if any(other.startswith(name + '/') for other in names):
            raise ArtifactError('A source path cannot be both a file and a directory')
    return files
