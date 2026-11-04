"""Public, combined QQ Space health report. Secrets never enter the report."""
import datetime
import inspect
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path('/home/admin/qq-evolution-state')
SCHEDULE = ROOT / 'report-schedule.json'
HEALTH = ROOT / 'monitor-health.json'
SSH = ['/usr/bin/ssh','-i','/home/admin/.ssh/qq-evolution-prod','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','root@39.105.219.112']

def report_slot(start, now):
    elapsed=max(0,int(now)-int(start))
    return 'fast-'+str(elapsed//300) if elapsed<7200 else 'slow-'+str((elapsed-7200)//14400)

def probe():
    def active(unit):
        return subprocess.run(['/usr/bin/systemctl','is-active','--quiet',unit],timeout=10).returncode==0
    info={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key,rest=line.split(':',1)
        info[key]=int(rest.split()[0])
    disk=shutil.disk_usage('/')
    return {'online':True,'memoryFree':info['MemAvailable']//1024,'memoryTotal':info['MemTotal']//1024,
            'swapFree':info['SwapFree']//1024,'swapTotal':info['SwapTotal']//1024,
            'diskFree':disk.free//(1024**3),'diskTotal':disk.total//(1024**3),
            'bridge':active('qq-hermes-bridge.service'),'api':active('hermes-qq-api.service'),
            'supervisor':active('qq-evolution.service')}

def format_report(control, production, now):
    dt=datetime.datetime.fromtimestamp(now,datetime.timezone(datetime.timedelta(hours=8)))
    def resources(row):
        return f"内存余{row['memoryFree']}/{row['memoryTotal']}M，盘余{row['diskFree']}/{row['diskTotal']}G，换页余{row['swapFree']}M"
    text=(f"{dt.month}月{dt.day}日{dt:%H:%M} 双机巡检：Codex机在线，监听{control['monitor']}、评估{control['evaluation']}，{resources(control)}。"
          f"QQ机在线，机器人{'正常' if production['bridge'] else '异常'}、API{'正常' if production['api'] else '异常'}，{resources(production)}。")
    if not 25<=len(text)<=140:
        raise ValueError('public status report length invalid')
    return text

def save_schedule(data):
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=SCHEDULE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data),encoding='utf-8')
    os.chmod(tmp,0o600)
    tmp.replace(SCHEDULE)

def main():
    now=int(time.time())
    schedule=json.loads(SCHEDULE.read_text())
    slot=report_slot(schedule['start'],now)
    if schedule.get('lastSentSlot')==slot:
        print('status report not due',flush=True)
        return
    control=probe()
    try:
        health=json.loads(HEALTH.read_text())
    except (FileNotFoundError,json.JSONDecodeError):
        health={}
    fresh=now-int(health.get('pollStarted',0))<=600 and now-int(health.get('lastFetch',0))<=2400
    control['monitor']='正常' if control['supervisor'] and fresh else '待核实'
    try:
        assessment=json.loads((ROOT/'state.json').read_text()).get('status')
    except (FileNotFoundError,json.JSONDecodeError):
        assessment=None
    control['evaluation']='异常' if assessment in ('cycle_error','release_error','rolled_back') or health.get('outcome')=='locked_out' else '进行中' if assessment=='evaluating' else '待机' if health.get('outcome')=='cooldown' else '正常' if fresh else '待核实'
    script='import json,shutil,subprocess\nfrom pathlib import Path\n'+inspect.getsource(probe)+'\nprint(json.dumps(probe()))\n'
    result=subprocess.run(SSH+['python3 -'],input=script,text=True,capture_output=True,timeout=50,check=True)
    production=json.loads(result.stdout)
    report=format_report(control,production,now)
    ident='dual-status-'+str(schedule['start'])+'-'+slot
    publish_script=(
        'import json,subprocess\nfrom pathlib import Path\n'
        f'r=subprocess.run(["/home/hermes/.hermes/tools/node-26.12.1-linux-x64/bin/node","/home/hermes/qq-qzone-post.mjs","--publish-update",{ident!r}],input={report!r},text=True,capture_output=True,timeout=100)\n'
        's=json.loads(Path("/home/hermes/qq-qzone-state.json").read_text())\n'
        f'v=s.get("publishedUpdates",{{}}).get({ident!r},{{}})\n'
        'print(json.dumps({"sent":v.get("status")=="sent" and bool(v.get("tid")),"publisher_exit":r.returncode}))\n'
    )
    sent=subprocess.run(SSH+['python3 -'],input=publish_script,text=True,capture_output=True,timeout=130,check=True)
    if not json.loads(sent.stdout).get('sent'):
        raise RuntimeError('QQ Space publication unconfirmed')
    schedule['lastSentSlot']=slot
    schedule['lastSentAt']=now
    save_schedule(schedule)
    print(json.dumps({'slot':slot,'sent':True,'report':report},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
