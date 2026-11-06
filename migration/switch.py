"""Production responder switch. Invoke only after live acceptance and observer adaptation."""

import argparse
import json
import subprocess
import time
from pathlib import Path

OLD = 'qq-hermes-bridge.service'
NEW = 'jiangsheng-astrbot.service'
REQUIRED = ('attribution', 'images', 'quoted_images', 'aliases', 'bursts',
            'fallback', 'restart_persistence', 'speech', 'controller_observation', 'resource_budget')


def rollback(run, connect=None):
    # Never start Hermes if stopping the new responder fails.
    run('stop', NEW)
    run('disable', NEW)
    if connect:
        connect(False)
    run('enable', OLD)
    run('start', OLD)


def cutover(run, healthy, *, acceptance, connect=None):
    if not all(acceptance.get(key) is True for key in REQUIRED):
        raise ValueError('live acceptance is incomplete; keep the old responder')
    try:
        run('stop', OLD)
        if connect:
            connect(True)
        run('start', NEW)
        if not healthy():
            raise RuntimeError('AstrBot failed the post-start health window')
        run('enable', NEW)
        run('disable', OLD)
    except Exception:
        rollback(run, connect)
        raise


def systemctl(action, unit):
    subprocess.run(['systemctl', action, unit], check=True, timeout=90)


def healthy_window():
    def ready():
        try:
            state = json.loads(Path('/opt/jiangsheng-astrbot/runtime/data/jiangsheng-health.json').read_text())
            return (state.get('qqConnected') is True and state.get('companionReady') is True
                    and state.get('acceptance') is False and 0 <= time.time() - state['timestamp'] <= 30)
        except (OSError, ValueError, KeyError, TypeError):
            return False
    for _ in range(24):
        if ready():
            break
        time.sleep(5)
    else:
        return False
    for _ in range(12):
        if subprocess.run(['systemctl', 'is-active', '--quiet', NEW], timeout=10).returncode:
            return False
        if not ready():
            return False
        time.sleep(5)
    return True


def configure_connection(enabled):
    # Old responder has already stopped before this can add a live reverse client.
    path = Path('/home/napcat/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_3899701587.json')
    c = json.loads(path.read_text(encoding='utf-8-sig'))
    backup = Path('/var/backups/jiangsheng-astrbot/napcat-before-cutover.json')
    if enabled and not backup.exists():
        backup.write_bytes(path.read_bytes())
        backup.chmod(0o600)
    clients = c['network'].get('websocketClients', [])
    clients = [row for row in clients if row.get('name') != 'jiangsheng-astrbot']
    if enabled:
        systemctl('stop', NEW)
        subprocess.run(['/opt/jiangsheng-astrbot/venv/bin/python', '/opt/jiangsheng-astrbot/configure.py'], check=True, timeout=60)
        import sys
        sys.path.insert(0, '/home/hermes')
        import importlib.util
        spec = importlib.util.spec_from_file_location('release', '/home/hermes/qq-evolution-release.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        release.sync_astrbot()
        dropin = Path('/etc/systemd/system/jiangsheng-astrbot.service.d')
        dropin.mkdir(exist_ok=True)
        (dropin / 'production.conf').write_text('[Unit]\nConflicts=qq-hermes-bridge.service\n[Service]\nEnvironment=JIANGSHENG_ACCEPTANCE=0\n')
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        clients.append(dict(name='jiangsheng-astrbot', enable=True, url='ws://127.0.0.1:6199/ws/',
            messagePostFormat='array', reportSelfMessage=False, reconnectInterval=3000,
            heartInterval=30000, token='', debug=False))
    c['network']['websocketClients'] = clients
    stat = path.stat()
    temp = path.with_suffix('.migration-tmp')
    temp.write_text(json.dumps(c, ensure_ascii=False, indent=2))
    import os
    os.chown(temp, stat.st_uid, stat.st_gid)
    os.chmod(temp, stat.st_mode & 0o777)
    temp.replace(path)
    Path('/etc/jiangsheng-runtime').write_text('astrbot\n' if enabled else 'hermes\n')
    systemctl('restart', 'napcat-qq.service')


def main():
    import fcntl  # Production is Linux; replay tests also run on Windows.
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['cutover', 'rollback'])
    parser.add_argument('--acceptance', type=Path)
    args = parser.parse_args()
    with open('/run/lock/jiangsheng-responder.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.mode == 'rollback':
            rollback(systemctl, configure_connection)
        else:
            if not args.acceptance:
                parser.error('--acceptance is required')
            cutover(systemctl, healthy_window, acceptance=json.loads(args.acceptance.read_text()), connect=configure_connection)
        print(json.dumps({'operation': args.mode, 'completed': True}), flush=True)


if __name__ == '__main__':
    main()
