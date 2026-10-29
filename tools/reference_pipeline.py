"""参考职责编译与官方即梦 CLI 有界执行；默认离线，不打印第三方原始响应。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid


READY = {'ready', 'reviewed', 'local_reviewed_limited', 'reviewed_local_candidate',
         'available_reviewed', 'selected_source'}
IDENTITY_ROLES = {'identity', 'costume', 'character', 'appearance', 'identity_primary',
                  'costume_reference', 'identity_source'}
ALIAS = re.compile(r'\[\[([A-Za-z][A-Za-z0-9_]*)\]\]')
NODE = re.compile(r'node_[0123456789abcdefghjkmnpqrstvwxyz]{10}\Z')
UUID = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
SAFE_CODE = re.compile(r'[A-Za-z0-9_.:-]{1,160}\Z')
EXECUTION_BLOCKERS = {'plan_retired', 'segment_retired', 'execution_explicitly_denied',
                      'work_cloud_mutations_denied'}
# 不随--work-root、工作克隆或工具副本切换；测试仅通过mock隔离到临时目录。
AUTHORITY_STORE = Path.home() / '.local/state/last-ai-video/reference-pipeline-authority'
ASSET_IDENTITY_FIELDS = ('node_id', 'resource_id', 'update_id', 'submit_id', 'semantic_hash',
                         'authorization_hash', 'origin', 'upload_file_sha256', 'upload_file_bytes')
ASSET_STATUS_SUCCESSORS = {
    'pending': {'pending', 'uploaded_import_pending', 'unknown', 'verified'},
    'uploaded_import_pending': {'uploaded_import_pending', 'unknown', 'verified'},
    'element_edit_pending': {'element_edit_pending', 'unknown', 'verified'},
    'unknown': {'unknown', 'verified'},
    'verified': {'verified'},
}


class PipelineError(Exception):
    """只携带本地安全错误码，不透传 CLI/provider 异常文本。"""
    def __init__(self, code, details=None):
        self.code = code
        self.details = details or {}
        super().__init__(code)


class UnknownOutcome(PipelineError):
    pass


def require(condition, code, details=None):
    if not condition:
        raise PipelineError(code, details)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _png_metadata(path):
    """限定8位RGB/RGBA PNG；caBX来源签名独记，其余非像素块精确比较。"""
    data = Path(path).read_bytes()
    require(len(data) >= 33 and data[:8] == b'\x89PNG\r\n\x1a\n' and
            data[8:16] == b'\x00\x00\x00\rIHDR' and data[24] == 8 and data[25] in (2, 6),
            'uploaded_source_content_mismatch')
    metadata, provenance, offset, ended = hashlib.sha256(), [], 8, False
    while offset < len(data):
        require(offset + 12 <= len(data), 'uploaded_source_content_mismatch')
        size = int.from_bytes(data[offset:offset + 4], 'big')
        end, kind = offset + 12 + size, data[offset + 4:offset + 8]
        require(end <= len(data), 'uploaded_source_content_mismatch')
        if kind == b'caBX':
            provenance.append({'bytes': size, 'sha256': hashlib.sha256(data[offset + 8:offset + 8 + size]).hexdigest()})
        elif kind not in (b'IHDR', b'IDAT', b'IEND'):
            metadata.update(data[offset:offset + 8 + size])
        offset = end
        if kind == b'IEND':
            ended = size == 0 and offset == len(data)
            break
    require(ended, 'uploaded_source_content_mismatch')
    return {'non_provenance_sha256': metadata.hexdigest(), 'caBX': provenance}


def verify_downloaded_source(original, downloaded, source, receipt):
    """先验回执与实际文件；编码变化仅放行严格PNG逐RGBA字节相同。"""
    original, downloaded = Path(original), Path(downloaded)
    require(original.is_file() and original.stat().st_size == source['bytes'] and
            file_sha(original) == source['sha256'], 'uploaded_source_input_changed')
    require(downloaded.is_file(), 'uploaded_source_content_mismatch')
    actual_bytes, actual_sha = downloaded.stat().st_size, file_sha(downloaded)
    require(type(receipt.get('size')) is int and receipt['size'] == actual_bytes and
            receipt.get('sha256') == actual_sha, 'uploaded_source_download_receipt_mismatch')
    evidence = {'original_sha256': source['sha256'], 'original_bytes': source['bytes'],
                'download_sha256': actual_sha, 'download_bytes': actual_bytes}
    if actual_bytes == source['bytes'] and actual_sha == source['sha256']:
        return dict(evidence, method='exact_file_identity')
    require(source['type'] == 'image', 'uploaded_source_content_mismatch')
    original_metadata, remote_metadata = _png_metadata(original), _png_metadata(downloaded)
    require(original_metadata['non_provenance_sha256'] == remote_metadata['non_provenance_sha256'] and
            (original_metadata['caBX'] == remote_metadata['caBX'] or
             (original_metadata['caBX'] and not remote_metadata['caBX'])), 'uploaded_source_content_mismatch')
    try:
        from PIL import Image
    except ImportError:
        raise PipelineError('exact_png_verification_requires_pillow') from None
    try:
        with Image.open(original) as approved, Image.open(downloaded) as remote:
            require(all(image.format == 'PNG' and image.mode in {'RGB', 'RGBA'} and
                        getattr(image, 'n_frames', 1) == 1 and not getattr(image, 'is_animated', False)
                        for image in (approved, remote)) and approved.size == remote.size,
                    'uploaded_source_content_mismatch')
            approved.load(); remote.load()
            require(approved.info == remote.info, 'uploaded_source_content_mismatch')
            pixels, remote_pixels = approved.convert('RGBA').tobytes(), remote.convert('RGBA').tobytes()
            require(pixels == remote_pixels, 'uploaded_source_content_mismatch')
            return dict(evidence, method='exact_pixel_identity', dimensions=list(approved.size),
                        rgba_sha256=hashlib.sha256(pixels).hexdigest(),
                        original_metadata=original_metadata, download_metadata=remote_metadata,
                        metadata_exact=original_metadata == remote_metadata,
                        server_removed_chunks=['caBX'] if original_metadata['caBX'] != remote_metadata['caBX'] else [])
    except (OSError, ValueError, TypeError):
        raise PipelineError('uploaded_source_content_mismatch') from None


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        raise PipelineError('invalid_json_file') from None


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
    tmp.replace(path)


def work_path(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            'path_must_be_work_relative')
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), 'path_outside_work')
    return path


def execution_blockers(plan, root, segment=None):
    """退休/停线属于执行门禁，不从paid_ready推断，更不禁止历史只读。"""
    blockers = []
    retired = re.compile(r'(^|[_\W])(retired|superseded|denied|rejected)([_\W]|$)', re.I)
    for label, item in [('plan', plan), ('segment', segment or {})]:
        if retired.search(str(item.get('status', ''))):
            blockers.append({'code': label + '_retired'})
        if item.get('execution_allowed') is False:
            blockers.append({'code': 'execution_explicitly_denied'})
    policy_path = Path(root).resolve() / 'production/execution-policy.json'
    if policy_path.exists():
        policy = read_json(policy_path)
        require(isinstance(policy, dict) and policy.get('schema_version') == 1 and
                type(policy.get('cloud_mutations_allowed')) is bool and
                policy.get('work_id') == plan.get('work_id'), 'invalid_work_execution_policy')
        if policy['cloud_mutations_allowed'] is False:
            blockers.append({'code': 'work_cloud_mutations_denied'})
    return blockers


def locator(asset, project_id):
    remote = asset.get('remote')
    if not remote:
        return None
    require(isinstance(remote, dict) and remote.get('kind') in {'node', 'resource'},
            'invalid_remote_locator')
    require(remote.get('project_id') == project_id, 'remote_project_mismatch')
    kind, value = remote['kind'], remote.get('id', '')
    require(bool(NODE.fullmatch(value) if kind == 'node' else UUID.fullmatch(value)),
            'invalid_remote_identity')
    result = {'kind': kind, 'id': value, 'project_id': project_id}
    if asset.get('kind', 'media') != 'element':
        selected = remote.get('selected_resource_id')
        if kind == 'resource':
            require(selected in (None, value), 'frozen_resource_mismatch')
            selected = value
        if selected is not None:
            require(bool(UUID.fullmatch(selected)), 'invalid_selected_resource')
        result['selected_resource_id'] = selected
    return result


def _characters(value):
    require(isinstance(value, list), 'characters_must_be_list')
    result = {}
    for character in value:
        require(isinstance(character, dict) and isinstance(character.get('id'), str),
                'invalid_character')
        require(character['id'] not in result, 'duplicate_character')
        result[character['id']] = character
    return result


def _pinned_model_contract(plan, work_root):
    """新事务显式固定能力证据；旧plan不隐式联网或扩大离线profile。"""
    if 'model_contract' not in plan:
        return None, None
    pin = plan['model_contract']
    require(isinstance(pin, dict) and set(pin) == {'path', 'sha256'} and
            isinstance(pin.get('sha256'), str) and SHA.fullmatch(pin['sha256']),
            'invalid_model_contract_pin')
    path = work_path(work_root, pin.get('path'))
    require(path.is_file(), 'model_contract_missing')
    # 同一份字节完成指纹和解析，避免读两次时证据在中间变化。
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == pin['sha256'], 'model_contract_fingerprint_mismatch')
    try:
        contract = json.loads(data)
    except (ValueError, UnicodeError):
        raise PipelineError('invalid_model_contract_file') from None
    require(isinstance(contract, dict), 'invalid_model_contract_file')
    if 'ok' in contract:
        require(contract.get('ok') is True and isinstance(contract.get('data'), dict),
                'model_contract_envelope_failed')
        contract = contract['data']
    require(isinstance(contract.get('items'), list) and contract['items'] and
            all(isinstance(item, dict) for item in contract['items']), 'invalid_model_contract_file')
    return contract, deepcopy(pin)


def _model_check(request, references, contract=None, explicit_flags=False):
    mode = request['mode']
    types = [r['type'] for r in references]
    require(mode in {'m2v', 'first_last_frame', 't2v'}, 'unsupported_mode')
    if mode == 'first_last_frame':
        require(len(types) in (1, 2) and all(t == 'image' for t in types),
                'first_last_requires_ordered_images')
        for index, reference in enumerate(references):
            roles = set(reference['roles'])
            require('first_frame' not in roles or index == 0, 'first_frame_order_conflict')
            require('last_frame' not in roles or (len(types) == 2 and index == 1),
                    'last_frame_order_conflict')
    elif mode == 't2v':
        require(not types and bool(request['prompt'].strip()), 't2v_reference_conflict')
    else:
        require(1 <= len(types) <= 50, 'm2v_reference_count')
        for media, limit in [('image', 30), ('video', 10), ('audio', 10)]:
            require(types.count(media) <= limit, 'm2v_media_count')
    require(type(request['outputCount']) is int and 1 <= request['outputCount'] <= 4,
            'invalid_output_count')
    require(type(request['durationSeconds']) is int and 4 <= request['durationSeconds'] <= 30,
            'invalid_duration')
    require(request['ratio'] in {'21:9', '16:9', '4:3', '1:1', '3:4', '9:16'}, 'invalid_ratio')
    require(request['resolution'] in {'480p', '720p', '1080p'}, 'invalid_resolution')
    require(len(request['prompt']) <= 15000, 'prompt_too_long')
    if contract is None:
        require(request['model'] == 'seedance_2.5', 'unverified_model')
        require(request['ratio'] == '16:9' and request['resolution'] == '720p',
                'offline_profile_only_16x9_720p')
        return
    # 仅使用当前官方 model find 的公开 flags，不自造 capability 开关。
    if explicit_flags:
        require(isinstance(contract, dict) and isinstance(contract.get('items'), list) and
                all(isinstance(item, dict) for item in contract['items']), 'invalid_model_contract_file')
    items = contract.get('items', [contract])
    models = [m for m in items if m.get('model') == request['model']]
    require(len(models) == 1, 'live_model_not_found')
    candidates = [m for m in models[0].get('modes', []) if m.get('name') == mode]
    valid = False
    for candidate in candidates:
        if explicit_flags:
            flag_list = candidate.get('flags')
            require(isinstance(flag_list, list) and all(isinstance(f, dict) and
                    isinstance(f.get('flag'), str) for f in flag_list) and
                    len({f['flag'] for f in flag_list}) == len(flag_list), 'invalid_model_contract_flags')
        flags = {f['flag']: f for f in candidate.get('flags', [])}
        if explicit_flags:
            # 缺枚举/范围不是"全部允许"；固定证据与实时复核采用相同的保守解释。
            needed = {'--ratio', '--resolution', '--duration', '--count'}
            require(needed.issubset(flags) and
                    all(isinstance(flags[f].get('values'), list) and flags[f]['values']
                        for f in ('--ratio', '--resolution')) and
                    all(type(flags[f].get(k)) is int for f in ('--duration', '--count') for k in ('min', 'max')) and
                    all(flags[f]['min'] <= flags[f]['max'] for f in ('--duration', '--count')),
                    'model_contract_explicit_flags_required')
        pairs = [('--ratio', 'ratio'), ('--resolution', 'resolution'),
                 ('--duration', 'durationSeconds'), ('--count', 'outputCount')]
        ok = True
        for flag, key in pairs:
            rule, value = flags.get(flag, {}), request[key]
            ok = ok and ('values' not in rule or value in rule['values'])
            ok = ok and ('min' not in rule or value >= rule['min'])
            ok = ok and ('max' not in rule or value <= rule['max'])
        count = candidate.get('references', {})
        ok = ok and count.get('min', 0) <= len(types) <= count.get('max', 50)
        for entry in count.get('types', []):
            total = types.count(entry['mediaType'])
            ok = ok and entry.get('min', 0) <= total <= entry.get('max', 50)
        # Element 的解析数由服务端决定；这里不把 Element 假称为一张 image。
        if 'element' in types and mode == 'm2v':
            ok = ok and all(t in {'image', 'video', 'audio', 'element'} for t in types)
        valid = valid or ok
    require(valid, 'live_model_contract_conflict')


def compile_segment(registry, plan, segment_id, work_root, model_contract=None):
    """纯本地编译；缺资源可返回 blocked，结构/职责/年代矛盾显式报错。"""
    pinned_contract, model_contract_pin = _pinned_model_contract(plan, work_root)
    if model_contract_pin is not None:
        require(model_contract is None, 'model_contract_override_conflict')
        model_contract = pinned_contract
    assets = registry.get('assets')
    require(isinstance(assets, dict), 'assets_must_be_dictionary')
    require(isinstance(plan.get('segments'), dict) and segment_id in plan['segments'],
            'segment_not_found')
    segment = plan['segments'][segment_id]
    project = plan.get('project_id')
    require(isinstance(project, str) and UUID.fullmatch(project), 'invalid_project')
    delivery = segment.get('delivery', 'generate')
    require(delivery in {'generate', 'reuse', 'local_edit'}, 'invalid_delivery')
    def check_dependencies(sid, chain):
        require(sid not in chain, 'segment_dependency_cycle')
        dependencies = plan['segments'][sid].get('dependencies', [])
        require(isinstance(dependencies, list), 'dependencies_must_be_list')
        for dependency in dependencies:
            require(isinstance(dependency, dict), 'dependency_must_be_object')
            prior, checks = dependency.get('segment_id'), dependency.get('checks')
            require(isinstance(prior, str) and prior in plan['segments'], 'dependency_segment_not_found')
            require(isinstance(checks, list) and all(isinstance(c, str) and c.strip() for c in checks) and
                    len(checks) == len(set(checks)), 'dependency_checks_must_be_string_list')
            check_dependencies(prior, chain | {sid})
    check_dependencies(segment_id, set())
    blockers = execution_blockers(plan, work_root, segment)
    fingerprints, sources, elements, order = {}, {}, {}, []
    semantic_assets, visiting = {}, set()

    def block(code, asset_id=None):
        item = {'code': code}
        if asset_id is not None:
            item['asset_id'] = asset_id
        if item not in blockers:
            blockers.append(item)

    def visit(asset_id):
        require(asset_id in assets, 'asset_not_registered', {'asset_id': asset_id})
        require(asset_id not in visiting, 'element_dependency_cycle')
        if asset_id in fingerprints:
            return
        visiting.add(asset_id)
        asset = assets[asset_id]
        kind = asset.get('kind', 'media')
        require(kind in {'media', 'element'}, 'invalid_asset_kind')
        require(isinstance(asset.get('allowed_roles', []), list) and
                isinstance(asset.get('forbidden_roles', []), list), 'invalid_role_declaration')
        if asset.get('status') not in READY:
            block('asset_not_ready', asset_id)
        if not asset.get('review'):
            block('asset_review_missing', asset_id)
        remote = locator(asset, project)
        require(not (kind == 'element' and remote and remote['kind'] != 'node'),
                'element_remote_node_required')
        semantic = {k: deepcopy(asset.get(k)) for k in ['kind', 'media_type', 'sha256', 'bytes',
                    'status', 'allowed_roles', 'forbidden_roles', 'characters', 'review',
                    'provenance', 'main', 'auxiliaries', 'voice'] if k in asset}
        if kind == 'media':
            require(asset.get('media_type') in {'image', 'video', 'audio'}, 'invalid_media_type')
            if asset.get('path'):
                path = work_path(work_root, asset['path'])
                if not path.is_file():
                    block('media_file_missing', asset_id)
                elif (not SHA.fullmatch(str(asset.get('sha256', ''))) or
                      type(asset.get('bytes')) is not int or path.stat().st_size != asset['bytes'] or
                      file_sha(path) != asset['sha256']):
                    block('media_fingerprint_mismatch', asset_id)
            elif remote is None:
                block('media_source_missing', asset_id)
            if remote and not remote.get('selected_resource_id'):
                block('selected_resource_unpinned', asset_id)
            sources[asset_id] = {'asset_id': asset_id, 'type': asset['media_type'], 'remote': remote,
                                 'path': asset.get('path'), 'sha256': asset.get('sha256'),
                                 'bytes': asset.get('bytes')}
        else:
            require(isinstance(asset.get('main'), str), 'element_main_required')
            require(isinstance(asset.get('auxiliaries', []), list), 'element_auxiliaries_list')
            children = [asset['main'], *asset.get('auxiliaries', [])]
            if asset.get('voice'):
                children.append(asset['voice'])
            for child in children:
                visit(child)
            require(assets[asset['main']].get('kind', 'media') == 'media', 'element_main_media_required')
            if assets[asset['main']].get('media_type') != 'image':
                # 公开main契约未枚举类型；本片仅已核实image，不推断video/audio可执行。
                block('element_main_type_runtime_unverified', asset_id)
            for child in asset.get('auxiliaries', []):
                require(assets[child].get('kind', 'media') == 'media' and
                        assets[child].get('media_type') == 'image', 'element_auxiliary_image_required')
            if asset.get('voice'):
                require(assets[asset['voice']].get('kind', 'media') == 'media' and
                        assets[asset['voice']].get('media_type') == 'audio', 'element_voice_audio_required')
            semantic['dependency_hashes'] = [fingerprints[c]['semantic_hash'] for c in children]
            elements[asset_id] = {'asset_id': asset_id, 'remote': remote, 'main': asset['main'],
                                  'auxiliaries': asset.get('auxiliaries', []), 'voice': asset.get('voice')}
        if remote is None and delivery == 'generate':
            block('remote_binding_missing', asset_id)
        semantic_assets[asset_id] = semantic
        fingerprints[asset_id] = {'semantic_hash': digest(semantic), 'remote': remote}
        fingerprints[asset_id]['binding_hash'] = digest({
            'semantic_hash': fingerprints[asset_id]['semantic_hash'], 'remote': remote,
            'children': [fingerprints[c]['binding_hash'] for c in
                         ([asset['main'], *asset.get('auxiliaries', []), *([asset['voice']] if asset.get('voice') else [])]
                          if kind == 'element' else [])]})
        visiting.remove(asset_id)
        order.append(asset_id)

    expected_characters = _characters(segment.get('characters', []))
    references, aliases, physical = [], {}, {}
    for use in segment.get('references', []):
        asset_id, alias = use.get('asset_id'), use.get('alias')
        require(isinstance(alias, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', alias), 'invalid_alias')
        require(alias not in aliases, 'duplicate_alias')
        visit(asset_id)
        asset, roles = assets[asset_id], use.get('roles', [])
        require(isinstance(roles, list) and roles and len(roles) == len(set(roles)), 'invalid_reference_roles')
        require(set(roles) <= set(asset.get('allowed_roles', [])), 'role_not_allowed', {'asset_id': asset_id})
        require(not set(roles) & set(asset.get('forbidden_roles', [])), 'role_forbidden', {'asset_id': asset_id})
        excluded = set(use.get('exclusions', []))
        require(not (('composition' in roles and excluded & {'composition', 'framing'}) or
                     (set(roles) & {'first_frame', 'last_frame', 'action_endpoint'} and
                      excluded & {'pose', 'action_state'})),
                'reference_role_exclusion_conflict')
        if set(roles) & IDENTITY_ROLES:
            ids = [asset_id]
            if asset.get('kind') == 'element':
                ids += [asset['main'], *asset.get('auxiliaries', [])]
            declarations = []
            for identity in ids:
                declarations.extend(_characters(assets[identity].get('characters', [])).values())
            require(bool(declarations), 'identity_character_missing')
            for char in declarations:
                expected = expected_characters.get(char['id'])
                require(expected is not None, 'unexpected_identity_character')
                require(char.get('era') == expected.get('era', segment.get('era')),
                        'identity_era_conflict', {'asset_id': asset_id})
                require('age' in char and 'age' in expected and char['age'] == expected['age'],
                        'identity_age_conflict', {'asset_id': asset_id})
        remote = fingerprints[asset_id]['remote']
        key = (remote['kind'], remote['id']) if remote else ('local', asset_id)
        if key in physical:
            index = physical[key]
            # 同一远端身份不能以两份互相矛盾的本地内容声明混用。
            require(fingerprints[references[index]['asset_id']]['semantic_hash'] ==
                    fingerprints[asset_id]['semantic_hash'], 'duplicate_physical_source_conflict')
            references[index]['roles'] = sorted(set(references[index]['roles']) | set(roles))
        else:
            index = len(references)
            physical[key] = index
            references.append({'asset_id': asset_id, 'type': 'element' if asset.get('kind') == 'element'
                               else asset['media_type'], 'remote': remote, 'roles': list(roles),
                               'exclusions': list(use.get('exclusions', []))})
        aliases[alias] = index

    text = segment.get('prompt', '')
    require(isinstance(text, str), 'prompt_must_be_text')
    require('{{' not in text, 'raw_cli_placeholder_forbidden')
    used, parts, chunks, start = set(), [], [], 0
    for match in ALIAS.finditer(text):
        alias = match.group(1)
        require(alias in aliases, 'undefined_prompt_alias')
        if match.start() > start:
            part = text[start:match.start()]
            parts.append({'kind': 'text', 'text': part}); chunks.append(part)
        index, remote = aliases[alias], references[aliases[alias]]['remote']
        parts.append({'kind': 'reference', 'referenceIndex': index})
        chunks.append('{{' + ('node' if remote['kind'] == 'node' else 'res') + ':' + remote['id'] + '}}'
                      if remote else match.group())
        used.add(alias); start = match.end()
    if start < len(text):
        parts.append({'kind': 'text', 'text': text[start:]}); chunks.append(text[start:])
    require('[[' not in ALIAS.sub('', text), 'malformed_prompt_alias')
    require(set(aliases) == used, 'unused_reference_alias')
    first_appearance = list(dict.fromkeys(part['referenceIndex'] for part in parts if part['kind'] == 'reference'))
    # 官方CLI按正文首次出现解析槽序，--ref声明本身不能固定不同的槽序。
    # 显式拒绝冲突，不暗中重排首尾帧或多模态引用的有序含义。
    require(first_appearance == list(range(len(references))), 'reference_first_appearance_order_conflict')
    prompt = ''.join(chunks)
    baseline = {}
    files = plan.get('baseline_files', {})
    if isinstance(files, list):
        files = {v if isinstance(v, str) else v['path']: None if isinstance(v, str)
                 else v.get('sha256') for v in files}
    require(isinstance(files, dict), 'baseline_files_invalid')
    for relative, expected in sorted(files.items()):
        path = work_path(work_root, relative)
        if not path.is_file():
            block('baseline_missing'); continue
        actual = file_sha(path); baseline[relative] = actual
        if expected is not None and actual != expected:
            block('baseline_fingerprint_mismatch')
    request = {'model': segment.get('model', 'seedance_2.5'), 'mode': segment.get('mode', 'm2v'),
               'ratio': segment.get('ratio', '16:9'), 'resolution': segment.get('resolution', '720p'),
               'durationSeconds': segment.get('duration_seconds'), 'outputCount': segment.get('count', 1),
               'prompt': prompt, 'promptParts': parts}
    if delivery == 'generate':
        _model_check(request, references, model_contract, explicit_flags=model_contract_pin is not None)
    semantic_segment = {k: deepcopy(v) for k, v in segment.items() if k not in {'remote', 'status'}}
    semantic_input = {'segment': semantic_segment, 'assets': semantic_assets, 'baseline': baseline}
    if model_contract_pin is not None:
        semantic_input['model_contract'] = model_contract_pin
    semantic_hash = digest(semantic_input)
    result = {'schema_version': 1, 'segment_id': segment_id, 'project_id': project, 'delivery': delivery,
              'beat_ids': segment.get('beat_ids', []), 'timeline': segment.get('timeline'),
              'request': request, 'references': references, 'aliases': aliases, 'sources': sources,
              'elements': elements, 'dependency_order': order, 'dependency_fingerprints': fingerprints,
              'baseline_fingerprints': baseline, 'semantic_hash': semantic_hash,
              'target': segment.get('remote'), 'blocking': blockers,
              'model_validation': 'provided_contract' if model_contract is not None else 'offline_16x9_720p_profile_only',
              'element_media_counting': 'server_runtime_unverified' if elements else 'not_applicable'}
    if model_contract_pin is not None:
        result.update(model_validation='pinned_official_contract', model_contract_fingerprint=model_contract_pin)
    result['request_hash'] = digest({k: result[k] for k in ['project_id', 'request', 'references',
                                                          'dependency_fingerprints', 'target']})
    result['executable'] = delivery == 'generate' and not blockers
    result['local_ready'] = not any(b['code'] not in {'remote_binding_missing', 'selected_resource_unpinned'}
                                   for b in blockers)
    result['required_external_operations'] = [
        {'operation': 'uploads', 'asset_id': aid, 'sha256': assets[aid].get('sha256')}
        if assets[aid].get('kind', 'media') == 'media' else
        {'operation': 'elements', 'asset_id': aid, 'semantic_hash': fingerprints[aid]['semantic_hash']}
        for aid in order if not fingerprints[aid]['remote']]
    return result


def _binding_identity(binding):
    return {'kind': binding.get('kind'), 'id': binding.get('id'), 'type': binding.get('type')}


def _check_binding(expected, actual, media_type, problems, label, nodes):
    if not isinstance(actual, dict) or expected is None:
        problems.append(label + ':binding_missing'); return
    kind = 'node' if expected['kind'] == 'node' else 'resource'
    if actual.get('kind') != kind or actual.get('id') != expected['id'] or actual.get('type') != media_type:
        problems.append(label + ':identity_mismatch')
    if actual.get('writebackSupported') is not True or actual.get('unavailableCode'):
        problems.append(label + ':unavailable')
    if media_type != 'element':
        resource = actual.get('resource')
        if 'resource' not in actual:
            # 当前CLI的Node绑定不内嵌resource；只有来源恰好一个成功产物时才无歧义。
            # 显式resource无论是否冲突均不能走此替代，多产物也不能靠“包含旧ID”放行。
            source = nodes.get(expected['id'], {}) if expected['kind'] == 'node' and actual.get('kind') == 'node' else {}
            resources = source.get('resources', [])
            if (source.get('nodeId') != expected['id'] or source.get('status') != 'success'
                    or source.get('type') != media_type or not isinstance(resources, list)
                    or len(resources) != 1 or not isinstance(resources[0], dict)
                    or resources[0].get('resourceId') != expected.get('selected_resource_id')
                    or resources[0].get('status') != 'success' or resources[0].get('type') != media_type):
                problems.append(label + ':selected_resource_unverified'); return
            resource = resources[0]
        if not isinstance(resource, dict):
            problems.append(label + ':selected_resource_unverified'); return
        if resource.get('resourceId') != expected.get('selected_resource_id'):
            problems.append(label + ':selected_resource_changed')
        if resource.get('status') != 'success' or resource.get('type') != media_type:
            problems.append(label + ':resource_not_ready')


def normalize_nodes(readback):
    """保留比较所需的内存对象，绝不将第三方原始对象直接落盘。"""
    nodes = readback.get('nodes', {})
    if isinstance(nodes, list):
        nodes = {entry['node']['nodeId']: entry['node'] for entry in nodes
                 if entry.get('result') == 'FOUND' and isinstance(entry.get('node'), dict)}
    require(isinstance(nodes, dict), 'invalid_node_readback')
    return nodes


def compare_readback(compiled, readback, target_id=None):
    problems = []
    nodes = normalize_nodes(readback)
    target_id = target_id or (compiled.get('target') or {}).get('node_id')
    node = nodes.get(target_id, {})
    if node.get('type') != 'video':
        problems.append('target:video_missing')
    generation = node.get('generation', {})
    expected = compiled['request']
    for field in ['model', 'mode', 'ratio', 'resolution', 'durationSeconds', 'outputCount', 'prompt', 'promptParts']:
        if generation.get(field) != expected.get(field):
            problems.append('target:' + field + '_mismatch')
    if generation.get('writebackSupported') is not True or generation.get('writebackBlockers'):
        problems.append('target:writeback_unavailable')
    actual_refs = generation.get('references', [])
    if len(actual_refs) != len(compiled['references']):
        problems.append('target:reference_count_mismatch')
    for index, ref in enumerate(compiled['references']):
        _check_binding(ref['remote'], actual_refs[index] if index < len(actual_refs) else None,
                       ref['type'], problems, 'reference:' + str(index), nodes)
    expected_edges = {r['remote']['id'] for r in compiled['references']
                      if r['remote'] and r['remote']['kind'] == 'node'}
    if not expected_edges <= set(node.get('upstreamNodeIds', [])):
        problems.append('target:upstream_missing')
    for aid, source in compiled['sources'].items():
        remote = source['remote']
        if remote is None:
            problems.append('source:' + aid + ':remote_missing'); continue
        if remote['kind'] == 'node':
            actual = nodes.get(remote['id'], {})
            if actual.get('type') != source['type'] or actual.get('status') != 'success':
                problems.append('source:' + aid + ':node_not_ready')
            # 此处验证来源产物存在；选中证据仍由_check_binding的严格分支单独验证。
            if not any(r.get('resourceId') == remote.get('selected_resource_id') and
                       r.get('status') == 'success' and r.get('type') == source['type']
                       for r in actual.get('resources', [])):
                problems.append('source:' + aid + ':resource_missing')
    for aid, element in compiled['elements'].items():
        remote = element['remote']
        if not remote or remote['kind'] != 'node':
            problems.append('element:' + aid + ':node_required'); continue
        actual = nodes.get(remote['id'], {})
        if actual.get('type') != 'element':
            problems.append('element:' + aid + ':missing')
        bindings = actual.get('subjectBindings', {})
        main = compiled['sources'][element['main']]
        _check_binding(main['remote'], bindings.get('main'), main['type'], problems, 'element:' + aid + ':main', nodes)
        expected_aux, actual_aux = element['auxiliaries'], bindings.get('auxiliaries', [])
        if len(expected_aux) != len(actual_aux):
            problems.append('element:' + aid + ':auxiliary_count_mismatch')
        for index, child in enumerate(expected_aux):
            _check_binding(compiled['sources'][child]['remote'], actual_aux[index] if index < len(actual_aux) else None,
                           'image', problems, 'element:' + aid + ':aux:' + str(index), nodes)
        if element.get('voice'):
            _check_binding(compiled['sources'][element['voice']]['remote'], bindings.get('voice'),
                           'audio', problems, 'element:' + aid + ':voice', nodes)
        elif bindings.get('voice'):
            problems.append('element:' + aid + ':unexpected_voice')
        children = [element['main'], *expected_aux, *([element['voice']] if element.get('voice') else [])]
        edges = {compiled['sources'][c]['remote']['id'] for c in children
                 if compiled['sources'][c]['remote'] and compiled['sources'][c]['remote']['kind'] == 'node'}
        if not edges <= set(actual.get('upstreamNodeIds', [])):
            problems.append('element:' + aid + ':upstream_missing')
    if type(readback.get('draftVersion')) is not int:
        problems.append('draft_version_missing')
    return {'ok': not problems, 'problems': problems, 'draft_version': readback.get('draftVersion'),
            'request_hash': compiled['request_hash']}


class OfficialCLI:
    """只构造 argv-list；异常永不包含 stdout、stderr、argv 或 token。"""
    ALLOWED = {('schema',), ('model', 'find'), ('auth', 'account'), ('node', 'show'),
               ('node', 'create'), ('node', 'edit'), ('node', 'quote'), ('node', 'confirm'),
               ('node', 'run'), ('resource', 'upload'), ('resource', 'get'), ('resource', 'download'),
               ('operation', 'status'), ('operation', 'wait')}

    def __init__(self, executable, runner=None):
        self.executable = str(executable)
        self.runner = runner or subprocess.run
        self.request_ids = []

    def call(self, args):
        prefix = tuple(args[:1]) if args[:1] == ['schema'] else tuple(args[:2])
        require(prefix in self.ALLOWED and '--yes' not in args and '--run' not in args,
                'cli_command_forbidden')
        argv = [self.executable, *args, '--format', 'json', '--non-interactive', '--profile', 'default', '--region', 'cn']
        try:
            proc = self.runner(argv, capture_output=True, text=True, timeout=60)
            # 某些CLI错误将合法envelope写入stderr；顺序检查，不输出任何raw文本。
            envelope = None
            for stream in (proc.stdout, proc.stderr):
                if not isinstance(stream, str):
                    continue
                for match in re.finditer(r'\{', stream):
                    try:
                        candidate, _ = json.JSONDecoder().raw_decode(stream[match.start():])
                    except ValueError:
                        continue
                    if isinstance(candidate, dict) and type(candidate.get('ok')) is bool and (
                            isinstance(candidate.get('data'), dict) or isinstance(candidate.get('error'), dict)):
                        envelope = candidate
                        break
                if envelope is not None:
                    break
            require(envelope is not None, 'cli_response_unreadable')
        except (subprocess.TimeoutExpired, OSError, ValueError, TypeError):
            raise UnknownOutcome('cli_outcome_unknown') from None
        # 仅保留顶层关联ID；失败envelope也可供排查，绝不保留meta其余字段或原始响应。
        meta = envelope.get('meta')
        request_id = meta.get('requestId') if isinstance(meta, dict) else None
        if isinstance(request_id, str) and SAFE_CODE.fullmatch(request_id) and request_id not in self.request_ids:
            self.request_ids.append(request_id)
        if proc.returncode or envelope.get('ok') is not True:
            error = envelope.get('error') or {}
            code = error.get('code')
            public_codes = {'cli.operation_submission_absent', 'cli.credit_confirmation_required',
                            'cli.validation_failed', 'cli.non_interactive_confirmation_required'}
            code = code if code in public_codes else 'cli_rejected'
            raise PipelineError('cli_rejected', {'service_code': code, 'exit_code': proc.returncode})
        require(isinstance(envelope.get('data'), dict), 'cli_response_unreadable')
        return envelope['data']


def _binding_coverage(compiled, approval, grant, journal, allow_pending=False):
    """现有绑定须明确冻结；新导入只能由实际批准与本轮事务共同派生。"""
    fixed = grant.get('source_bindings', {}) if isinstance(grant, dict) else {}
    if not isinstance(fixed, dict):
        fixed = {}
    records = (journal or {}).get('assets', {})
    covered, derived = set(), set()
    fingerprints = compiled['dependency_fingerprints']
    for aid in compiled['dependency_order']:
        fp = fingerprints[aid]
        if fixed.get(aid) == fp['binding_hash'] and fp['remote']:
            covered.add(aid)
            continue
        if allow_pending and fp['remote'] is None:
            if aid in compiled['sources']:
                sha = compiled['sources'][aid].get('sha256')
                permitted = isinstance(sha, str) and SHA.fullmatch(sha) and (
                    approval.get('operations', {}).get('uploads', {}).get(aid) == sha)
            else:
                element = compiled['elements'][aid]
                children = [element['main'], *element['auxiliaries'],
                            *([element['voice']] if element.get('voice') else [])]
                permitted = (approval.get('operations', {}).get('elements', {}).get(aid) == fp['semantic_hash'] and
                             all(child in covered for child in children))
            if permitted:
                covered.add(aid)
                continue
        rec = records.get(aid, {})
        common = (rec.get('status') == 'verified' and rec.get('authorization_hash') == digest(approval) and
                  rec.get('semantic_hash') == fp['semantic_hash'] and rec.get('remote') == fp['remote'] and
                  fp['remote'] is not None and rec.get('node_id') == fp['remote']['id'])
        if aid in compiled['sources']:
            source, sha = compiled['sources'][aid], compiled['sources'][aid].get('sha256')
            uploaded = (common and rec.get('origin') == 'reference_pipeline_upload' and
                        isinstance(sha, str) and SHA.fullmatch(sha) and
                        approval.get('operations', {}).get('uploads', {}).get(aid) == sha and
                        rec.get('upload_file_sha256') == sha and rec.get('upload_file_bytes') == source.get('bytes') and
                        rec.get('verified_import_resource_id') == rec.get('resource_id') and
                        fp['remote'].get('selected_resource_id') == rec.get('resource_id'))
            if uploaded:
                covered.add(aid); derived.add(aid)
        else:
            element = compiled['elements'][aid]
            children = [element['main'], *element['auxiliaries'],
                        *([element['voice']] if element.get('voice') else [])]
            element_ok = (common and rec.get('origin') in {'reference_pipeline_element_create',
                                                           'reference_pipeline_element_edit'} and
                          approval.get('operations', {}).get('elements', {}).get(aid) == fp['semantic_hash'] and
                          rec.get('verified_element_binding_hash') == fp['binding_hash'] and
                          all(child in covered for child in children))
            if element_ok:
                covered.add(aid); derived.add(aid)
    return covered, derived


def authorization_delta(compiled, approval, work_root, operations, journal=None):
    """operations=[{operation,asset_id|segment_id,...}]；不推断批准、不改旧记录。"""
    problems = []
    if not isinstance(approval, dict) or approval.get('schema_version') != 1:
        return [{'code': 'normalized_approval_missing'}]
    evidence = approval.get('evidence') or {}
    try:
        path = work_path(work_root, evidence.get('path'))
        evidence_ok = path.is_file() and file_sha(path) == evidence.get('sha256')
    except PipelineError:
        evidence_ok = False
    if not evidence_ok or approval.get('human_approved') is not True:
        problems.append({'code': 'approval_evidence_unverified'})
    if approval.get('project_id') != compiled['project_id']:
        problems.append({'code': 'approval_project_mismatch'})
    grants = approval.get('operations', {})
    for op in operations:
        kind = op['operation']
        key = op.get('asset_id', op.get('segment_id'))
        granted = grants.get(kind, {}).get(key)
        wanted = op.get('sha256') if kind == 'uploads' else op.get('semantic_hash')
        actual = granted.get('semantic_hash') if isinstance(granted, dict) else granted
        if actual != wanted:
            problems.append({'code': 'uncovered_' + kind, 'id': key})
        elif kind in {'runs', 'drafts'}:
            # 核价草稿也须对应批准来源；不能先写错资源再等run才拦。
            covered, _ = _binding_coverage(compiled, approval, granted, journal, allow_pending=kind == 'drafts')
            for aid in compiled['dependency_order']:
                if aid not in covered:
                    problems.append({'code': 'uncovered_source_binding', 'id': aid})
    return problems


class Executor:
    def __init__(self, registry, plan, work_root, state_path, cli, approval=None):
        self.registry, self.plan = deepcopy(registry), deepcopy(plan)
        self.root, self.state_path = Path(work_root).resolve(), Path(state_path).resolve()
        self.cli, self.approval = cli, approval
        self.state = None
        self._authority = None
        self._authority_path = None

    @contextmanager
    def _approval_lock(self, mutation):
        """先锁批准再锁journal：并发换路径也只能绑定一个权威账本。"""
        if not mutation:
            yield
            return
        blocked = execution_blockers(self.plan, self.root)
        require(not blocked, 'execution_retired_or_denied', {'blocking': blocked})
        problems = authorization_delta({'project_id': self.plan['project_id']}, self.approval,
                                       self.root, [], None)
        require(not problems, 'authorization_delta', {'delta': problems})
        # 按人类批准证据定位；只改标准化合同/复制证据路径不能获得新额度。
        key = digest({'project_id': self.plan['project_id'],
                      'evidence_sha256': self.approval['evidence']['sha256']})
        directory = AUTHORITY_STORE
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (key + '.json')
        with path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._authority_path = path
            self._authority = read_json(path) if path.exists() else {}
            try:
                yield
            finally:
                self._authority = None
                self._authority_path = None

    def _bind_authority(self):
        state_path = str(self.state_path.resolve())
        if self._authority:
            authority = self._authority
            require(authority.get('approval_hash') == digest(self.approval),
                    'approval_authority_contract_changed')
            require(authority.get('work_root') == str(self.root), 'approval_bound_to_other_work_root')
            require(authority.get('state_path') == state_path, 'approval_bound_to_other_journal')
            require(self.state.get('authority_nonce') == authority.get('journal_nonce') and
                    bool(UUID.fullmatch(str(authority.get('journal_nonce', '')))),
                    'approval_journal_reset_or_missing')
            require(self.state['run_calls'] >= authority.get('run_calls', 0) and
                    self.state['reserved_credits'] >= authority.get('reserved_credits', 0),
                    'approval_usage_rollback')
            for sid, previous in authority.get('segments', {}).items():
                current = self.state.get('segments', {}).get(sid, {})
                require(current.get('run_calls', 0) >= previous.get('run_calls', 0) and
                        current.get('reserved_credits', 0) >= previous.get('reserved_credits', 0) and
                        (not previous.get('target') or current.get('target') == previous['target']),
                        'approval_usage_rollback')
            for aid, previous in authority.get('assets', {}).items():
                current = self.state.get('assets', {}).get(aid)
                require(isinstance(current, dict) and all(current.get(key) == value for key, value
                        in previous.get('identity', {}).items()), 'approval_asset_rollback')
                # recover可按原身份从unknown推进到verified；旧快照不能遗失已尝试上传。
                require(current.get('status') in ASSET_STATUS_SUCCESSORS.get(previous.get('status'),
                                                                           {previous.get('status')}),
                        'approval_asset_rollback')
        else:
            require(not self.state.get('authority_nonce'), 'approval_authority_missing')
            self.state['authority_nonce'] = str(uuid.uuid4())
            self._authority.update(schema_version=1, approval_hash=digest(self.approval),
                                   work_root=str(self.root), state_path=state_path,
                                   journal_nonce=self.state['authority_nonce'])
        self.persist()

    @contextmanager
    def transaction(self, mutation=False):
        with self._approval_lock(mutation):
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with self.state_path.with_suffix('.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                self.state = read_json(self.state_path) if self.state_path.exists() else {
                    'schema_version': 1, 'project_id': self.plan['project_id'], 'assets': {}, 'segments': {},
                    'reserved_credits': 0, 'run_calls': 0, 'approval_hash': None}
                require(self.state.get('project_id') == self.plan['project_id'], 'journal_project_mismatch')
                require(type(self.state.get('reserved_credits')) is int and self.state['reserved_credits'] >= 0 and
                        type(self.state.get('run_calls')) is int and self.state['run_calls'] >= 0,
                        'journal_counters_invalid')
                records = list(self.state.get('segments', {}).values())
                require(all(type(r.get('run_calls', 0)) is int and 0 <= r.get('run_calls', 0) <= 1 and
                            type(r.get('reserved_credits', 0)) is int and r.get('reserved_credits', 0) >= 0
                            for r in records), 'journal_segment_counters_invalid')
                require(sum(r.get('run_calls', 0) for r in records) == self.state['run_calls'] and
                        sum(r.get('reserved_credits', 0) for r in records) == self.state['reserved_credits'],
                        'journal_totals_mismatch')
                if mutation:
                    self._bind_authority()
                try:
                    yield
                finally:
                    # 只读可恢复原操作，但不重建批准pin或把空账本恢复成新额度。
                    self.persist()

    def persist(self):
        previous = self.state.get('cli_request_ids', [])
        current = getattr(self.cli, 'request_ids', [])
        previous = previous if isinstance(previous, list) else []
        current = current if isinstance(current, list) else []
        self.state['cli_request_ids'] = list(dict.fromkeys(value for value in [*previous, *current]
            if isinstance(value, str) and SAFE_CODE.fullmatch(value)))
        if self._authority is not None:
            self._authority.update(run_calls=self.state['run_calls'],
                                   reserved_credits=self.state['reserved_credits'],
                                   assets={aid: {'identity': {key: deepcopy(rec[key]) for key in
                                           ASSET_IDENTITY_FIELDS if key in rec}, 'status': rec.get('status')}
                                           for aid, rec in self.state.get('assets', {}).items()},
                                   segments={sid: {k: deepcopy(rec[k]) for k in
                                             ('target', 'run_calls', 'reserved_credits') if k in rec}
                                             for sid, rec in self.state.get('segments', {}).items()})
            # 先落不可回退用量，再落工作账本；崩溃最多保守阻断，不能重获次数。
            save_json(self._authority_path, self._authority)
        save_json(self.state_path, self.state)

    def _compile(self, sid):
        registry = deepcopy(self.registry)
        original = compile_segment(registry, self.plan, sid, self.root)
        for aid, rec in self.state['assets'].items():
            if aid in registry['assets'] and rec.get('status') == 'verified':
                require(aid not in original['dependency_fingerprints'] or rec.get('semantic_hash') ==
                        original['dependency_fingerprints'][aid]['semantic_hash'], 'imported_asset_input_changed')
                registry['assets'][aid]['remote'] = rec['remote']
        plan = deepcopy(self.plan)
        if self.state['segments'].get(sid, {}).get('target'):
            plan['segments'][sid]['remote'] = self.state['segments'][sid]['target']
        return compile_segment(registry, plan, sid, self.root)

    def _grant(self, compiled, operations):
        problems = authorization_delta(compiled, self.approval, self.root, operations, self.state)
        require(not problems, 'authorization_delta', {'delta': problems})
        fingerprint = digest(self.approval)
        pinned = self.state.get('approval_hash')
        require(pinned in (None, fingerprint), 'approval_changed_use_explicit_migration')
        self.state['approval_hash'] = fingerprint

    def _show(self, ids):
        args = ['node', 'show', '--project-id', self.plan['project_id']]
        for node_id in sorted(set(ids)):
            args += ['--node-id', node_id]
        return self.cli.call(args) if ids else {'draftVersion': None, 'nodes': {}}

    def _inspect(self, compiled):
        ids = [v['remote']['id'] for v in [*compiled['sources'].values(), *compiled['elements'].values()]
               if v.get('remote') and v['remote']['kind'] == 'node']
        if compiled.get('target'):
            ids.append(compiled['target']['node_id'])
        return self._show(ids)

    def inspect(self, sid):
        with self.transaction():
            compiled = self._compile(sid)
            readback = self._inspect(compiled)
            return compare_readback(compiled, readback)

    def _video_args(self, compiled, action, target):
        require(compiled['executable'], 'compiled_request_blocked', {'blocking': compiled['blocking']})
        req = compiled['request']
        args = ['node', action, 'video', '--project-id', compiled['project_id'],
                '--node-id', target['node_id'], '--update-id', target['update_id'],
                '--title', compiled['segment_id'], '--model', req['model'], '--mode', req['mode'],
                '--ratio', req['ratio'], '--resolution', req['resolution'],
                '--duration', str(req['durationSeconds']), '--count', str(req['outputCount']),
                '--prompt', req['prompt']]
        for ref in compiled['references']:
            remote = ref['remote']
            args += ['--ref', ('node:' if remote['kind'] == 'node' else 'res:') + remote['id']]
        return args

    def _target(self, sid):
        rec = self.state['segments'].setdefault(sid, {'run_calls': 0, 'reserved_credits': 0})
        if not rec.get('target'):
            target = deepcopy(self.plan['segments'][sid].get('remote')) or {
                'node_id': 'node_' + uuid.uuid4().hex[:10], 'update_id': str(uuid.uuid4()),
                'submit_id': str(uuid.uuid4())}
            require(NODE.fullmatch(target.get('node_id', '')) and UUID.fullmatch(target.get('update_id', '')) and
                    UUID.fullmatch(target.get('submit_id', '')), 'invalid_target_identity')
            rec['target'] = target
            self.persist()
        return rec

    def _prepare_asset(self, aid, compiled):
        asset = self.registry['assets'][aid]
        is_element = asset.get('kind') == 'element'
        op = {'operation': 'elements' if is_element else 'uploads', 'asset_id': aid,
              'semantic_hash': compiled['dependency_fingerprints'][aid]['semantic_hash'],
              'sha256': asset.get('sha256')}
        self._grant(compiled, [op])
        old = self.state['assets'].get(aid)
        if old:
            require(old.get('status') == 'verified', 'asset_outcome_unknown_recover_only')
            return
        rec = {'node_id': 'node_' + uuid.uuid4().hex[:10], 'update_id': str(uuid.uuid4()),
               'submit_id': str(uuid.uuid4()), 'resource_id': str(uuid.uuid4()), 'status': 'pending',
               'semantic_hash': op['semantic_hash'], 'authorization_hash': digest(self.approval),
               'origin': 'reference_pipeline_element_create' if is_element else 'reference_pipeline_upload'}
        if not is_element:
            rec.update(upload_file_sha256=asset['sha256'], upload_file_bytes=asset['bytes'])
        self.state['assets'][aid] = rec
        self.persist()  # 任何外部写之前稳定身份必须落盘。
        try:
            if is_element:
                require(not compiled['blocking'] or all(b['code'] == 'remote_binding_missing'
                        for b in compiled['blocking']), 'asset_input_blocked')
                current = self._compile(compiled['segment_id'])
                args = ['node', 'create', 'element', '--project-id', compiled['project_id'],
                        '--node-id', rec['node_id'], '--update-id', rec['update_id'], '--title', aid]
                for flag, child in [('--main', asset['main']), *[('--auxiliary', c) for c in asset.get('auxiliaries', [])],
                                    *([('--voice', asset['voice'])] if asset.get('voice') else [])]:
                    source = current['sources'][child]['remote']
                    require(source is not None, 'element_source_not_prepared')
                    args += [flag, source['id']]
                self.cli.call(args)
                rec['remote'] = {'kind': 'node', 'id': rec['node_id'], 'project_id': compiled['project_id']}
            else:
                path = work_path(self.root, asset['path'])
                require(path.is_file() and file_sha(path) == asset['sha256'] and path.stat().st_size == asset['bytes'],
                        'upload_file_changed')
                uploaded = self.cli.call(['resource', 'upload', '--project-id', compiled['project_id'],
                                          '--resource-id', rec['resource_id'], '--file', str(path), '--name', aid,
                                          '--type', asset['media_type'], '--import-kind', 'external_generated'])
                require(uploaded.get('resourceId') == rec['resource_id'], 'upload_resource_identity_mismatch')
                rec['status'] = 'uploaded_import_pending'; self.persist()
                self.cli.call(['node', 'create', asset['media_type'], '--project-id', compiled['project_id'],
                               '--node-id', rec['node_id'], '--update-id', rec['update_id'],
                               '--submit-id', rec['submit_id'], '--resource-id', rec['resource_id'],
                               '--import-kind', 'external_generated', '--title', aid])
                rec['remote'] = {'kind': 'node', 'id': rec['node_id'], 'project_id': compiled['project_id'],
                                 'selected_resource_id': rec['resource_id']}
            rb = self._show([rec['node_id']]); node = normalize_nodes(rb).get(rec['node_id'], {})
            if is_element:
                require(node.get('type') == 'element', 'element_create_readback_mismatch')
                # 完整绑定在视频保存前统一比较；不得仅凭 create 成功宣布可运行。
            else:
                require(node.get('type') == asset['media_type'] and node.get('status') == 'success' and
                        any(v.get('resourceId') == rec['resource_id'] and v.get('status') == 'success'
                            for v in node.get('resources', [])), 'import_readback_mismatch')
                rec['verified_import_resource_id'] = rec['resource_id']
            rec['status'] = 'verified'
            if is_element:
                actual_compiled = self._compile(compiled['segment_id'])
                check = compare_readback(actual_compiled, self._inspect(actual_compiled))
                require(not any(p.startswith('element:' + aid + ':') for p in check['problems']),
                        'element_create_binding_mismatch')
                rec['verified_element_binding_hash'] = actual_compiled['dependency_fingerprints'][aid]['binding_hash']
            self.persist()
        except (PipelineError, KeyError, TypeError):
            rec['status'] = 'unknown'; self.persist()
            raise UnknownOutcome('asset_outcome_unknown_recover_only') from None

    def _edit_element(self, aid, compiled):
        """完整替换显式批准的主/辅/音色；遗漏值不能意外保留旧绑定。"""
        element = compiled['elements'][aid]
        remote = element['remote']
        require(remote is not None and remote['kind'] == 'node', 'element_edit_node_required')
        self._grant(compiled, [{'operation': 'elements', 'asset_id': aid,
                               'semantic_hash': compiled['dependency_fingerprints'][aid]['semantic_hash']}])
        previous = self.state['assets'].get(aid)
        require(not previous or previous.get('status') == 'verified', 'element_outcome_unknown_recover_only')
        rec = {'node_id': remote['id'], 'update_id': str(uuid.uuid4()), 'submit_id': str(uuid.uuid4()),
               'status': 'element_edit_pending', 'remote': remote,
               'semantic_hash': compiled['dependency_fingerprints'][aid]['semantic_hash'],
               'origin': 'reference_pipeline_element_edit', 'authorization_hash': digest(self.approval)}
        self.state['assets'][aid] = rec; self.persist()
        args = ['node', 'edit', 'element', '--project-id', compiled['project_id'],
                '--node-id', remote['id'], '--update-id', rec['update_id']]
        for flag, child in [('--main', element['main']),
                            *[('--auxiliary', c) for c in element['auxiliaries']],
                            *([('--voice', element['voice'])] if element.get('voice') else [])]:
            source = compiled['sources'][child]['remote']
            require(source is not None, 'element_source_not_prepared')
            args += [flag, source['id']]
        if not element['auxiliaries']:
            args.append('--clear-auxiliary')
        if not element.get('voice'):
            args.append('--clear-voice')
        try:
            self.cli.call(args)
            check = compare_readback(compiled, self._inspect(compiled))
            require(not any(p.startswith('element:' + aid + ':') for p in check['problems']),
                    'element_edit_readback_mismatch')
            rec['status'] = 'verified'
            rec['verified_element_binding_hash'] = compiled['dependency_fingerprints'][aid]['binding_hash']
            self.persist()
        except (PipelineError, KeyError, TypeError):
            rec['status'] = 'unknown'; self.persist()
            raise UnknownOutcome('element_outcome_unknown_recover_only') from None

    def prepare(self, sid):
        require(not execution_blockers(self.plan, self.root, self.plan['segments'][sid]),
                'execution_retired_or_denied')
        with self.transaction(mutation=True):
            compiled = self._compile(sid)
            require(compiled['delivery'] == 'generate', 'not_generation_delivery')
            require(all(b['code'] in {'remote_binding_missing'} for b in compiled['blocking']),
                    'local_inputs_blocked', {'blocking': compiled['blocking']})
            # 全部增量先检查，避免上传一半才发现下一项没有授权。
            operations = []
            initial_readback = self._inspect(compiled)
            initial_nodes = normalize_nodes(initial_readback)
            initial_check = compare_readback(compiled, initial_readback)
            require(not any(p.startswith('source:') and not p.endswith(':remote_missing')
                            for p in initial_check['problems']), 'existing_source_not_ready')
            element_edits = []
            for aid, element in compiled['elements'].items():
                if element['remote'] and any(p.startswith('element:' + aid + ':') for p in initial_check['problems']):
                    require(element['remote']['id'] in initial_nodes, 'existing_element_not_found')
                    element_edits.append(aid)
                    operations.append({'operation': 'elements', 'asset_id': aid,
                                       'semantic_hash': compiled['dependency_fingerprints'][aid]['semantic_hash']})
            for aid in compiled['dependency_order']:
                if not compiled['dependency_fingerprints'][aid]['remote']:
                    a = self.registry['assets'][aid]
                    operations.append({'operation': 'elements' if a.get('kind') == 'element' else 'uploads',
                                       'asset_id': aid, 'sha256': a.get('sha256'),
                                       'semantic_hash': compiled['dependency_fingerprints'][aid]['semantic_hash']})
            if operations:
                self._grant(compiled, operations + [{'operation': 'drafts', 'segment_id': sid,
                                                      'semantic_hash': compiled['semantic_hash']}])
            for aid in compiled['dependency_order']:
                if not self._compile(sid)['dependency_fingerprints'][aid]['remote']:
                    self._prepare_asset(aid, self._compile(sid))
            for aid in element_edits:
                self._edit_element(aid, self._compile(sid))
            compiled = self._compile(sid)
            rec = self._target(sid)
            require(rec.get('run_calls', 0) == 0 and rec.get('status') not in
                    {'submission_pending', 'unknown', 'confirmation_pending', 'confirmation_unknown',
                     'draft_pending', 'draft_unknown'}, 'submitted_node_cannot_edit')
            target = rec['target']; compiled = self._compile(sid)
            rb = self._inspect(compiled); nodes = normalize_nodes(rb)
            comparison = compare_readback(compiled, rb)
            require(not any(p.startswith(('source:', 'element:')) for p in comparison['problems']),
                    'source_readback_mismatch')
            if comparison['ok']:
                rec.update(status='prepared', request_hash=compiled['request_hash'], semantic_hash=compiled['semantic_hash'])
                self.persist(); return {'status': 'reused_correct_draft', **comparison}
            self._grant(compiled, [{'operation': 'drafts', 'segment_id': sid, 'semantic_hash': compiled['semantic_hash']}])
            actual = nodes.get(target['node_id'])
            if actual:
                require(actual.get('type') == 'video' and actual.get('status') == 'empty' and not actual.get('resources'),
                        'existing_target_not_empty')
            require(rec.get('status') != 'draft_pending', 'draft_outcome_unknown_recover_only')
            rec.update(status='draft_pending', request_hash=compiled['request_hash'], semantic_hash=compiled['semantic_hash'])
            rec.pop('quote', None); self.persist()
            try:
                self.cli.call(self._video_args(compiled, 'edit' if actual else 'create', target))
                check = compare_readback(compiled, self._inspect(compiled))
                require(check['ok'], 'draft_readback_mismatch', {'problems': check['problems']})
            except (PipelineError, KeyError, TypeError):
                rec['status'] = 'draft_unknown'; self.persist()
                raise UnknownOutcome('draft_outcome_unknown_recover_only') from None
            rec['status'] = 'prepared'; self.persist()
            return check

    def _quote(self, sid):
        compiled = self._compile(sid)
        require(compiled['delivery'] == 'generate' and compiled.get('target') and
                not any(b['code'] not in EXECUTION_BLOCKERS for b in compiled['blocking']),
                'compiled_request_blocked')
        contract = self.cli.call(['model', 'find', compiled['request']['model'], '--type', 'video'])
        _model_check(compiled['request'], compiled['references'], contract,
                     explicit_flags='model_contract_fingerprint' in compiled)
        rb = self._inspect(compiled)
        check = compare_readback(compiled, rb)
        require(check['ok'], 'readback_mismatch', {'problems': check['problems']})
        node_id = compiled['target']['node_id']
        node = normalize_nodes(rb)[node_id]
        require(node.get('status') == 'empty' and not node.get('resources'), 'target_already_has_output')
        data = self.cli.call(['node', 'quote', '--project-id', compiled['project_id'], '--node-id', node_id])
        require(data.get('draftVersion') == rb['draftVersion'] and data.get('confirmable') is True,
                'quote_draft_mismatch')
        items = data.get('items', [])
        require(len(items) == 1 and items[0].get('nodeId') == node_id and not items[0].get('error') and
                not items[0].get('generationDiff'), 'quote_item_invalid')
        amount = data.get('totalMaxCredits')
        require(type(amount) is int and amount > 0 and items[0].get('maxCredits') == amount, 'quote_amount_invalid')
        quote = {'draft_version': rb['draftVersion'], 'max_credits': amount,
                 'request_hash': compiled['request_hash'], 'semantic_hash': compiled['semantic_hash']}
        return compiled, quote

    def quote(self, sid):
        with self.transaction():
            compiled, quote = self._quote(sid)
            rec = self._target(sid)
            rec['quote'] = quote; self.persist()
            return quote

    def _predecessors(self, sid):
        for dependency in self.plan['segments'][sid].get('dependencies', []):
            prior = dependency['segment_id']
            rec = self.state['segments'].get(prior, {})
            review = self.state.get('reviews', {}).get(prior, {})
            output = work_path(self.root, rec['output_path']) if rec.get('output_path') else None
            require(review.get('accepted_for_successor') is True and rec.get('output_sha256') and
                    rec.get('output_sha256') == review.get('output_sha256') and
                    output is not None and output.is_file() and file_sha(output) == rec['output_sha256'] and
                    len(rec.get('resource_ids', [])) == 1 and
                    review.get('origin_resource_id') == rec['resource_ids'][0] and
                    all(review.get('checks', {}).get(k) is True for k in dependency.get('checks', [])),
                    'predecessor_review_missing')

    def _verify_derived_bindings(self, compiled, grant):
        """journal不能自授来源权：核对实际字节，PNG无损重编码须逐像素精确相等。"""
        covered, derived = _binding_coverage(compiled, self.approval, grant, self.state)
        require(len(covered) == len(compiled['dependency_order']), 'source_bindings_not_covered')
        with tempfile.TemporaryDirectory(prefix='reference-binding-') as directory:
            for index, aid in enumerate(sorted(derived & set(compiled['sources']))):
                source = compiled['sources'][aid]
                rid = source['remote']['selected_resource_id']
                data = self.cli.call(['resource', 'get', rid, '--project-id', compiled['project_id']])
                require(data.get('resourceId') == rid and data.get('type') == source['type'] and
                        data.get('status') == 'success', 'uploaded_source_resource_not_ready')
                output = Path(directory) / (str(index) + '.media')
                result = self.cli.call(['resource', 'download', rid, '--project-id', compiled['project_id'],
                                        '--output', str(output)])
                evidence = verify_downloaded_source(work_path(self.root, source['path']), output, source, result)
                evidence.update(resource_id=rid, request_hash=compiled['request_hash'])
                self.state['assets'][aid]['source_content_verification'] = evidence
                self.persist()

    def run(self, sid):
        require(not execution_blockers(self.plan, self.root, self.plan['segments'][sid]),
                'execution_retired_or_denied')
        with self.transaction(mutation=True):
            compiled = self._compile(sid)
            self._grant(compiled, [{'operation': 'runs', 'segment_id': sid, 'semantic_hash': compiled['semantic_hash']}])
            grant = self.approval['operations']['runs'][sid]
            require(isinstance(grant, dict), 'run_grant_requires_limits')
            require(self.approval.get('existing_credits_only') is True and
                    self.approval.get('automatic_retry_allowed') is False and
                    self.approval.get('topup_allowed') is False and self.approval.get('publication_allowed') is False,
                    'unsafe_approval_policy')
            rec = self._target(sid)
            require(rec.get('run_calls', 0) == 0 and rec.get('status') not in
                    {'confirmation_pending', 'submission_pending', 'unknown', 'confirmation_unknown',
                     'draft_pending', 'draft_unknown'}, 'once_limit_or_unknown')
            require(type(grant.get('max_calls')) is int and grant['max_calls'] == 1 and
                    type(self.approval.get('max_generation_calls')) is int and
                    self.state['run_calls'] < self.approval['max_generation_calls'],
                    'generation_call_limit')
            self._predecessors(sid)
            self._verify_derived_bindings(compiled, grant)
            account = self.cli.call(['auth', 'account'])
            require(account.get('isVip') is True, 'existing_membership_unavailable')
            compiled, quote = self._quote(sid)  # 永不复用历史核价。
            amount = quote['max_credits']
            require(type(grant.get('credit_ceiling')) is int and amount <= grant['credit_ceiling'] and
                    type(self.approval.get('max_total_credits')) is int and
                    self.state['reserved_credits'] + amount <= self.approval['max_total_credits'], 'credit_ceiling_exceeded')
            rec.update(status='confirmation_pending', quote=quote); self.persist()
            token = None
            try:
                confirmation = self.cli.call(['node', 'confirm', '--project-id', compiled['project_id'],
                                               '--node-id', rec['target']['node_id'], '--credit-ceiling', str(amount)])
                token = confirmation.get('creditConfirmationToken')
                require(isinstance(token, str) and token and confirmation.get('creditCeiling') == amount,
                        'confirmation_invalid')
                # 确认期间被修改的草稿/选中来源必须阻断，token 不等于引用锁。
                rb = self._inspect(compiled)
                check = compare_readback(compiled, rb)
                require(check['ok'] and rb.get('draftVersion') == quote['draft_version'], 'post_confirm_draft_changed')
                rec.update(run_calls=1, reserved_credits=amount, status='submission_pending',
                           request_hash=compiled['request_hash'], semantic_hash=compiled['semantic_hash'])
                self.state['run_calls'] += 1
                self.state['reserved_credits'] += amount
                self.persist()
                data = self.cli.call(['node', 'run', '--project-id', compiled['project_id'],
                                      '--node-id', rec['target']['node_id'], '--submit-id', rec['target']['submit_id'],
                                      '--credit-token', token])
                items = data.get('items', [])
                require(len(items) == 1 and items[0].get('nodeId') == rec['target']['node_id'] and
                        items[0].get('submitId') == rec['target']['submit_id'], 'run_identity_mismatch')
                item = items[0]
                require(not item.get('error') and not item.get('generationDiff'), 'run_rejected_or_changed')
                rec.update(status='submitted', operation_state=_safe_state(item.get('state')),
                           resource_ids=_resource_ids(item.get('resources', [])))
                self.persist()
                return {'status': rec['status'], 'submit_id': rec['target']['submit_id'], 'reserved_credits': amount}
            except (PipelineError, KeyError, TypeError):
                rec['status'] = 'unknown' if rec.get('run_calls') else 'confirmation_unknown'
                self.persist()
                raise UnknownOutcome('execution_unknown_recover_only') from None
            finally:
                token = None

    def recover(self, sid=None, asset_id=None):
        """仅只读核验原身份；即使 absent，也不重提交或释放预算。"""
        with self.transaction():
            if asset_id:
                rec = self.state['assets'].get(asset_id)
                require(rec is not None, 'asset_journal_missing')
                rb = self._show([rec['node_id']]); node = normalize_nodes(rb).get(rec['node_id'])
                if node:
                    asset = self.registry['assets'][asset_id]
                    if asset.get('kind') == 'element':
                        require(node.get('type') == 'element', 'recovery_type_mismatch')
                        remote = {'kind': 'node', 'id': rec['node_id'], 'project_id': self.plan['project_id']}
                    else:
                        require(node.get('type') == asset['media_type'] and node.get('status') == 'success' and
                                any(r.get('resourceId') == rec['resource_id'] and r.get('status') == 'success'
                                    for r in node.get('resources', [])), 'recovery_resource_not_ready')
                        remote = {'kind': 'node', 'id': rec['node_id'], 'project_id': self.plan['project_id'],
                                  'selected_resource_id': rec['resource_id']}
                        rec['verified_import_resource_id'] = rec['resource_id']
                    rec.update(status='verified', remote=remote)
                    if asset.get('kind') == 'element':
                        try:
                            candidates = [sid] if sid else list(self.plan['segments'])
                            found = False
                            for candidate in candidates:
                                compiled = self._compile(candidate)
                                if asset_id in compiled['elements']:
                                    check = compare_readback(compiled, self._inspect(compiled))
                                    require(not any(p.startswith('element:' + asset_id + ':') for p in check['problems']),
                                            'recovery_element_bindings_mismatch')
                                    rec['verified_element_binding_hash'] = compiled['dependency_fingerprints'][asset_id]['binding_hash']
                                    found = True
                                    break
                            require(found, 'recovery_element_not_in_plan')
                        except PipelineError:
                            rec['status'] = 'unknown'; self.persist()
                            raise
                    self.persist()
                    return {'status': 'asset_recovered_read_only'}
                return {'status': 'unknown', 'automatic_resubmit': False}
            require(sid in self.state['segments'], 'segment_journal_missing')
            rec = self.state['segments'][sid]
            if not rec.get('run_calls'):
                check = compare_readback(self._compile(sid), self._inspect(self._compile(sid)))
                if check['ok'] and rec.get('status') not in {'confirmation_unknown', 'confirmation_pending'}:
                    rec['status'] = 'prepared'; self.persist()
                return {'status': rec.get('status'), 'comparison': check, 'automatic_resubmit': False}
            try:
                data = self.cli.call(['operation', 'status', rec['target']['submit_id'], '--project-id', self.plan['project_id']])
            except PipelineError:
                return {'status': 'unknown', 'submit_id': rec['target']['submit_id'], 'automatic_resubmit': False}
            require(data.get('operationRef') == rec['target']['submit_id'], 'recovery_operation_mismatch')
            rec.update(operation_state=_safe_state(data.get('state')), resource_ids=_resource_ids(data.get('resources', [])))
            rec['status'] = 'observed'
            self.persist()
            return {'status': rec['status'], 'operation_state': rec['operation_state'],
                    'resource_ids': rec['resource_ids'], 'automatic_resubmit': False}

    def download(self, sid, relative_output):
        with self.transaction():
            rec = self.state['segments'].get(sid, {})
            require(rec.get('run_calls') == 1 and len(rec.get('resource_ids', [])) == 1, 'output_not_resolved')
            resource = rec['resource_ids'][0]
            data = self.cli.call(['resource', 'get', resource, '--project-id', self.plan['project_id']])
            require(data.get('resourceId') == resource and data.get('type') == 'video' and data.get('status') == 'success',
                    'output_resource_not_ready')
            output = work_path(self.root, relative_output)
            require(not output.exists(), 'output_already_exists')
            output.parent.mkdir(parents=True, exist_ok=True)
            result = self.cli.call(['resource', 'download', resource, '--project-id', self.plan['project_id'], '--output', str(output)])
            require(output.is_file() and output.stat().st_size > 0 and result.get('size') == output.stat().st_size and
                    result.get('sha256') == file_sha(output), 'download_fingerprint_mismatch')
            rec.update(status='downloaded_pending_review', output_path=relative_output,
                       output_sha256=file_sha(output), output_bytes=output.stat().st_size)
            self.persist()
            return {k: rec[k] for k in ['status', 'output_path', 'output_sha256', 'output_bytes']}


def _safe_state(value):
    return value if isinstance(value, str) and SAFE_CODE.fullmatch(value) else 'unknown'


def _resource_ids(resources):
    ids = [r.get('resourceId') for r in resources]
    require(all(isinstance(v, str) and UUID.fullmatch(v) for v in ids), 'invalid_resource_identity')
    return ids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['compile', 'compare', 'inspect', 'prepare', 'quote', 'run', 'recover', 'download'])
    parser.add_argument('--registry', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--work-root', required=True)
    parser.add_argument('--segment')
    parser.add_argument('--asset')
    parser.add_argument('--output')
    parser.add_argument('--readback')
    parser.add_argument('--state')
    parser.add_argument('--approval')
    parser.add_argument('--cli', default='/private/tmp/dreamina-canvas-battle-v02')
    args = parser.parse_args(argv)
    try:
        registry, plan = read_json(args.registry), read_json(args.plan)
        if args.command == 'compile':
            ids = [args.segment] if args.segment else list(plan['segments'])
            result = {'segments': {sid: compile_segment(registry, plan, sid, args.work_root) for sid in ids}}
            if args.output:
                save_json(args.output, result)
            print(json.dumps({'ok': True, 'compiled_segments': len(ids), 'executable_segments':
                              [sid for sid, c in result['segments'].items() if c['executable']],
                              'local_ready_segments': [sid for sid, c in result['segments'].items() if c['local_ready']],
                              'blocked_segments': [sid for sid, c in result['segments'].items() if c['blocking']]}))
            return 0
        require(args.segment or args.asset, 'segment_required')
        if args.command == 'compare':
            require(args.readback and args.segment, 'readback_required')
            result = compare_readback(compile_segment(registry, plan, args.segment, args.work_root), read_json(args.readback))
        else:
            require(args.state is not None, 'state_path_required')
            executor = Executor(registry, plan, args.work_root, args.state, OfficialCLI(args.cli),
                                read_json(args.approval) if args.approval else None)
            if args.command == 'recover':
                result = executor.recover(args.segment, args.asset)
            elif args.command == 'download':
                require(args.output is not None, 'download_output_required')
                result = executor.download(args.segment, args.output)
            else:
                result = getattr(executor, args.command)(args.segment)
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False))
        return 0
    except PipelineError as error:
        print(json.dumps({'ok': False, 'error': error.code, 'details': error.details}, ensure_ascii=False))
        return 2
    except (KeyError, TypeError, ValueError, OSError):
        print(json.dumps({'ok': False, 'error': 'invalid_input_or_local_io'}))
        return 2
    except Exception:
        # 顶层也不打印第三方异常字符串或含token的调用栈。
        print(json.dumps({'ok': False, 'error': 'unexpected_failure_no_raw_output'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
