"""Run on production to prepare a disconnected AstrBot runtime; never switches QQ."""
import json
import os
import secrets
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


def defaults(schema):
    result = {}
    for key, value in schema.items():
        if 'default' in value:
            result[key] = deepcopy(value['default'])
        elif value.get('type') == 'object':
            result[key] = defaults(value.get('items', {}))
    return result


def main():
    root = Path('/opt/jiangsheng-astrbot')
    run = root / 'runtime'
    (run / 'data/config').mkdir(parents=True, exist_ok=True)
    config = run / 'data/cmd_config.json'
    if config.exists():
        raise RuntimeError('runtime configuration already exists; inspect rather than overwrite')
    sys.path.insert(0, str(root / 'app'))
    from astrbot.core.config.default import DEFAULT_CONFIG
    c = deepcopy(DEFAULT_CONFIG)
    route = json.loads(Path('/home/hermes/.hermes/chat-routing.json').read_text())
    c['dashboard'].update(host='127.0.0.1', port=6185, password=secrets.token_urlsafe(32), jwt_secret=secrets.token_urlsafe(48))
    c['platform'] = []
    c['platform_settings'].update(enable_id_white_list=False, ignore_bot_self_message=True, ignore_at_all=True)
    c['provider_sources'] = [dict(id='jiangsheng-router', provider='openai', type='openai_chat_completion', provider_type='chat_completion', enable=True, key=[route['localKey']], api_base='http://127.0.0.1:8650/v1', timeout=90, proxy='', custom_headers={})]
    c['provider'] = [dict(id='jiangsheng-chat', provider_source_id='jiangsheng-router', model='qq-chat', enable=True, modalities=['text', 'image'], custom_extra_body={})]
    c['agent_runner']['config']['model'].update(provider_id='jiangsheng-chat', request_max_retries=1)
    c['agent_runner']['config']['compression'].update(max_turns=30)
    c['agent_runner']['config']['misc'].update(max_steps=8)
    c['provider_settings'].update(provider_id='jiangsheng-chat', default_image_caption_provider_id='jiangsheng-chat', max_quoted_fallback_images=3)
    c['provider_ltm_settings'].update(group_message_history_enable=True, group_message_history_max_cnt=60)
    config.write_text(json.dumps(c, ensure_ascii=False, indent=2))
    os.chmod(config, 0o600)
    plugins = run / 'data/plugins'
    plugins.mkdir(exist_ok=True)
    for origin, name in [('companion', 'astrbot_plugin_private_companion'), ('recorder', 'astrbot_plugin_message_recorder')]:
        target = plugins / name
        if not target.exists():
            shutil.copytree(root / origin, target, ignore=shutil.ignore_patterns('.git', 'tests', 'tools', 'fixtures', '__pycache__'))
    cc = defaults(json.loads((root / 'companion/_conf_schema.json').read_text()))
    cc['performance']['enabled'] = True
    cc['model']['provider_id'] = 'jiangsheng-chat'
    cc['runtime'].update(foreground_slots=2, background_slots=1, retained_tasks=2000)
    cc['voice_reply']['enabled'] = False
    (run / 'data/config/astrbot_plugin_private_companion_config.json').write_text(json.dumps(cc, ensure_ascii=False, indent=2))
    shutil.copy2('/home/hermes/qq-persona.md', run / 'data/jiangsheng-persona.md')
    for name in ['qq-memory', 'qq-user-memory']:
        target = run / 'data/legacy' / name
        if not target.exists():
            shutil.copytree('/home/hermes/' + name, target, ignore=shutil.ignore_patterns('*.bak', '*.before*'))
    subprocess.run(['chown', '-R', 'hermes:hermes', str(run)], check=True)
    unit = '''[Unit]
Description=Jiangsheng AstrBot social runtime
After=network-online.target qq-chat-router.service
[Service]
User=hermes
Group=hermes
WorkingDirectory=/opt/jiangsheng-astrbot/app
Environment=ASTRBOT_ROOT=/opt/jiangsheng-astrbot/runtime
Environment=HOME=/home/hermes
Environment=PYTHONUNBUFFERED=1
Environment=OPENBLAS_NUM_THREADS=1
Environment=OMP_NUM_THREADS=1
ExecStart=/opt/jiangsheng-astrbot/venv/bin/python -u main.py
Restart=on-failure
RestartSec=10
MemoryHigh=420M
MemoryMax=600M
MemorySwapMax=768M
CPUQuota=80%
TasksMax=96
[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system/jiangsheng-astrbot.service').write_text(unit)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'start', 'jiangsheng-astrbot.service'], check=True)
    print('ASTRBOT_STAGED_NO_QQ_PLATFORM')


if __name__ == '__main__':
    main()
