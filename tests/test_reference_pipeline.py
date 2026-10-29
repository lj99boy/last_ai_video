"""离线验证创作编译与消费门禁；FakeCLI 从不访问外部服务。"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import multiprocessing
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zlib


MODULE = Path(__file__).resolve().parents[1] / 'tools/reference_pipeline.py'
spec = importlib.util.spec_from_file_location('reference_pipeline', MODULE)
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


def nid(name):
    return 'node_' + hashlib.sha256(name.encode()).hexdigest()[:10]


PROJECT = uid('project')
TARGET = {'node_id': nid('video'), 'update_id': uid('video_update'), 'submit_id': uid('video_submit')}


def binding(asset):
    loc = asset['remote']
    result = {'kind': loc['kind'], 'id': loc['id'], 'type': asset.get('media_type', 'element'),
              'writebackSupported': True}
    if asset.get('kind') != 'element':
        result['resource'] = {'resourceId': loc.get('selected_resource_id', loc['id']),
                              'type': asset['media_type'], 'status': 'success'}
    return result


class FakeCLI:
    def __init__(self, registry):
        self.nodes, self.resources, self.calls = {}, {}, []
        self.blobs = {}
        self.version, self.timeout_run, self.timeout_save = 1, False, False
        self.bad_quote, self.change_after_confirm = False, False
        self.model_contract = None
        self.token = 'SECRET-CREDIT-TOKEN-DO-NOT-PERSIST'
        for aid, asset in registry['assets'].items():
            if asset.get('remote') and asset.get('kind') != 'element':
                loc = asset['remote']; rid = loc['selected_resource_id']
                res = {'resourceId': rid, 'type': asset['media_type'], 'status': 'success'}
                self.resources[rid] = res
                if loc['kind'] == 'node':
                    self.nodes[loc['id']] = {'nodeId': loc['id'], 'type': asset['media_type'],
                                             'status': 'success', 'resources': [res], 'upstreamNodeIds': []}
        for aid, asset in registry['assets'].items():
            if asset.get('kind') == 'element' and asset.get('remote'):
                source = registry['assets']
                binds = {'main': binding(source[asset['main']]),
                         'auxiliaries': [binding(source[c]) for c in asset.get('auxiliaries', [])]}
                if asset.get('voice'):
                    binds['voice'] = binding(source[asset['voice']])
                children = [asset['main'], *asset.get('auxiliaries', []), *([asset['voice']] if asset.get('voice') else [])]
                self.nodes[asset['remote']['id']] = {'nodeId': asset['remote']['id'], 'type': 'element',
                    'subjectBindings': binds, 'resources': [], 'upstreamNodeIds':
                    [source[c]['remote']['id'] for c in children if source[c]['remote']['kind'] == 'node']}

    def _ref(self, typed):
        kind, value = typed.split(':', 1)
        if kind == 'node':
            node = self.nodes[value]
            result = {'kind': 'node', 'id': value, 'type': node['type'], 'writebackSupported': True}
            if node['type'] != 'element':
                result['resource'] = deepcopy(node['resources'][0])
            return result
        return {'kind': 'resource', 'id': value, 'type': self.resources[value]['type'],
                'writebackSupported': True, 'resource': deepcopy(self.resources[value])}

    def call(self, args):
        self.calls.append(list(args))
        def get(flag, default=None):
            return args[args.index(flag) + 1] if flag in args else default
        def many(flag):
            return [args[i + 1] for i, v in enumerate(args) if v == flag]
        if args[:2] == ['node', 'show']:
            return {'draftVersion': self.version, 'nodes': [{'result': 'FOUND', 'node': deepcopy(self.nodes[n])}
                    if n in self.nodes else {'result': 'MISSING'} for n in many('--node-id')]}
        if args[:2] == ['model', 'find']:
            if self.model_contract is not None:
                return deepcopy(self.model_contract)
            return {'items': [{'model': 'seedance_2.5', 'modes': [
                {'name': 'm2v', 'flags': [], 'references': {'min': 1, 'max': 50}},
                {'name': 'first_last_frame', 'flags': [], 'references': {'min': 1, 'max': 2}},
                {'name': 't2v', 'flags': [], 'references': {'min': 0, 'max': 0}}]}]}
        if args[:2] == ['auth', 'account']:
            return {'isVip': True}
        if args[:2] == ['resource', 'upload']:
            self.resources[get('--resource-id')] = {'resourceId': get('--resource-id'),
                                                     'type': get('--type'), 'status': 'success'}
            self.blobs[get('--resource-id')] = Path(get('--file')).read_bytes()
            return {'resourceId': get('--resource-id')}
        if args[:2] in (['node', 'create'], ['node', 'edit']):
            if self.timeout_save:
                raise rp.UnknownOutcome('cli_outcome_unknown')
            node_id, kind = get('--node-id'), args[2]
            node = {'nodeId': node_id, 'type': kind, 'status': 'empty', 'resources': [], 'upstreamNodeIds': []}
            if kind == 'element':
                def selected(value):
                    return self._ref(('node:' if value.startswith('node_') else 'res:') + value)
                node['subjectBindings'] = {'main': selected(get('--main')),
                                           'auxiliaries': [selected(v) for v in many('--auxiliary')]}
                if get('--voice'):
                    node['subjectBindings']['voice'] = selected(get('--voice'))
                node['upstreamNodeIds'] = [v['id'] for v in [node['subjectBindings']['main'],
                    *node['subjectBindings']['auxiliaries'], *([node['subjectBindings']['voice']]
                    if node['subjectBindings'].get('voice') else [])] if v['kind'] == 'node']
            elif get('--resource-id'):
                node.update(status='success', resources=[deepcopy(self.resources[get('--resource-id')])])
            elif kind == 'video':
                refs, prompt = many('--ref'), get('--prompt')
                parts, start = [], 0
                for match in re.finditer(r'\{\{((?:node|res):[^}]+)\}\}', prompt):
                    if match.start() > start:
                        parts.append({'kind': 'text', 'text': prompt[start:match.start()]})
                    parts.append({'kind': 'reference', 'referenceIndex': refs.index(match.group(1))})
                    start = match.end()
                if start < len(prompt):
                    parts.append({'kind': 'text', 'text': prompt[start:]})
                node['generation'] = {'model': get('--model'), 'mode': get('--mode'), 'ratio': get('--ratio'),
                    'resolution': get('--resolution'), 'durationSeconds': int(get('--duration')),
                    'outputCount': int(get('--count')), 'prompt': prompt, 'promptParts': parts,
                    'references': [self._ref(v) for v in refs], 'writebackSupported': True, 'writebackBlockers': []}
                node['upstreamNodeIds'] = [v.split(':', 1)[1] for v in refs if v.startswith('node:')]
            self.nodes[node_id] = node
            self.version += 1
            return {'node': deepcopy(node)}
        if args[:2] == ['node', 'quote']:
            return {'draftVersion': self.version + int(self.bad_quote), 'confirmable': True,
                    'totalMaxCredits': 90, 'items': [{'nodeId': get('--node-id'), 'maxCredits': 90}]}
        if args[:2] == ['node', 'confirm']:
            if self.change_after_confirm:
                self.version += 1
            return {'creditConfirmationToken': self.token, 'creditCeiling': int(get('--credit-ceiling'))}
        if args[:2] == ['node', 'run']:
            if self.timeout_run:
                raise rp.UnknownOutcome('cli_outcome_unknown')
            return {'items': [{'nodeId': get('--node-id'), 'submitId': get('--submit-id'),
                               'state': 'accepted', 'resources': [{'resourceId': uid('output')}]}]}
        if args[:2] == ['operation', 'status']:
            self.resources[uid('output')] = {'resourceId': uid('output'), 'type': 'video', 'status': 'success'}
            return {'operationRef': args[2], 'state': 'succeeded', 'resources': [{'resourceId': uid('output'), 'state': 'success'}]}
        if args[:2] == ['resource', 'get']:
            return deepcopy(self.resources[args[2]])
        if args[:2] == ['resource', 'download']:
            output = Path(get('--output')); output.write_bytes(self.blobs.get(args[2], b'fake-video'))
            return {'size': output.stat().st_size, 'sha256': rp.file_sha(output)}
        raise RuntimeError('unexpected FakeCLI command')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.host_tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.host_tmp.cleanup)
        self.authority_dir = Path(self.host_tmp.name) / 'authority'
        store_patch = patch.object(rp, 'AUTHORITY_STORE', self.authority_dir)
        store_patch.start(); self.addCleanup(store_patch.stop)
        self.registry = {'assets': {}}
        for aid, kind, roles in [('HERO', 'image', ['identity', 'costume', 'first_frame', 'last_frame']),
                                  ('WORLD', 'image', ['environment', 'first_frame', 'last_frame']),
                                  ('STYLE', 'image', ['style']), ('VOICE', 'audio', ['voice'])]:
            path = self.root / (aid + '.bin'); path.write_bytes(aid.encode())
            self.registry['assets'][aid] = {'kind': 'media', 'media_type': kind, 'path': path.name,
                'sha256': rp.file_sha(path), 'bytes': path.stat().st_size, 'status': 'ready',
                'allowed_roles': roles, 'forbidden_roles': ['composition'],
                'characters': [{'id': 'marko', 'era': 1648, 'age': 31}] if aid == 'HERO' else [],
                'review': {'status': 'reviewed'}, 'remote': {'kind': 'node', 'id': nid(aid),
                    'project_id': PROJECT, 'selected_resource_id': uid(aid)}}
        self.plan = {'work_id': 'test', 'project_id': PROJECT, 'baseline_files': {}, 'segments': {'BATTLE': {
            'beat_ids': ['S005'], 'timeline': {'start_s': 15, 'end_s': 18}, 'delivery': 'generate',
            'era': 1648, 'characters': [{'id': 'marko', 'era': 1648, 'age': 31}],
            'viewing_task': 'understand rescue route', 'camera_intent': 'frontal', 'mode': 'm2v',
            'model': 'seedance_2.5', 'ratio': '16:9', 'resolution': '720p', 'duration_seconds': 5,
            'prompt': '[[HERO]] only identity; [[WORLD]] only world; [[STYLE]] only style.',
            'references': [{'asset_id': a, 'alias': a, 'roles': r, 'exclusions': []}
                for a, r in [('HERO', ['identity']), ('WORLD', ['environment']), ('STYLE', ['style'])]],
            'acceptance': ['original speed review'], 'remote': deepcopy(TARGET)}}}
        self.state = self.root / 'state.json'

    def compile(self):
        return rp.compile_segment(self.registry, self.plan, 'BATTLE', self.root)

    def approval(self):
        compiled = self.compile()
        evidence = self.root / 'human-approval.json'; evidence.write_text('{"answer":"explicit test approval"}')
        return {'schema_version': 1, 'human_approved': True, 'project_id': PROJECT,
                'evidence': {'path': evidence.name, 'sha256': rp.file_sha(evidence)},
                'operations': {'uploads': {a: v.get('sha256') for a, v in self.registry['assets'].items()
                                          if v.get('kind') != 'element'},
                    'elements': {a: compiled['dependency_fingerprints'][a]['semantic_hash']
                                 for a, v in self.registry['assets'].items() if v.get('kind') == 'element'},
                    'drafts': {'BATTLE': {'semantic_hash': compiled['semantic_hash'], 'source_bindings':
                        {aid: fp['binding_hash'] for aid, fp in compiled['dependency_fingerprints'].items() if fp['remote']}}},
                    'runs': {'BATTLE': {'semantic_hash': compiled['semantic_hash'], 'max_calls': 1, 'credit_ceiling': 100,
                        'source_bindings': {aid: fp['binding_hash'] for aid, fp in
                                            compiled['dependency_fingerprints'].items() if fp['remote']}}}},
                'max_total_credits': 100, 'max_generation_calls': 1, 'existing_credits_only': True,
                'automatic_retry_allowed': False, 'topup_allowed': False, 'publication_allowed': False}

    def executor(self, approval=True):
        cli = FakeCLI(self.registry)
        return rp.Executor(self.registry, self.plan, self.root, self.state, cli,
                           self.approval() if approval else None), cli

    def add_element(self):
        self.registry['assets']['MARKO'] = {'kind': 'element', 'main': 'HERO', 'auxiliaries': ['STYLE'],
            'voice': 'VOICE', 'status': 'ready', 'allowed_roles': ['identity'], 'forbidden_roles': [],
            'characters': [{'id': 'marko', 'era': 1648, 'age': 31}], 'review': {'status': 'local contract only'},
            'remote': {'kind': 'node', 'id': nid('MARKO'), 'project_id': PROJECT}}
        seg = self.plan['segments']['BATTLE']
        seg['references'][0]['asset_id'] = 'MARKO'

    def test_deterministic_order_parts_and_multiple_media(self):
        compiled = self.compile()
        self.assertEqual(compiled, self.compile())
        self.assertTrue(compiled['executable'])
        self.assertEqual([r['asset_id'] for r in compiled['references']], ['HERO', 'WORLD', 'STYLE'])
        self.assertEqual([p['referenceIndex'] for p in compiled['request']['promptParts'] if p['kind'] == 'reference'], [0, 1, 2])

    def test_dedup_same_source_multiple_roles(self):
        seg = self.plan['segments']['BATTLE']
        seg['references'].append({'asset_id': 'HERO', 'alias': 'CLOTH', 'roles': ['costume']})
        seg['prompt'] += ' [[CLOTH]] costume only.'
        compiled = self.compile()
        self.assertEqual(len(compiled['references']), 3)
        self.assertEqual(compiled['aliases']['CLOTH'], 0)

    def test_prompt_first_physical_appearance_must_match_declared_order(self):
        self.plan['segments']['BATTLE']['prompt'] = '[[WORLD]], [[HERO]], [[STYLE]].'
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'reference_first_appearance_order_conflict')

    @unittest.skipUnless(Path('/private/tmp/dreamina-canvas-battle-v02').is_file(), 'official local CLI not installed')
    def test_official_local_dry_run_reference_order_contract(self):
        """真实binary仅--dry-run，不靠FakeCLI推断正文/槽序契约。"""
        seg = self.plan['segments']['BATTLE']
        seg['references'] = seg['references'][:2]
        seg['prompt'] = '[[HERO]] first, [[WORLD]] second.'
        compiled = self.compile()
        cli = rp.OfficialCLI('/private/tmp/dreamina-canvas-battle-v02')
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli)
        # 连同生产中的新ID生成分支一起让真实CLI验证，不只测试手填fixture。
        executor.plan['segments']['BATTLE'].pop('remote')
        with executor.transaction():
            generated_target = executor._target('BATTLE')['target']
        self.assertRegex(generated_target['node_id'], r'^node_[0123456789abcdefghjkmnpqrstvwxyz]{10}$')
        args = executor._video_args(compiled, 'create', generated_target) + ['--dry-run']
        data = cli.call(args)
        self.assertEqual(data['validationScope'], 'local'); self.assertEqual(data['sideEffects'], [])
        self.assertEqual([r['id'] for r in data['plan']['references']],
                         [r['remote']['id'] for r in compiled['references']])
        # 官方实测：相同--ref A B，正文B A会实际成为B A；编译必须先拒绝。
        args[args.index('--prompt') + 1] = '{{node:' + nid('WORLD') + '}} first, {{node:' + nid('HERO') + '}} second.'
        reverse = cli.call(args)
        self.assertEqual([r['id'] for r in reverse['plan']['references']], [nid('WORLD'), nid('HERO')])
        seg['prompt'] = '[[WORLD]] first, [[HERO]] second.'
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'reference_first_appearance_order_conflict')

    def test_alias_roles_and_era_rejected(self):
        original = deepcopy(self.plan)
        for mutate, code in [
            (lambda: self.plan['segments']['BATTLE'].update(prompt='[[MISSING]]'), 'undefined_prompt_alias'),
            (lambda: self.plan['segments']['BATTLE']['references'][0].update(roles=['composition']), 'role_not_allowed'),
            (lambda: self.plan['segments']['BATTLE']['characters'][0].update(era=1636), 'identity_era_conflict'),
            (lambda: self.plan['segments']['BATTLE']['characters'][0].update(age=19), 'identity_age_conflict')]:
            self.plan = deepcopy(original); mutate()
            with self.assertRaises(rp.PipelineError) as error:
                self.compile()
            self.assertEqual(error.exception.code, code)

    def test_style_source_does_not_inherit_identity(self):
        self.registry['assets']['STYLE']['characters'] = [{'id': 'marko', 'era': 1675, 'age': 58}]
        self.assertTrue(self.compile()['executable'])

    def test_actual_registry_identity_role_names_enforce_era_and_age(self):
        for role in ['identity_primary', 'costume_reference', 'identity_source']:
            self.registry['assets']['HERO']['allowed_roles'].append(role)
            self.plan['segments']['BATTLE']['references'][0]['roles'] = [role]
            self.plan['segments']['BATTLE']['characters'][0]['era'] = 1636
            with self.assertRaises(rp.PipelineError) as error: self.compile()
            self.assertEqual(error.exception.code, 'identity_era_conflict')
            self.plan['segments']['BATTLE']['characters'][0]['era'] = 1648
            self.plan['segments']['BATTLE']['characters'][0]['age'] = 19
            with self.assertRaises(rp.PipelineError) as error: self.compile()
            self.assertEqual(error.exception.code, 'identity_age_conflict')
            self.plan['segments']['BATTLE']['characters'][0]['age'] = 31

    def test_explicit_unknown_supporting_actor_age_does_not_invent_age(self):
        self.registry['assets']['HERO']['characters'][0]['age'] = None
        self.plan['segments']['BATTLE']['characters'][0]['age'] = None
        self.assertTrue(self.compile()['executable'])
        self.registry['assets']['HERO']['characters'][0].pop('age')
        with self.assertRaises(rp.PipelineError): self.compile()

    def test_local_ready_without_remote_blocks_not_loses_plan(self):
        self.registry['assets']['HERO']['remote'] = None
        compiled = self.compile()
        self.assertFalse(compiled['executable'])
        self.assertEqual(compiled['aliases']['HERO'], 0)
        self.assertIn({'code': 'remote_binding_missing', 'asset_id': 'HERO'}, compiled['blocking'])
        self.assertFalse(self.state.exists())

    def test_missing_file_and_fingerprint_and_baseline(self):
        self.registry['assets']['HERO']['bytes'] += 1
        self.assertIn({'code': 'media_fingerprint_mismatch', 'asset_id': 'HERO'}, self.compile()['blocking'])
        self.registry['assets']['HERO']['status'] = 'planned_missing'
        self.plan['baseline_files'] = {'missing.md': '0' * 64}
        self.assertFalse(self.compile()['executable'])

    def test_element_closure_binding_hash_changes(self):
        self.add_element()
        before = self.compile()
        self.assertIn('VOICE', before['dependency_order'])
        self.registry['assets']['VOICE']['remote']['selected_resource_id'] = uid('newvoice')
        after = self.compile()
        self.assertEqual(before['semantic_hash'], after['semantic_hash'])
        self.assertNotEqual(before['request_hash'], after['request_hash'])
        self.assertNotEqual(before['dependency_fingerprints']['MARKO']['binding_hash'],
                            after['dependency_fingerprints']['MARKO']['binding_hash'])

    def test_element_bad_aux_voice_and_cycle(self):
        self.add_element()
        self.registry['assets']['MARKO']['auxiliaries'] = ['VOICE']
        with self.assertRaises(rp.PipelineError): self.compile()
        self.registry['assets']['MARKO']['auxiliaries'] = ['MARKO']
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'element_dependency_cycle')

    def test_element_nonimage_main_remains_unverified_not_executable(self):
        self.add_element(); self.registry['assets']['MARKO']['main'] = 'VOICE'
        compiled = self.compile()
        self.assertIn({'code': 'element_main_type_runtime_unverified', 'asset_id': 'MARKO'}, compiled['blocking'])
        self.assertFalse(compiled['executable'])

    def test_runtime_dependencies_reject_notes_and_missing_segments(self):
        seg = self.plan['segments']['BATTLE']
        cases = [(['narrative note'], 'dependency_must_be_object'),
                 ([{'segment_id': 'MISSING', 'checks': []}], 'dependency_segment_not_found'),
                 ([{'segment_id': 'BATTLE', 'checks': 'not-list'}], 'dependency_checks_must_be_string_list'),
                 ([{'segment_id': 'BATTLE', 'checks': []}], 'segment_dependency_cycle')]
        for dependencies, expected in cases:
            seg['dependencies'] = dependencies
            with self.assertRaises(rp.PipelineError) as error: self.compile()
            self.assertEqual(error.exception.code, expected)

    def test_offline_profile_does_not_claim_unqueried_ratios(self):
        self.plan['segments']['BATTLE']['ratio'] = '21:9'
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'offline_profile_only_16x9_720p')

    def pin_model_contract(self, resolutions=None):
        contract = {'items': [{'model': 'seedance_2.5', 'modes': [{'name': 'm2v', 'flags': [
            {'flag': '--ratio', 'values': ['16:9']},
            {'flag': '--resolution', 'values': resolutions or ['480p', '720p']},
            {'flag': '--duration', 'min': 4, 'max': 30},
            {'flag': '--count', 'min': 1, 'max': 4}],
            'references': {'min': 1, 'max': 50}}]}]}
        path = self.root / 'model-find.json'
        path.write_text(json.dumps({'ok': True, 'data': contract}))
        self.plan['model_contract'] = {'path': path.name, 'sha256': rp.file_sha(path)}
        return contract, path

    def test_pinned_model_contract_preserves_historical_720_semantic(self):
        old = self.compile()
        self.assertEqual(old['semantic_hash'], '9f0e1b5cc78d781bc89d7d5c294902bae928bf8b932d675ca542ce148d1ea9df')
        self.assertNotIn('model_contract_fingerprint', old)
        self.assertEqual(old['model_validation'], 'offline_16x9_720p_profile_only')
        self.pin_model_contract()
        pinned = self.compile()
        self.assertNotEqual(pinned['semantic_hash'], old['semantic_hash'])
        self.assertEqual(pinned['request_hash'], old['request_hash'])
        self.assertEqual(pinned['model_validation'], 'pinned_official_contract')

    def test_480_without_pinned_contract_stays_blocked(self):
        self.plan['segments']['BATTLE']['resolution'] = '480p'
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'offline_profile_only_16x9_720p')

    def test_480_pinned_contract_all_execution_stages_and_once_guard(self):
        self.plan['segments']['BATTLE']['resolution'] = '480p'
        contract, _ = self.pin_model_contract()
        executor, cli = self.executor()
        cli.model_contract = contract
        self.assertEqual(executor.prepare('BATTLE')['ok'], True)
        self.assertEqual(executor.quote('BATTLE')['max_credits'], 90)
        executor.run('BATTLE')
        self.assertEqual(executor.state['run_calls'], 1)
        self.assertEqual(executor.state['reserved_credits'], 90)
        self.assertEqual(sum(args[:2] == ['model', 'find'] for args in cli.calls), 2)
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'once_limit_or_unknown')
        self.assertEqual(sum(args[:2] == ['node', 'run'] for args in cli.calls), 1)

    def test_pinned_contract_tamper_missing_and_override_fail_closed(self):
        _, path = self.pin_model_contract()
        original = path.read_bytes()
        executor, cli = self.executor()
        path.write_bytes(original + b' ')
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'model_contract_fingerprint_mismatch')
        self.assertEqual(cli.calls, [])
        path.unlink()
        with self.assertRaises(rp.PipelineError) as error: self.compile()
        self.assertEqual(error.exception.code, 'model_contract_missing')
        path.write_bytes(original)
        with self.assertRaises(rp.PipelineError) as error:
            rp.compile_segment(self.registry, self.plan, 'BATTLE', self.root, model_contract={})
        self.assertEqual(error.exception.code, 'model_contract_override_conflict')

    def test_pinned_contract_repin_changes_semantic_and_rejects_old_approval(self):
        self.pin_model_contract()
        approval = self.approval()
        original = self.compile()
        self.pin_model_contract(['480p', '720p', '1080p'])
        changed = self.compile()
        self.assertNotEqual(original['semantic_hash'], changed['semantic_hash'])
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, FakeCLI(self.registry), approval)
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'authorization_delta')
        self.assertTrue(all(args[:2] == ['node', 'show'] for args in executor.cli.calls))

    def test_pinned_contract_requires_explicit_flags_and_success_envelope(self):
        contract, path = self.pin_model_contract()
        contract['items'][0]['modes'][0]['flags'] = []
        for data, expected in [(contract, 'model_contract_explicit_flags_required'),
                               ({'ok': False, 'data': contract}, 'model_contract_envelope_failed')]:
            path.write_text(json.dumps(data))
            self.plan['model_contract']['sha256'] = rp.file_sha(path)
            with self.assertRaises(rp.PipelineError) as error: self.compile()
            self.assertEqual(error.exception.code, expected)

    def test_480_live_capability_withdrawal_blocks_before_confirmation(self):
        self.plan['segments']['BATTLE']['resolution'] = '480p'
        contract, _ = self.pin_model_contract()
        executor, cli = self.executor()
        executor.prepare('BATTLE')
        contract['items'][0]['modes'][0]['flags'][1]['values'] = ['720p']
        cli.model_contract = contract
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'live_model_contract_conflict')
        self.assertFalse(any(args[:2] in (['node', 'confirm'], ['node', 'run']) for args in cli.calls))
        self.assertEqual(executor.state['run_calls'], 0)

    def test_480_live_missing_flags_cannot_inherit_pinned_capabilities(self):
        self.plan['segments']['BATTLE']['resolution'] = '480p'
        self.pin_model_contract()
        executor, cli = self.executor()
        executor.prepare('BATTLE')
        # 默认FakeCLI的实时响应缺flag，不能因本地合同已核验而按无限制放行。
        with self.assertRaises(rp.PipelineError) as error: executor.quote('BATTLE')
        self.assertEqual(error.exception.code, 'model_contract_explicit_flags_required')
        self.assertFalse(any(args[:2] in (['node', 'quote'], ['node', 'confirm'], ['node', 'run']) for args in cli.calls))

    def test_first_last_order_and_modes(self):
        seg = self.plan['segments']['BATTLE']
        seg['references'] = [dict(asset_id='HERO', alias='FIRST', roles=['first_frame']),
                             dict(asset_id='WORLD', alias='LAST', roles=['last_frame'])]
        seg['prompt'], seg['mode'] = '[[FIRST]] to [[LAST]].', 'first_last_frame'
        compiled = self.compile()
        self.assertEqual([r['asset_id'] for r in compiled['references']], ['HERO', 'WORLD'])
        seg['references'].reverse()
        with self.assertRaises(rp.PipelineError): self.compile()
        seg['references'] = seg['references'][1:]; seg['prompt'] = '[[FIRST]]'
        self.assertTrue(self.compile()['executable'])
        seg['mode'] = 't2v'
        with self.assertRaises(rp.PipelineError): self.compile()

    def test_element_cannot_be_first_last(self):
        self.add_element(); self.plan['segments']['BATTLE']['mode'] = 'first_last_frame'
        with self.assertRaises(rp.PipelineError): self.compile()

    def test_prepare_readback_reuse_and_full_reference_validation(self):
        executor, cli = self.executor()
        self.assertTrue(executor.prepare('BATTLE')['ok'])
        writes = sum(c[:2] == ['node', 'create'] for c in cli.calls)
        self.assertEqual(executor.prepare('BATTLE')['status'], 'reused_correct_draft')
        self.assertEqual(sum(c[:2] == ['node', 'create'] for c in cli.calls), writes)
        cli.nodes[TARGET['node_id']]['generation']['promptParts'][0]['referenceIndex'] = 2
        self.assertFalse(executor.inspect('BATTLE')['ok'])

    def test_element_full_readback_detects_changed_auxiliary(self):
        self.add_element(); executor, cli = self.executor()
        executor.prepare('BATTLE')
        self.assertTrue(executor.inspect('BATTLE')['ok'])
        cli.nodes[nid('MARKO')]['subjectBindings']['auxiliaries'][0]['resource']['resourceId'] = uid('wrong')
        self.assertFalse(executor.inspect('BATTLE')['ok'])
        with self.assertRaises(rp.PipelineError): executor.quote('BATTLE')

    def test_actual_cli_reference_shape_recovers_with_unique_source_without_write(self):
        """真实CLI只返回绑定身份；唯一成功来源可补足选中产物证据。"""
        executor, cli = self.executor(); executor.prepare('BATTLE')
        for ref in cli.nodes[TARGET['node_id']]['generation']['references']:
            ref.pop('resource'); ref['title'] = 'source title'
            self.assertEqual(set(ref), {'kind', 'id', 'type', 'title', 'writebackSupported'})
        with executor.transaction():
            executor.state['segments']['BATTLE']['status'] = 'draft_unknown'
            executor.persist()
        writes_before = sum(c[:2] in [['node', 'create'], ['node', 'edit'], ['node', 'run'], ['node', 'confirm']]
                            for c in cli.calls)
        result = executor.recover('BATTLE')
        self.assertTrue(result['comparison']['ok'])
        self.assertEqual(result['status'], 'prepared')
        self.assertFalse(result['automatic_resubmit'])
        self.assertEqual(sum(c[:2] in [['node', 'create'], ['node', 'edit'], ['node', 'run'], ['node', 'confirm']]
                             for c in cli.calls), writes_before)

    def test_explicit_binding_resource_conflict_never_falls_back_to_good_source(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        original = deepcopy(cli.nodes[TARGET['node_id']]['generation']['references'][0]['resource'])
        bad_resources = [dict(original, resourceId=uid('wrong')), dict(original, status='failed'),
                         dict(original, type='video'), {}, None]
        for resource in bad_resources:
            with self.subTest(resource=resource):
                cli.nodes[TARGET['node_id']]['generation']['references'][0]['resource'] = resource
                check = executor.inspect('BATTLE')
                self.assertFalse(check['ok'])
                self.assertTrue(any(p.startswith('reference:0:') for p in check['problems']))

    def test_missing_embedded_resource_rejects_ambiguous_sources(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.nodes[TARGET['node_id']]['generation']['references'][0].pop('resource')
        source = cli.nodes[nid('HERO')]
        original = deepcopy(source['resources'][0])
        for resources in [[original, dict(original, resourceId=uid('new-selection'))],
                          [original, deepcopy(original)], []]:
            with self.subTest(resources=resources):
                source['resources'] = resources
                check = executor.inspect('BATTLE')
                self.assertFalse(check['ok'])
                self.assertIn('reference:0:selected_resource_unverified', check['problems'])

    def test_missing_embedded_resource_rejects_missing_wrong_or_unready_source(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.nodes[TARGET['node_id']]['generation']['references'][0].pop('resource')
        original = deepcopy(cli.nodes[nid('HERO')])
        variants = [None, dict(original, status='running'), dict(original, type='video'),
                    dict(original, nodeId=nid('wrong-node')),
                    dict(original, resources=[dict(original['resources'][0], resourceId=uid('wrong'))]),
                    dict(original, resources=[dict(original['resources'][0], status='running')]),
                    dict(original, resources=[dict(original['resources'][0], type='video')])]
        for source in variants:
            with self.subTest(source=source):
                if source is None:
                    cli.nodes.pop(nid('HERO'), None)
                else:
                    cli.nodes[nid('HERO')] = source
                check = executor.inspect('BATTLE')
                self.assertFalse(check['ok'])
                self.assertIn('reference:0:selected_resource_unverified', check['problems'])

    def test_resource_kind_requires_explicit_resource_even_with_lookalike_node(self):
        asset = self.registry['assets']['HERO']
        asset['remote'].update(kind='resource', id=uid('HERO'))
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.nodes[TARGET['node_id']]['generation']['references'][0].pop('resource')
        cli.nodes[uid('HERO')] = {'nodeId': uid('HERO'), 'type': 'image', 'status': 'success',
            'resources': [{'resourceId': uid('HERO'), 'type': 'image', 'status': 'success'}]}
        check = executor.inspect('BATTLE')
        self.assertFalse(check['ok'])
        self.assertIn('reference:0:selected_resource_unverified', check['problems'])

    def test_element_main_auxiliary_voice_use_same_unique_source_rule(self):
        self.add_element(); executor, cli = self.executor(); executor.prepare('BATTLE')
        bindings = cli.nodes[nid('MARKO')]['subjectBindings']
        for ref in [bindings['main'], *bindings['auxiliaries'], bindings['voice']]:
            ref.pop('resource')
        self.assertTrue(executor.inspect('BATTLE')['ok'])
        for aid, label in [('HERO', 'main'), ('STYLE', 'aux:0'), ('VOICE', 'voice')]:
            with self.subTest(aid=aid):
                source = cli.nodes[nid(aid)]
                original = deepcopy(source['resources'])
                source['resources'].append(dict(source['resources'][0], resourceId=uid('other-' + aid)))
                check = executor.inspect('BATTLE')
                self.assertFalse(check['ok'])
                self.assertIn('element:MARKO:' + label + ':selected_resource_unverified', check['problems'])
                source['resources'] = original

    def test_new_upload_uncovered_by_old_scope_is_blocked_before_write(self):
        self.registry['assets']['HERO']['remote'] = None
        approval = self.approval(); approval['operations']['uploads'] = {}
        cli = FakeCLI(self.registry)
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli, approval)
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'authorization_delta')
        self.assertFalse(any(c[:2] in [['node', 'create'], ['node', 'edit'], ['resource', 'upload']]
                             for c in cli.calls))

    def test_authorized_element_edit_replaces_all_bindings(self):
        self.add_element(); executor, cli = self.executor()
        cli.nodes[nid('MARKO')]['subjectBindings']['auxiliaries'][0]['resource']['resourceId'] = uid('wrong')
        executor.prepare('BATTLE')
        self.assertTrue(any(c[:3] == ['node', 'edit', 'element'] for c in cli.calls))
        self.assertTrue(executor.inspect('BATTLE')['ok'])

    def test_element_edit_requires_exact_grant(self):
        self.add_element(); executor, cli = self.executor()
        executor.approval['operations']['elements'] = {}
        cli.nodes[nid('MARKO')]['subjectBindings']['auxiliaries'][0]['resource']['resourceId'] = uid('wrong')
        with self.assertRaises(rp.PipelineError): executor.prepare('BATTLE')
        self.assertFalse(any(c[:2] in [['node', 'edit'], ['node', 'create']] for c in cli.calls))

    def test_readback_rejects_reference_order_selection_and_edges(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        original = deepcopy(cli.nodes[TARGET['node_id']])
        changes = [lambda n: n['generation']['references'].reverse(),
                   lambda n: n['generation']['references'][0]['resource'].update(resourceId=uid('other')),
                   lambda n: n['upstreamNodeIds'].clear(),
                   lambda n: n['generation'].update(prompt='unbound text'),
                   lambda n: n['generation'].update(writebackBlockers=[{'code': 'unavailable'}])]
        for change in changes:
            cli.nodes[TARGET['node_id']] = deepcopy(original)
            change(cli.nodes[TARGET['node_id']])
            self.assertFalse(executor.inspect('BATTLE')['ok'])

    def test_imported_content_change_cannot_follow_old_cloud_source(self):
        self.registry['assets']['HERO']['remote'] = None
        executor, cli = self.executor(); executor.prepare('BATTLE')
        executor.registry['assets']['HERO']['review']['status'] = 'changed_identity'
        with self.assertRaises(rp.PipelineError) as error: executor.inspect('BATTLE')
        self.assertEqual(error.exception.code, 'imported_asset_input_changed')

    def test_authorized_upload_and_element_creation(self):
        self.add_element()
        for asset in self.registry['assets'].values(): asset['remote'] = None
        executor, cli = self.executor()
        self.assertTrue(executor.prepare('BATTLE')['ok'])
        self.assertEqual(sum(c[:2] == ['resource', 'upload'] for c in cli.calls), 4)
        self.assertTrue(executor.inspect('BATTLE')['ok'])

    def test_existing_selected_rebind_is_not_covered_by_same_semantic_grant(self):
        executor, cli = self.executor(); before = self.compile()
        executor.registry['assets']['HERO']['remote']['selected_resource_id'] = uid('rebound')
        changed = rp.compile_segment(executor.registry, executor.plan, 'BATTLE', self.root)
        self.assertEqual(before['semantic_hash'], changed['semantic_hash'])
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'authorization_delta')
        self.assertTrue(any(d['code'] == 'uncovered_source_binding' for d in error.exception.details['delta']))
        self.assertFalse(any(c[:2] == ['node', 'confirm'] for c in cli.calls))

    def test_existing_selected_rebind_also_blocks_unapproved_draft_write(self):
        executor, cli = self.executor()
        selected = uid('rebound')
        executor.registry['assets']['HERO']['remote']['selected_resource_id'] = selected
        cli.nodes[nid('HERO')]['resources'][0]['resourceId'] = selected
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'authorization_delta')
        self.assertFalse(any(c[:2] in [['node', 'create'], ['node', 'edit']] for c in cli.calls))

    def test_existing_element_closure_selected_change_requires_binding_approval(self):
        self.add_element(); executor, cli = self.executor()
        executor.registry['assets']['VOICE']['remote']['selected_resource_id'] = uid('newvoice')
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        uncovered = {d.get('id') for d in error.exception.details['delta']}
        self.assertIn('VOICE', uncovered); self.assertIn('MARKO', uncovered)
        self.assertFalse(any(c[:2] == ['node', 'confirm'] for c in cli.calls))

    def test_new_upload_and_element_receipts_preserve_approved_run(self):
        self.add_element()
        for asset in self.registry['assets'].values(): asset['remote'] = None
        executor, cli = self.executor()
        self.assertEqual(executor.approval['operations']['runs']['BATTLE']['source_bindings'], {})
        executor.prepare('BATTLE')
        result = executor.run('BATTLE')
        self.assertEqual(result['status'], 'submitted')
        self.assertEqual(sum(c[:2] == ['resource', 'download'] for c in cli.calls), 4)

    def test_verified_boolean_in_journal_does_not_autoapprove_existing_binding(self):
        executor, cli = self.executor()
        executor.approval['operations']['runs']['BATTLE']['source_bindings'].pop('HERO')
        compiled = self.compile(); asset = self.registry['assets']['HERO']
        with executor.transaction():
            executor.state['assets']['HERO'] = {'status': 'verified', 'remote': asset['remote'],
                'semantic_hash': compiled['dependency_fingerprints']['HERO']['semantic_hash']}
            executor.persist()
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'authorization_delta')
        self.assertFalse(any(c[:2] == ['node', 'confirm'] for c in cli.calls))

    def test_new_upload_downloaded_bytes_must_match_approved_file(self):
        self.registry['assets']['HERO']['remote'] = None
        executor, cli = self.executor(); executor.prepare('BATTLE')
        state = rp.read_json(self.state)
        rid = state['assets']['HERO']['resource_id']
        cli.blobs[rid] = b'other face'
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'uploaded_source_content_mismatch')
        self.assertFalse(any(c[:2] == ['node', 'confirm'] for c in cli.calls))

    def test_download_receipt_must_match_actual_file_even_when_original_bytes_match(self):
        original = self.root / 'approved.bin'; original.write_bytes(b'approved bytes')
        source = {'type': 'image', 'bytes': original.stat().st_size, 'sha256': rp.file_sha(original)}
        for receipt in [{'size': source['bytes'] + 1, 'sha256': source['sha256']},
                        {'size': source['bytes'], 'sha256': '0' * 64},
                        {'sizeBytes': source['bytes'], 'sha256': source['sha256']}]:
            with self.subTest(receipt=receipt), self.assertRaises(rp.PipelineError) as error:
                rp.verify_downloaded_source(original, original, source, receipt)
            self.assertEqual(error.exception.code, 'uploaded_source_download_receipt_mismatch')
        with patch.dict(sys.modules, {'PIL': None}):
            evidence = rp.verify_downloaded_source(original, original, source,
                {'size': source['bytes'], 'sha256': source['sha256']})
        self.assertEqual(evidence['method'], 'exact_file_identity')

    def _png_pair(self):
        from PIL import Image
        original, remote = self.root / 'approved.png', self.root / 'downloaded.png'
        image = Image.new('RGB', (18, 12), (17, 64, 121))
        image.putpixel((4, 5), (2, 3, 4))
        image.save(original, compress_level=0)
        image.save(remote, compress_level=9)
        self.assertNotEqual(rp.file_sha(original), rp.file_sha(remote))
        source = {'type': 'image', 'path': original.name, 'bytes': original.stat().st_size,
                  'sha256': rp.file_sha(original)}
        return image, original, remote, source

    def _verify_png_pair(self, original, remote, source):
        return rp.verify_downloaded_source(original, remote, source,
            {'size': remote.stat().st_size, 'sha256': rp.file_sha(remote)})

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for strict PNG pixel tests')
    def test_lossless_png_reencoding_passes_with_exact_pixel_audit(self):
        image, original, remote, source = self._png_pair()
        evidence = self._verify_png_pair(original, remote, source)
        self.assertEqual(evidence['method'], 'exact_pixel_identity')
        self.assertEqual(evidence['dimensions'], [18, 12])
        self.assertEqual(evidence['rgba_sha256'], hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest())
        self.assertEqual(evidence['original_sha256'], source['sha256'])
        self.assertEqual(evidence['download_sha256'], rp.file_sha(remote))
        self.assertEqual(evidence['original_bytes'], original.stat().st_size)
        self.assertEqual(evidence['download_bytes'], remote.stat().st_size)
        self.assertTrue(evidence['metadata_exact'])
        # 模拟实际上传后的无损重编码；批准仍冻结原始文件SHA，不改授权或plan。
        asset = self.registry['assets']['HERO']
        asset.update(path=original.name, bytes=source['bytes'], sha256=source['sha256'], remote=None)
        executor, cli = self.executor(); executor.prepare('BATTLE')
        state = rp.read_json(self.state); rid = state['assets']['HERO']['resource_id']
        cli.blobs[rid] = remote.read_bytes()
        self.assertEqual(executor.run('BATTLE')['status'], 'submitted')
        saved = rp.read_json(self.state)['assets']['HERO']['source_content_verification']
        self.assertEqual(saved['method'], 'exact_pixel_identity')
        self.assertEqual(saved['original_sha256'], asset['sha256'])
        self.assertEqual(saved['resource_id'], rid)
        self.assertEqual(executor.approval['operations']['uploads']['HERO'], source['sha256'])

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for strict PNG pixel tests')
    def test_png_reencoding_rejects_single_pixel_change(self):
        image, original, remote, source = self._png_pair()
        image.putpixel((0, 0), (18, 64, 121)); image.save(remote, compress_level=9)
        with self.assertRaises(rp.PipelineError) as error:
            self._verify_png_pair(original, remote, source)
        self.assertEqual(error.exception.code, 'uploaded_source_content_mismatch')

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for strict PNG pixel tests')
    def test_png_reencoding_rejects_icc_orientation_and_animation_changes(self):
        from PIL import Image
        image, original, remote, source = self._png_pair()
        exif = Image.Exif(); exif[274] = 3
        second = image.copy(); second.putpixel((0, 0), (0, 0, 0))
        variants = [{'icc_profile': b'changed ICC profile'}, {'exif': exif},
                    {'save_all': True, 'append_images': [second], 'duration': 100, 'loop': 0}]
        for options in variants:
            with self.subTest(options=list(options)):
                image.save(remote, format='PNG', compress_level=9, **options)
                with self.assertRaises(rp.PipelineError) as error:
                    self._verify_png_pair(original, remote, source)
                self.assertEqual(error.exception.code, 'uploaded_source_content_mismatch')

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for strict PNG pixel tests')
    def test_png_server_removed_cabx_is_audited_but_other_unknown_chunks_still_rejected(self):
        _, original, remote, source = self._png_pair()
        clean = original.read_bytes()
        def add_chunk(kind, payload):
            chunk = len(payload).to_bytes(4, 'big') + kind + payload
            chunk += (zlib.crc32(kind + payload) & 0xffffffff).to_bytes(4, 'big')
            original.write_bytes(clean[:33] + chunk + clean[33:])
            source.update(bytes=original.stat().st_size, sha256=rp.file_sha(original))
        payload = b'original provenance retained locally'
        add_chunk(b'caBX', payload)
        evidence = self._verify_png_pair(original, remote, source)
        self.assertEqual(evidence['method'], 'exact_pixel_identity')
        self.assertEqual(evidence['server_removed_chunks'], ['caBX'])
        self.assertFalse(evidence['metadata_exact'])
        self.assertEqual(evidence['original_metadata']['caBX'],
                         [{'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}])
        self.assertEqual(evidence['download_metadata']['caBX'], [])
        add_chunk(b'vpAg', b'unknown metadata must not be ignored')
        with self.assertRaises(rp.PipelineError) as error:
            self._verify_png_pair(original, remote, source)
        self.assertEqual(error.exception.code, 'uploaded_source_content_mismatch')

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow is required for strict PNG pixel tests')
    def test_png_pixel_fallback_rejects_palette_nonpng_and_missing_pillow(self):
        image, original, remote, source = self._png_pair()
        for mode, format_ in [('P', 'PNG'), ('RGB', 'BMP')]:
            with self.subTest(mode=mode, format=format_):
                image.convert(mode).save(remote, format=format_)
                with self.assertRaises(rp.PipelineError) as error:
                    self._verify_png_pair(original, remote, source)
                self.assertEqual(error.exception.code, 'uploaded_source_content_mismatch')
        image.save(remote, format='PNG', compress_level=9)
        with patch.dict(sys.modules, {'PIL': None}), self.assertRaises(rp.PipelineError) as error:
            self._verify_png_pair(original, remote, source)
        self.assertEqual(error.exception.code, 'exact_png_verification_requires_pillow')

    def test_quote_and_run_once_reserves_before_unknown(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.timeout_run = True
        with self.assertRaises(rp.UnknownOutcome): executor.run('BATTLE')
        state = rp.read_json(self.state)
        self.assertEqual(state['run_calls'], 1)
        self.assertEqual(state['reserved_credits'], 90)
        self.assertEqual(state['segments']['BATTLE']['status'], 'unknown')
        self.assertNotIn(cli.token, self.state.read_text())
        with self.assertRaises(rp.PipelineError): executor.run('BATTLE')
        count = sum(c[:2] == ['node', 'run'] for c in cli.calls)
        result = executor.recover('BATTLE')
        self.assertFalse(result['automatic_resubmit'])
        self.assertEqual(sum(c[:2] == ['node', 'run'] for c in cli.calls), count)
        self.assertEqual(cli.calls[-1][2], TARGET['submit_id'])

    def test_quote_drift_and_credit_limits(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.bad_quote = True
        with self.assertRaises(rp.PipelineError): executor.run('BATTLE')
        self.assertFalse(any(c[:2] == ['node', 'confirm'] for c in cli.calls))
        cli.bad_quote = False
        executor.approval['max_total_credits'] = 80
        # approval不可静默修改，先得到明确迁移拒绝也满足fail closed。
        with self.assertRaises(rp.PipelineError): executor.run('BATTLE')

    def test_post_confirm_mutation_stops_without_token_logging(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        cli.change_after_confirm = True
        with self.assertRaises(rp.UnknownOutcome): executor.run('BATTLE')
        self.assertFalse(any(c[:2] == ['node', 'run'] for c in cli.calls))
        self.assertNotIn(cli.token, self.state.read_text())
        with self.assertRaises(rp.PipelineError): executor.run('BATTLE')

    def test_save_unknown_does_not_automatically_repeat(self):
        executor, cli = self.executor(); cli.timeout_save = True
        with self.assertRaises(rp.UnknownOutcome): executor.prepare('BATTLE')
        writes = sum(c[:2] == ['node', 'create'] for c in cli.calls)
        with self.assertRaises(rp.PipelineError): executor.prepare('BATTLE')
        self.assertEqual(sum(c[:2] == ['node', 'create'] for c in cli.calls), writes)

    def test_download_new_path_only(self):
        executor, cli = self.executor(); executor.prepare('BATTLE'); executor.run('BATTLE'); executor.recover('BATTLE')
        result = executor.download('BATTLE', 'media/take01.mp4')
        self.assertEqual(result['status'], 'downloaded_pending_review')
        with self.assertRaises(rp.PipelineError): executor.download('BATTLE', 'media/take01.mp4')

    def test_official_cli_no_shell_and_sanitizes_errors(self):
        calls = []
        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 20, json.dumps({'ok': False, 'error': {
                'code': 'SECRET_CREDIT_TOKEN', 'message': 'https://host/?token=SECRET',
                'providerPayload': {'secret': 'DO_NOT_PRINT'}}}), 'SECRET STDERR')
        cli = rp.OfficialCLI('/official/dreamina-canvas', runner)
        with self.assertRaises(rp.PipelineError) as error: cli.call(['node', 'show', '--node-id', 'node_a'])
        self.assertNotIn('SECRET', str(error.exception.details))
        self.assertIsInstance(calls[0][0], list)
        self.assertNotIn('shell', calls[0][1])
        with self.assertRaises(rp.PipelineError): cli.call(['node', 'run', '--yes'])

    def test_official_cli_error_envelope_in_stderr(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 20, 'diagnostic without JSON', json.dumps({
                'ok': False, 'error': {'code': 'cli.operation_submission_absent',
                                       'message': 'https://host/?token=DO_NOT_PRINT'}}))
        cli = rp.OfficialCLI('/official/dreamina-canvas', runner)
        with self.assertRaises(rp.PipelineError) as error:
            cli.call(['operation', 'status', uid('absent'), '--project-id', PROJECT])
        self.assertEqual(error.exception.details['service_code'], 'cli.operation_submission_absent')
        self.assertNotIn('DO_NOT_PRINT', str(error.exception.details))

    def test_official_cli_stdout_envelope_has_priority(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, 'prefix {invalid}\n' + json.dumps({'ok': True, 'data': {'isVip': True}}),
                                               json.dumps({'ok': False, 'error': {'code': 'cli.validation_failed'}}))
        cli = rp.OfficialCLI('/official/dreamina-canvas', runner)
        self.assertEqual(cli.call(['auth', 'account']), {'isVip': True})

    def test_official_cli_collects_only_safe_top_level_request_ids(self):
        responses = [
            (0, {'ok': True, 'data': {'isVip': True, 'requestId': 'DO_NOT_COLLECT_NESTED'},
                 'meta': {'requestId': '20261017ABC123', 'providerPayload': 'DO_NOT_PERSIST'}}, False),
            (20, {'ok': False, 'error': {'code': 'cli.validation_failed',
                  'message': 'https://host/?token=DO_NOT_PERSIST'},
                  'meta': {'requestId': 'request-failed-456', 'token': 'DO_NOT_PERSIST'}}, True),
            (0, {'ok': True, 'data': {}, 'meta': {'requestId': 'https://host/?token=DO_NOT_PERSIST'}}, False)]
        def runner(argv, **kwargs):
            code, envelope, stderr = responses.pop(0)
            payload = json.dumps(envelope)
            return subprocess.CompletedProcess(argv, code, '' if stderr else payload, payload if stderr else '')
        cli = rp.OfficialCLI('/official/dreamina-canvas', runner)
        cli.call(['auth', 'account'])
        with self.assertRaises(rp.PipelineError): cli.call(['auth', 'account'])
        cli.call(['auth', 'account'])
        self.assertEqual(cli.request_ids, ['20261017ABC123', 'request-failed-456'])
        self.assertNotIn('DO_NOT_', json.dumps(cli.request_ids))

    def test_request_ids_survive_persist_new_session_and_failed_read_only_call(self):
        executor, _ = self.executor()
        with executor.transaction():
            executor.state['cli_request_ids'] = ['earlier-request']
            executor.persist()  # FakeCLI 没有 request_ids 属性也可工作。
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 20, '', json.dumps({'ok': False,
                'error': {'code': 'cli.validation_failed', 'providerPayload': 'SECRET_PROVIDER'},
                'meta': {'requestId': 'failed-inspect-request', 'signedUrl': 'https://host/?token=SECRET_TOKEN'}}))
        cli = rp.OfficialCLI('/official/dreamina-canvas', runner)
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli)
        with self.assertRaises(rp.PipelineError): executor.inspect('BATTLE')
        persisted = rp.read_json(self.state)
        self.assertEqual(persisted['cli_request_ids'], ['earlier-request', 'failed-inspect-request'])
        self.assertNotIn('SECRET', self.state.read_text())
        executor, _ = self.executor()
        with executor.transaction(): executor.persist()
        self.assertEqual(rp.read_json(self.state)['cli_request_ids'], persisted['cli_request_ids'])

    def test_optimized_python_keeps_gates(self):
        script = '''import importlib.util,sys
s=importlib.util.spec_from_file_location("rp",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
try:m.require(False,"authorization_denied")
except m.PipelineError as e: print(e.code);sys.exit(0)
sys.exit(9)
'''
        process = subprocess.run([sys.executable, '-O', '-c', script, str(MODULE)], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout.strip(), 'authorization_denied')

    def test_explicit_retirement_denial_blocks_compile_and_mutation_without_cli(self):
        for status in ['superseded_for_current_creative_plan', 'retired', 'execution_rejected']:
            with self.subTest(status=status):
                self.plan['status'] = status
                self.assertFalse(self.compile()['executable'])
                executor, cli = self.executor()
                for action in [executor.prepare, executor.run]:
                    with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
                    self.assertEqual(error.exception.code, 'execution_retired_or_denied')
                self.assertEqual(cli.calls, [])
        self.plan.pop('status')
        self.plan['segments']['BATTLE']['status'] = 'actual_rejected_P0'
        self.assertFalse(self.compile()['executable'])
        self.plan['segments']['BATTLE'].pop('status')
        self.plan['execution_allowed'] = False
        self.assertFalse(self.compile()['executable'])
        self.plan.pop('execution_allowed')
        self.plan['paid_ready'] = False
        self.assertTrue(self.compile()['executable'])  # 不把旧ready字段当批准或停线政策。

    def test_work_policy_blocks_mutation_but_allows_historical_read_only(self):
        executor, cli = self.executor(); executor.prepare('BATTLE'); executor.run('BATTLE')
        path = self.root / 'production/execution-policy.json'
        rp.save_json(path, {'schema_version': 1, 'work_id': 'test', 'cloud_mutations_allowed': False,
                            'historical_read_only_allowed': True})
        self.assertFalse(self.compile()['executable'])
        before = len(cli.calls)
        for action in [executor.prepare, executor.run]:
            with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
            self.assertEqual(error.exception.code, 'execution_retired_or_denied')
        self.assertEqual(len(cli.calls), before)
        executor.inspect('BATTLE'); executor.quote('BATTLE')
        executor.recover('BATTLE'); executor.download('BATTLE', 'read-only-original.mp4')
        self.assertTrue((self.root / 'read-only-original.mp4').is_file())
        self.assertEqual(rp.read_json(self.state)['run_calls'], 1)
        self.assertFalse(any(c[:2] in [['node', 'create'], ['node', 'edit'], ['node', 'confirm'],
                                      ['node', 'run'], ['resource', 'upload']] for c in cli.calls[before:]))

    def test_retired_plan_remains_inspectable_recoverable_and_downloadable(self):
        executor, cli = self.executor(); executor.prepare('BATTLE'); executor.run('BATTLE')
        self.plan['status'] = 'retired_historical_input'
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli)
        executor.inspect('BATTLE'); executor.recover('BATTLE')
        executor.download('BATTLE', 'retired-output.mp4')
        self.assertTrue((self.root / 'retired-output.mp4').is_file())

    def test_same_approval_cannot_reset_once_by_fresh_journal(self):
        self.plan['segments']['BATTLE']['remote'] = None
        approval = self.approval(); cli = FakeCLI(self.registry)
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli, approval)
        executor.prepare('BATTLE'); executor.run('BATTLE')
        with self.assertRaises(rp.PipelineError) as error: executor.run('BATTLE')
        self.assertEqual(error.exception.code, 'once_limit_or_unknown')
        before = len(cli.calls)
        second = rp.Executor(self.registry, self.plan, self.root, self.root / 'new-state.json', cli, approval)
        for action in [second.prepare, second.run]:
            with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
            self.assertEqual(error.exception.code, 'approval_bound_to_other_journal')
        self.assertEqual(len(cli.calls), before)
        self.assertEqual(sum(c[:2] == ['node', 'run'] for c in cli.calls), 1)
        self.assertEqual(rp.read_json(self.state)['reserved_credits'], 90)

    def test_deleted_journal_read_only_recreation_cannot_restore_budget(self):
        for read_action in ['inspect', 'recover']:
            with self.subTest(read_action=read_action):
                # 每轮使用独立工作根；不删除批准权威用量。
                self.doCleanups(); self.setUp()
                executor, cli = self.executor(); executor.prepare('BATTLE'); executor.run('BATTLE')
                self.state.unlink()
                try: getattr(executor, read_action)('BATTLE')
                except rp.PipelineError as error:
                    self.assertEqual(error.code, 'segment_journal_missing')
                self.assertEqual(rp.read_json(self.state)['run_calls'], 0)
                before = len(cli.calls)
                for action in [executor.prepare, executor.run]:
                    with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
                    self.assertEqual(error.exception.code, 'approval_journal_reset_or_missing')
                self.assertEqual(len(cli.calls), before)

    def test_same_path_old_snapshot_cannot_roll_back_used_counts(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        old = rp.read_json(self.state)
        executor.run('BATTLE'); rp.save_json(self.state, old)
        before = len(cli.calls)
        for action in [executor.prepare, executor.run]:
            with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
            self.assertEqual(error.exception.code, 'approval_usage_rollback')
        self.assertEqual(len(cli.calls), before)

    def test_missing_authority_cannot_rebind_nonce_or_reuse_changed_approval(self):
        executor, cli = self.executor(); executor.prepare('BATTLE')
        changed = deepcopy(executor.approval)
        copied = self.root / 'copied-human-approval.json'
        copied.write_bytes((self.root / changed['evidence']['path']).read_bytes())
        changed['evidence']['path'] = copied.name
        another = rp.Executor(self.registry, self.plan, self.root, self.root / 'other.json', cli, changed)
        with self.assertRaises(rp.PipelineError) as error: another.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'approval_authority_contract_changed')
        for path in self.authority_dir.glob('*.json'): path.unlink()
        before = len(cli.calls)
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'approval_authority_missing')
        self.assertEqual(len(cli.calls), before)

    def test_two_processes_cannot_bind_same_approval_to_different_journals(self):
        self.plan['segments']['BATTLE']['remote'] = None
        approval = self.approval()
        context = multiprocessing.get_context('fork')
        start, results = context.Event(), context.Queue()
        def worker(filename):
            cli = FakeCLI(self.registry)
            executor = rp.Executor(self.registry, self.plan, self.root, self.root / filename, cli, approval)
            start.wait(5)
            try:
                executor.prepare('BATTLE'); result = 'prepared'
            except rp.PipelineError as error: result = error.code
            results.put((result, len(cli.calls)))
        processes = [context.Process(target=worker, args=(name,)) for name in ['one.json', 'two.json']]
        try:
            for process in processes: process.start()
            start.set()
            observed = [results.get(timeout=10) for _ in processes]
            self.assertEqual(sorted(result for result, _ in observed),
                             ['approval_bound_to_other_journal', 'prepared'])
            self.assertEqual([calls for result, calls in observed if result != 'prepared'], [0])
        finally:
            for process in processes:
                process.join(5)
                if process.is_alive(): process.terminate(); process.join(5)

    def test_copied_work_root_cannot_reuse_same_project_and_human_approval(self):
        self.plan['segments']['BATTLE']['remote'] = None
        approval = self.approval(); cli = FakeCLI(self.registry)
        with tempfile.TemporaryDirectory() as directory:
            second_root = Path(directory)
            for asset in self.registry['assets'].values():
                shutil.copyfile(self.root / asset['path'], second_root / asset['path'])
            shutil.copyfile(self.root / approval['evidence']['path'], second_root / approval['evidence']['path'])
            first = rp.Executor(self.registry, self.plan, self.root, self.state, cli, approval)
            first.prepare('BATTLE'); first.run('BATTLE')
            before = len(cli.calls)
            second = rp.Executor(self.registry, self.plan, second_root,
                                 second_root / 'state.json', cli, approval)
            for action in [second.prepare, second.run]:
                with self.assertRaises(rp.PipelineError) as error: action('BATTLE')
                self.assertEqual(error.exception.code, 'approval_bound_to_other_work_root')
            self.assertEqual(len(cli.calls), before)
            self.assertEqual(sum(c[:2] == ['node', 'run'] for c in cli.calls), 1)
            self.assertEqual(len(list(self.authority_dir.glob('*.json'))), 1)

    def test_other_work_root_cannot_borrow_original_journal_to_bypass_stop_policy(self):
        approval = self.approval(); cli = FakeCLI(self.registry)
        first = rp.Executor(self.registry, self.plan, self.root, self.state, cli, approval)
        first.prepare('BATTLE')
        rp.save_json(self.root / 'production/execution-policy.json',
                     {'schema_version': 1, 'work_id': 'test', 'cloud_mutations_allowed': False})
        with self.assertRaises(rp.PipelineError) as error: first.run('BATTLE')
        self.assertEqual(error.exception.code, 'execution_retired_or_denied')
        with tempfile.TemporaryDirectory() as directory:
            other_root = Path(directory)
            for asset in self.registry['assets'].values():
                shutil.copyfile(self.root / asset['path'], other_root / asset['path'])
            shutil.copyfile(self.root / approval['evidence']['path'], other_root / approval['evidence']['path'])
            before = len(cli.calls)
            borrowed = rp.Executor(self.registry, self.plan, other_root, self.state, cli, approval)
            with self.assertRaises(rp.PipelineError) as error: borrowed.run('BATTLE')
            self.assertEqual(error.exception.code, 'approval_bound_to_other_work_root')
            self.assertEqual(len(cli.calls), before)
            self.assertFalse(any(c[:2] == ['node', 'run'] for c in cli.calls))

    def test_journal_symlink_uses_canonical_lock_and_persistence_path(self):
        executor, cli = self.executor()
        with executor.transaction(): pass
        alias = self.root / 'state-alias.json'; alias.symlink_to(self.state)
        canonical = rp.Executor(self.registry, self.plan, self.root, alias, cli, executor.approval)
        canonical.prepare('BATTLE'); canonical.run('BATTLE')
        self.assertTrue(alias.is_symlink())
        self.assertEqual(canonical.state_path, self.state.resolve())
        self.assertEqual(rp.read_json(self.state)['run_calls'], 1)
        self.assertEqual(rp.read_json(alias)['authority_nonce'], rp.read_json(self.state)['authority_nonce'])

    def test_same_nonce_snapshot_cannot_lose_unknown_upload_identity(self):
        self.registry['assets']['HERO']['remote'] = None
        state_path = self.state
        class UploadThenUnknown(FakeCLI):
            snapshot = None
            def call(self, args):
                if args[:2] == ['node', 'show'] and self.snapshot is None:
                    self.snapshot = rp.read_json(state_path)
                result = super().call(args)
                if args[:2] == ['resource', 'upload']:
                    raise rp.UnknownOutcome('fake_uploaded_then_timed_out')
                return result
        cli = UploadThenUnknown(self.registry)
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli, self.approval())
        with self.assertRaises(rp.UnknownOutcome): executor.prepare('BATTLE')
        unknown = rp.read_json(self.state)
        self.assertEqual(unknown['assets']['HERO']['status'], 'unknown')
        self.assertEqual(cli.snapshot['authority_nonce'], unknown['authority_nonce'])
        rp.save_json(self.state, cli.snapshot)
        before = len(cli.calls)
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'approval_asset_rollback')
        self.assertEqual(len(cli.calls), before)
        self.assertEqual(sum(c[:2] == ['resource', 'upload'] for c in cli.calls), 1)

    def test_unknown_import_recovers_same_identity_then_prepare_and_rejects_rollback(self):
        self.registry['assets']['HERO']['remote'] = None
        class ImportThenUnknown(FakeCLI):
            failed = False
            def call(self, args):
                result = super().call(args)
                if args[:3] == ['node', 'create', 'image'] and not self.failed:
                    self.failed = True
                    raise rp.UnknownOutcome('fake_imported_then_timed_out')
                return result
        cli = ImportThenUnknown(self.registry)
        executor = rp.Executor(self.registry, self.plan, self.root, self.state, cli, self.approval())
        with self.assertRaises(rp.UnknownOutcome): executor.prepare('BATTLE')
        unknown = rp.read_json(self.state)
        original_ids = {key: value for key, value in unknown['assets']['HERO'].items()
                        if key in rp.ASSET_IDENTITY_FIELDS}
        self.assertEqual(executor.recover(asset_id='HERO')['status'], 'asset_recovered_read_only')
        executor.prepare('BATTLE')
        actual = rp.read_json(self.state)['assets']['HERO']
        self.assertEqual(actual['status'], 'verified')
        self.assertTrue(all(actual[key] == value for key, value in original_ids.items()))
        self.assertEqual(sum(c[:2] == ['resource', 'upload'] for c in cli.calls), 1)
        rolled_back = rp.read_json(self.state)
        rolled_back['assets']['HERO'] = unknown['assets']['HERO']
        rp.save_json(self.state, rolled_back)
        before = len(cli.calls)
        with self.assertRaises(rp.PipelineError) as error: executor.prepare('BATTLE')
        self.assertEqual(error.exception.code, 'approval_asset_rollback')
        self.assertEqual(len(cli.calls), before)


if __name__ == '__main__':
    unittest.main()
