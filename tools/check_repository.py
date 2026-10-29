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


def anchors(path, cache={}):
    """显式锚点与按GitHub规则生成的标题锚点。"""
    if path not in cache:
        text = path.read_text(encoding='utf-8')
        slugs = {re.sub(r'[^\w\- ]', '', title.strip().lower()).replace(' ', '-')
                 for title in re.findall(r'^#{1,6} (.+)$', text, re.M)}
        cache[path] = slugs | set(re.findall(r'<a id="([^"]+)"', text))
    return cache[path]

for name in sorted(set(filter(None, names))):
    path = ROOT / name
    if not path.is_file() or path.suffix not in ('.md', '.json', '.csv', '.py'):
        continue
    counts['text_files'] += 1
    try:
        content = path.read_text(encoding='utf-8')
        # 能力层和入口不应依赖某台机器的目录结构；作品历史记录保留原文。
        capability = name in ('README.md', 'AGENTS.md') or name.endswith('/README.md') and name.count('/') == 2 \
            or name.startswith(('docs/', 'templates/', 'tests/', 'openspec/', '.agents/')) \
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
                elif '#' in link and target.suffix == '.md' and link.split('#', 1)[1] not in anchors(target):
                    errors.append(f'{name}: missing anchor {link}')
    except (ValueError, SyntaxError, UnicodeError) as exc:
        errors.append(f'{name}: {exc}')

# 检查点Skill只负责触发，时机名称必须与制作经验入口的表格一致，避免两边各自演变。
skill = ROOT / '.agents/skills/production-checkpoint/SKILL.md'
if skill.is_file():
    text = skill.read_text(encoding='utf-8')
    front = re.match(r'---\nname: (\S+)\ndescription: (.+?)\n---\n', text, re.S)
    if not front or front.group(1) != skill.parent.name or len(front.group(2)) > 1024:
        errors.append(f'{skill.relative_to(ROOT)}: frontmatter needs matching name and description within 1024 characters')
    lessons = (ROOT / 'docs/production-lessons.md').read_text(encoding='utf-8')
    stages = set(re.findall(r'^\| ([^|]+?) \| [^|]+ \| [^|]+ \|$', lessons.split('## 六个触发时机', 1)[1].split('\n## ', 1)[0], re.M))
    used = set(re.findall(r'^\| [^|]+ \| ([^|]+?) \|$', text.split('## 1. 判断时机', 1)[1].split('\n## ', 1)[0], re.M))
    stages -= {'何时使用', '---'}
    used -= {'时机（制作经验入口表格中的行）', '---'}
    if stages != used:
        errors.append(f'{skill.relative_to(ROOT)}: stages differ from docs/production-lessons.md: {sorted(stages ^ used)}')

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
