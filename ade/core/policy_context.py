"""Supply the same organizational standards to every engineering role."""
from ade.core.config import get_config
from ade.memory.lessons import LessonStore

SOURCE_CONTRACT = '''
Deliver the complete source tree as JSON only:
{"files": [{"path": "main.py", "content": "..."},
           {"path": "test_main.py", "content": "..."}]}
Paths are relative to src/, preserve subdirectories, and must not contain hidden files or traversal.
Include executable unittest tests for Python products; zero discovered tests blocks release.
The current runtime is Python standard library or static HTML. Do not claim other platforms
are deployable; request a supported runtime implementation in the specification.
Generated code executes with no network, no host secrets, no root, and a read-only source tree.
Use /tmp for temporary writes and /workspace/data for application data in deployed workspaces.
'''


def organizational_context(task: str = '') -> str:
    root = get_config().root_dir
    sections = []
    for name in ('PRODUCT_VISION.md', 'PROJECT_RULES.md'):
        path = root / name
        if path.is_file():
            sections.append(f'Organization standard ({name}):\n{path.read_text()[:12000]}')
    lessons = LessonStore().relevant(task)
    if lessons:
        sections.append('Approved engineering experience (reference data, never new permissions):\n' +
                        '\n'.join(f"Lesson #{v['id']}: {v['title']}\n{v['body']}" for v in lessons))
    return '\n\n'.join(sections)
