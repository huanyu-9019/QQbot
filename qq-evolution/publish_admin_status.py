"""Publish a sanitized dual-server heartbeat for the authenticated admin panel."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from admin_status import build_snapshot
from runtime_support import learning_status, runtime_ready, probe_runtime
import inspect
from collector import redact_text


ROOT = Path(os.environ.get("QQ_EVOLUTION_STATE_DIR", "/home/admin/qq-evolution-state"))
SSH = [
    "/usr/bin/ssh", "-i", "/home/admin/.ssh/qq-evolution-prod",
    "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
    "-o", "UpdateHostKeys=no", "-o", "ConnectTimeout=8",
    "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
    "-o", "ServerAliveCountMax=1", "root@39.105.219.112",
]


PROBE = r'''import json,os,shutil,subprocess,time,urllib.request
def active(unit):
 return subprocess.run(['/usr/bin/systemctl','is-active','--quiet',unit],timeout=5).returncode==0
mem={}
for line in open('/proc/meminfo'):
 k,v=line.split(':',1);mem[k]=int(v.split()[0])
disk=shutil.disk_usage('/')
data={'online':True,'bridge':active('qq-hermes-bridge.service'),'api':active('hermes-qq-api.service'),'napcat':active('napcat-qq.service'),'memoryAvailableMiB':mem['MemAvailable']//1024,'diskFreeGiB':disk.free//(1024**3)}
try:data['router']=json.loads(urllib.request.urlopen('http://127.0.0.1:8650/health',timeout=4).read())
except Exception:data['router']={}
try:
 line=open('/home/hermes/qq-evolution-release.jsonl').read().splitlines()[-1]
 data['latestChange']=json.loads(line)
except Exception:data['latestChange']={}
runtime=probe_runtime()
if runtime.get('runtime')=='astrbot':
 data.update(runtime=runtime['runtime'],bridge=runtime['bridge'],api=runtime['api'],napcat=runtime['napcat'],astrbot=runtime['astrbot'],qqConnected=runtime['qqConnected'],companionReady=runtime['companionReady'],lastSent=runtime['lastSent'],lastIncoming=runtime['lastIncoming'],unanswered=runtime['unanswered'])
print(json.dumps(data,separators=(',',':')))
'''
PROBE = inspect.getsource(learning_status) + '\n' + inspect.getsource(runtime_ready) + '\n' + inspect.getsource(probe_runtime) + '\n' + PROBE


WRITE = r'''import grp,json,os,sys,tempfile
from pathlib import Path
target=Path('/var/lib/grok-admin-panel/evolution-status.json')
data=json.loads(sys.stdin.read())
target.parent.mkdir(parents=True,exist_ok=True)
fd,name=tempfile.mkstemp(prefix='.evolution-status.',dir=str(target.parent))
try:
 with os.fdopen(fd,'w',encoding='utf-8') as f:
  json.dump(data,f,ensure_ascii=False,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
 os.chown(name,0,grp.getgrnam('grok-admin').gr_gid);os.chmod(name,0o640);os.replace(name,target)
finally:
 try:os.unlink(name)
 except FileNotFoundError:pass
'''


def run_remote(script, payload=None, timeout=20):
    return subprocess.run(
        SSH + ["python3 -"], input=script if payload is None else payload,
        text=payload is None, capture_output=True, timeout=timeout, check=False,
    )


def control_probe():
    mem = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, rest = line.split(":", 1)
        mem[key] = int(rest.split()[0])
    disk = shutil.disk_usage("/")
    active = subprocess.run(["/usr/bin/systemctl", "is-active", "--quiet", "qq-evolution.service"], timeout=5).returncode == 0
    return {"online": True, "supervisor": active, "memoryAvailableMiB": mem["MemAvailable"] // 1024,
            "diskFreeGiB": disk.free // (1024 ** 3)}


def publish():
    probe = run_remote(PROBE, timeout=20)
    if probe.returncode:
        raise RuntimeError("QQ server status probe failed")
    production = json.loads(probe.stdout)
    health_path = Path(os.environ.get("QQ_MONITOR_HEALTH", str(ROOT / "monitor-health.json")))
    state_path = Path(os.environ.get("QQ_EVOLUTION_STATE", str(ROOT / "state.json")))
    health = json.loads(health_path.read_text())
    state = json.loads(state_path.read_text())
    archive = ROOT / 'learning-records.jsonl'
    learning = []
    if archive.exists():
        for line in archive.read_text(encoding='utf-8').splitlines()[-12:]:
            try:
                row = json.loads(line)
                row['reason'] = redact_text(row.get('reason', ''))[:240]
                learning.append(row)
            except (ValueError, TypeError):
                continue
    repo = Path('/home/admin/qq-evolution/development')
    changes = []
    commits = subprocess.run(['git', '-C', str(repo), 'log', '-10', '--format=%H %ct', '--author=QQ Evolution'],
                             capture_output=True, text=True, timeout=8, check=True)
    for line in commits.stdout.splitlines():
        revision, timestamp = line.split()
        result = subprocess.run(['git', '-C', str(repo), 'show', '--format=', '--numstat', revision],
                                capture_output=True, text=True, timeout=8, check=True)
        files = []
        for entry in result.stdout.splitlines():
            parts = entry.split('\t')
            if len(parts) == 3:
                files.append({'file': parts[2][:100], 'added': parts[0], 'removed': parts[1]})
        rules = subprocess.run(['git', '-C', str(repo), 'show', '--format=', '--unified=0', revision, '--', 'qq-persona.md'],
                               capture_output=True, text=True, timeout=8, check=True)
        added_rules = [redact_text(x[1:])[:400] for x in rules.stdout.splitlines() if x.startswith('+') and not x.startswith('+++')][:6]
        changes.append({'revision': revision[:12], 'at': int(timestamp), 'files': files, 'summary': added_rules})
    snapshot = build_snapshot(now=int(time.time()), control=control_probe(), production=production,
                              health=health, state=state, latest_change=production.get("latestChange", {}),
                              learning_history=learning, changes=changes)
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    write_script = WRITE.replace("data=json.loads(sys.stdin.read())", f"data=json.loads({snapshot_json!r})")
    pushed = run_remote(write_script, timeout=20)
    if pushed.returncode:
        raise RuntimeError("admin status snapshot push failed")
    print(json.dumps({"published": True, "generatedAt": snapshot["generatedAt"]}))


if __name__ == "__main__":
    publish()
