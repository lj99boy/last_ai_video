"""只读检查文本仓库和可选的媒体恢复指纹，不访问网络或执行制作脚本。"""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--media', action='store_true', help='同时检查首作v03剪辑必需媒体及已存在的归档素材。')
args = parser.parse_args()
names = subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT
).decode().split('\0')
errors, counts = [], {'text_files': 0, 'local_links': 0, 'local_media_links': 0, 'media_checked': 0}
for name in sorted(set(filter(None, names))):
    path = ROOT / name
    if not path.is_file() or path.suffix not in ('.md', '.json', '.csv', '.py'):
        continue
    counts['text_files'] += 1
    try:
        content = path.read_text(encoding='utf-8')
        # 能力层和入口不应依赖某台机器的目录结构；作品历史记录保留原文。
        capability = name in ('README.md', 'AGENTS.md') or name.endswith('/README.md') and name.count('/') == 2 \
            or name.startswith(('docs/', 'templates/', 'tests/', 'openspec/')) \
            or name.startswith('tools/') and name != 'tools/check_repository.py'
        if capability and re.search(r'/Users/[^/\s`]+/|/home/[^/\s`]+/|[A-Za-z]:\\Users\\', content):
            errors.append(f'{name}: contains a machine-specific absolute path')
        if path.suffix == '.json':
            json.loads(content)
        elif path.suffix == '.py':
            ast.parse(content, filename=name)
        elif path.suffix == '.csv':
            with path.open(newline='', encoding='utf-8') as source:
                rows = list(csv.reader(source))
            if not rows or len(set(rows[0])) != len(rows[0]):
                errors.append(f'{name}: missing or duplicate CSV header')
            elif any(len(row) != len(rows[0]) for row in rows[1:]):
                errors.append(f'{name}: inconsistent CSV row width')
        elif path.suffix == '.md':
            for link in re.findall(r'\]\(([^)]+)\)', content):
                if '://' in link or link.startswith('#'):
                    continue
                target = (path.parent / link.strip('<>').split('#')[0]).resolve()
                if 'media' in target.parts:
                    # 媒体不随Git分发，默认不能把缺少本地媒体视作文本克隆损坏。
                    counts['local_media_links'] += 1
                    continue
                counts['local_links'] += 1
                if not target.exists():
                    errors.append(f'{name}: missing local link {link}')
    except (ValueError, SyntaxError, UnicodeError) as exc:
        errors.append(f'{name}: {exc}')

if args.media:
    manifest = json.loads((ROOT / 'works/0001-in-london/delivery/media-manifest-v03.json').read_text())
    work = ROOT / manifest['work_root']
    for asset in manifest['assets']:
        path = work / asset['path']
        if not path.is_file():
            if asset['required_for_edit']:
                errors.append(f'missing required media: {asset["path"]}')
            continue
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        counts['media_checked'] += 1
        if path.stat().st_size != asset['bytes'] or digest.hexdigest() != asset['sha256']:
            errors.append(f'media fingerprint mismatch: {asset["path"]}')

print(json.dumps({'ok': not errors, **counts, 'errors': errors}, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
