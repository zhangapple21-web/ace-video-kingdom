import json
from pathlib import Path

from tools.validate_continuity_bridge import validate_bridge
from tools.validate_director_manifest import validate_manifest
from tools.validate_shot_rhythm import validate_shot_rhythm

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def test_a16_b9_c11_counts():
    checks = _load('assets/checklists/generic_default_layer.v1.json')['checks']
    assert [row['id'] for row in checks] == [f'A{i:02d}' for i in range(1, 33)]
    mines = (ROOT / 'research/REFERENCE_MINES.md').read_text(encoding='utf-8')
    assert '参考层' in mines
    for i in range(1, 10):
        assert f'B{i:02d}' in mines
    items = _load('governance/system_conflict_constraints.v1.json')['items']
    assert [row['id'] for row in items] == [f'C{i:02d}' for i in range(1, 23)]
    assert all(row['status'] == 'DISABLED_SYSTEM_CONFLICT' for row in items)
    assert _load('governance/system_conflict_constraints.v1.json')['mark'] == '系统级冲突，禁用'


def test_scene_and_prop_templates_exist():
    for rel in (
        'assets/templates/scene_asset_package.v1.json',
        'assets/templates/prop_asset_package.v1.json',
        'assets/schema/scene_asset_package.v1.json',
        'assets/schema/prop_asset_package.v1.json',
        'assets/checklists/generic_default_layer.v1.json',
        'governance/system_conflict_constraints.v1.json',
    ):
        assert (ROOT / rel).is_file(), rel
    scene = _load('assets/templates/scene_asset_package.v1.json')
    prop = _load('assets/templates/prop_asset_package.v1.json')
    character = _load('assets/templates/character_asset_package.v1.json')
    for package in (scene, prop, character):
        assert package['reference_image_camera_lock'] is False
        assert 'state_contract' in package
        assert 'material_structure' in package
        assert 'static_asset_rules' in package
        assert package.get('reference_role') == 'identity_not_keyframe'
    assert scene['reference_images_required'] is False
    assert scene.get('origin') == 'dynamic_scene_state_not_image_library'
    assert character['long_term_asset'] is True
    assert 'scene_state' in scene


def test_old_shot_rhythm_not_blocked_without_photography():
    shot = {
        'shot_purpose': '让观众理解迟疑',
        'scale': 'medium',
        'transition_intent': '切入回应',
        'movement': 'static',
        'timing_basis': 'AUDIO_DRIVEN',
        'audio_anchor': 'line-01',
        'script_annotations': {k: '有内容' for k in ('action', 'dialogue', 'emotion', 'subtext', 'motivation', 'atmosphere')},
        'performance_beats': {k: '有内容' for k in ('speaker_hands_body', 'listener_reaction', 'pause_point', 'inner_voice_mouth_state', 'cut_motivation')},
    }
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_incomplete_photography_is_warning_only():
    shot = {
        'shot_purpose': '让观众理解迟疑',
        'scale': 'medium',
        'transition_intent': '切入回应',
        'movement': 'static',
        'timing_basis': 'AUDIO_DRIVEN',
        'audio_anchor': 'line-01',
        'script_annotations': {k: '有内容' for k in ('action', 'dialogue', 'emotion', 'subtext', 'motivation', 'atmosphere')},
        'performance_beats': {k: '有内容' for k in ('speaker_hands_body', 'listener_reaction', 'pause_point', 'inner_voice_mouth_state', 'cut_motivation')},
        'photography': {'focal_length': '35mm'},
    }
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('photography.camera_height' in item for item in result['warnings'])


