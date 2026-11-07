"""Idempotent disconnected configuration refresh. Never changes the live model router."""
import asyncio
import json
import os
import pwd
import shutil
import sys
from pathlib import Path
from reply_routing import companion_owns_wakeup

BASE = Path('/opt/jiangsheng-astrbot')
DATA = BASE / 'runtime/data'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    path.chmod(0o600)
    owner = pwd.getpwnam('hermes')
    os.chown(path, owner.pw_uid, owner.pw_gid)


def configure():
    path = DATA / 'cmd_config.json'
    c = json.loads(path.read_text(encoding='utf-8-sig'))
    route = json.loads(Path('/home/hermes/.hermes/chat-routing.json').read_text())
    router = next(p for p in c['provider_sources'] if p['id'] == 'jiangsheng-router')
    router.update(api_base='http://127.0.0.1:8650/v1', key=[route['localKey']])
    c['platform'] = [dict(id='jiangsheng', type='aiocqhttp', name='江生 QQ', enable=True,
        ws_reverse_host='127.0.0.1', ws_reverse_port=6199, ws_reverse_token='')]
    companion_owns_wakeup(c)
    c['platform_settings'].update(enable_id_white_list=False, ignore_bot_self_message=True, ignore_at_all=True)
    c['provider_settings'].pop('provider_id', None)
    c['provider_settings'].update(default_image_caption_provider_id='jiangsheng-chat', max_quoted_fallback_images=3)
    c['provider_tts_settings'].update(enable=True, provider_id='jiangsheng-voice', dual_output=True, trigger_probability=.02)
    c['provider_stt_settings'].update(enable=True, provider_id='jiangsheng-stt')
    if not any(r['id'] == 'jiangsheng-stt' for r in c['provider']):
        c['provider'].append(dict(id='jiangsheng-stt', type='jiangsheng_cloud_stt', provider_type='speech_to_text', enable=True, model='cloud-gemini-audio'))
    write_json(path, c)
    cp = DATA / 'config/astrbot_plugin_private_companion_config.json'
    companion = json.loads(cp.read_text(encoding='utf-8-sig'))
    companion['performance']['enabled'] = True
    companion['model']['provider_id'] = 'jiangsheng-chat'
    companion['runtime'].update(foreground_slots=2, background_slots=1, retained_tasks=2000)
    companion['voice_reply']['enabled'] = False  # Native AstrBot owns TTS; never double-send.
    companion['multi_host'].update(enabled=True, installation_id='jiangsheng',
        targets=[dict(target_id='private-all', platform_id='jiangsheng', account_id='3899701587', bot_id='bot-3899701587', participant_id='*', __template_key='private_target')],
        group_targets=[dict(target_id='group-all', platform_id='jiangsheng', account_id='3899701587', bot_id='bot-3899701587', group_id='*', __template_key='group_target')],
        personas=[dict(bot_id='bot-3899701587', persona_id='default', role_id='jiangsheng', __template_key='persona_mapping')])
    write_json(cp, companion)
    recorder = dict(enable_commands=False, max_records=100000, retention_days=30,
        save_message_chain=True, save_raw_message=False, cleanup_interval_hours=4,
        save_media_files=True, image_save_mode='thumbnail')
    write_json(DATA / 'config/astrbot_plugin_message_recorder_config.json', recorder)
    # Refresh only the legacy import, leaving native AstrBot/companion memories intact.
    for name in ['qq-memory', 'qq-user-memory']:
        shutil.copytree('/home/hermes/' + name, DATA / 'legacy' / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('*.bak', '*.before*', '*.tmp'))
    owner = pwd.getpwnam('hermes')
    for item in (DATA / 'legacy').rglob('*'):
        os.chown(item, owner.pw_uid, owner.pw_gid)
        if item.is_file():
            item.chmod(0o600)
    print('CONFIGURATION_REFRESHED_ROUTER_UNCHANGED_TTS_2_PERCENT')


if __name__ == '__main__':
    configure()
