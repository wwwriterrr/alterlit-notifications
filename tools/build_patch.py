"""Собирает django/notifications_patch.py: шапка + модули пакета api/notifications/ по порядку."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'django'
MODULES = ['kinds.py', 'group.py', 'sanitize.py', 'service.py', 'settings.py', 'views.py', 'urls.py']

parts = [(ROOT / 'patch_header.txt').read_text().rstrip() + '\n']
parts.append('\n\n# ── 1. api/notifications/__init__.py — пустой файл ────────────────────────────\n')
for n, name in enumerate(MODULES, start=2):
    title = f'# ── {n}. api/notifications/{name} '
    parts.append('\n\n' + title + '─' * max(4, 80 - len(title)) + '\n')
    parts.append((ROOT / 'notifications' / name).read_text().rstrip() + '\n')
parts.append('\n\n' + (ROOT / 'patch_footer.txt').read_text().rstrip() + '\n')
(ROOT / 'notifications_patch.py').write_text(''.join(parts))
print('ok', ROOT / 'notifications_patch.py')