def test_director_optional_spatial_fields_do_not_warn_when_absent():
    shot = {
        'shot_id': 'S01',
        'creative_constraints': {
            'hard': {key: {'status': 'LOCKED', 'rules': ['test rule']} for key in (
                'identity_reference', 'narrative_order', 'spatial_relationship', 'visibility_and_exclusions', 'performance_and_audio'
            )},
            'flexible': {},
            'deferred': [],
        },
        'role_audit': {
            'schema': 'video_kingdom.oneapi_role_room.v2',
            'status': 'COMPLETED',
            'profile': 'standard',
            'production_submission': 'NOT_PERFORMED',
            'roles': [{'role_id': role_id, 'status': 'COMPLETED'} for role_id in (
                'primary_writer', 'storyboarder', 'contrarian_auditor', 'continuity_editor', 'director_convergence'
            )],
        },
        'story_goal': '建立人物处境',
        'duration_seconds': 6,
        'source_frame': 'assets/S01.png',
        'director_preflight': {
            'spatial_audit': {
                'foreground': '桌沿', 'midground': '人物', 'background': '窗户',
                'camera_start': '胸口高度', 'allowed_content': '人物抬头',
                'forbidden_additions': '新人物', 'subjects_present': True,
            },
            'camera': {'main_motion': '缓慢推近', 'tracking_subject': '人物眼神', 'camera_end': '停在半身'},
            'lighting': {'motivation': '窗光', 'key_source': '左侧窗户', 'direction': '左向右', 'exposure_lock': True, 'white_balance_lock': True},
            'performance': {
                'speaker_action': '说话时手指轻敲桌面',
                'listener_expression': '听到关键句时眉头收紧，再缓慢放松',
                'pause_points': '关键句后停顿一拍',
                'monologue_mouth_state': '无独白时不适用',
                'edit_intent': '保持正反打，反应镜头后再切回说话者',
            },
        },
    }
    result = validate_manifest({'shots': [shot]}, strict=True)
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_world_copied_as_screen_is_warning_only():
    shot = {
        'shot_id': 'S01',
        'story_goal': 'x',
        'duration_seconds': 1,
        'source_frame': 'a.png',
        'director_preflight': {
            'spatial_audit': {
                'foreground': 'a', 'midground': 'b', 'background': 'c',
                'camera_start': 'd', 'allowed_content': 'e', 'forbidden_additions': 'f',
                'subjects_present': True,
                'world_position': '画面左侧',
                'screen_left_right': '画面左侧',
            }
        },
    }
    result = validate_manifest({'shots': [shot]})
    assert result['status'] == 'PASS'
    assert any('world_position copied as screen_left_right' in item for item in result['warnings'])


def test_continuity_asset_register_optional_on_legacy_bridge():
    bridge = {
        'previous_end_frame_state': 'end',
        'next_initial_state': 'start',
        'camera_state': 'static',
        'lighting_state': 'window',
        'tail_frame_state': 'hold',
        'enter_direction': 'hold',
        'exit_direction': 'hold',
    }
    result = validate_bridge(bridge)
    assert result['status'] == 'PASS'
    assert any('scene_state missing' in item for item in result.get('warnings', []))


def test_entry_and_provider_unchanged():
    agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    skill = Path(r'C:/Users/Administrator/.codex/skills/video-kingdom/SKILL.md').read_text(encoding='utf-8')
    for text in (agents, skill):
        assert 'video_kingdom_entry.py' in text
        assert 'agnes-video-2.5-flash' in text
        assert 'gpt-image-2' in text
    entry = ROOT / 'tools' / 'video_kingdom_entry.py'
    assert entry.is_file()
    assert 'camera_motion_level' in skill
    assert 'V2 ≠ 新入口' in skill or 'V2' in skill
    assert 'trim_or_shorten_never_pad' in skill or '无信息垫秒' in skill
    assert '静帧' in skill or '可看变化' in skill
    assert '自然微动作' in skill or '可看变化提交句' in skill
    assert '导演当魂' in skill
    assert '不替你想戏' in skill
    assert '底线壳' in skill
    assert '图生视频' in skill
    assert '只锁脸' not in skill
    assert '分册' in skill
    assert 'Approved State' in skill
    assert (ROOT / 'research/soul_shot_ledger.v1.jsonl').is_file()
    assert (ROOT / 'memory/L3_experience.jsonl').read_text(encoding='utf-8').count('shell_is_gate_soul_is_performance') == 1
    assert 'Scene State' in skill
    assert '长期资产' in skill
    assert '证件照对口型' in skill
    assert 'MCUSTATIC' in skill
    playbook = (ROOT / 'docs/VIDEO_PRODUCTION_WORKFLOW_PLAYBOOK.v1.md').read_text(encoding='utf-8')
    architecture = (ROOT / 'docs/ASSET_WORKFLOW_ARCHITECTURE.v1.md').read_text(encoding='utf-8')
    kernel = json.loads((ROOT / 'governance/short_drama_dispatch_kernel.v1.json').read_text(encoding='utf-8'))
    assert 'Scene State' in playbook
    assert '默认不是图生视频' in playbook
    assert '不因缺少场景参考图阻断开拍' in architecture
    assert kernel['production_integration'] is False
    assert '不是开拍门票' in kernel['capability_boundary']['first_frame_policy']


def test_workflow_audit_accepts_configured_episode_contract_path(tmp_path, monkeypatch):
    from tools import audit_workflow_integrity

    contracts = tmp_path / 'contracts'
    contracts.mkdir()
    monkeypatch.setenv('VIDEO_KINGDOM_EPISODE_CONTRACTS', str(contracts))
    result = audit_workflow_integrity.audit()
    assert result['checked']['episode_contracts'] is True
    assert result['checked']['episode_contracts_path'] == str(contracts)
