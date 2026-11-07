"""Backfill the unified archive without changing native/recorder databases."""
import argparse
import hashlib
import hmac
import importlib
import json
import sqlite3
import sys
import types
from contextlib import closing
from pathlib import Path


def load_module(source):
    package=types.ModuleType('_jiangsheng_backfill');package.__path__=[str(source)]
    sys.modules[package.__name__]=package
    return importlib.import_module(package.__name__+'.person_memory')


def backfill(root, plugin, audit):
    memory=load_module(plugin).PersonMemory(root/'jiangsheng-person-memory.sqlite3')
    recorder=root/'plugin_data/astrbot_plugin_message_recorder/messages.db'
    processed=0
    while True:
        batch=memory.import_recorder(recorder)
        processed+=batch
        if not batch:break
    accounts=set()
    if recorder.exists():
        with closing(sqlite3.connect('file:'+recorder.as_posix()+'?mode=ro',uri=True)) as db:
            accounts.update(str(x[0]) for x in db.execute('SELECT DISTINCT sender_id FROM messages'))
    native=root/'plugin_data/astrbot_plugin_private_companion/installations/jiangsheng/runtime/companion-v2.sqlite3'
    if native.exists():
        with closing(sqlite3.connect('file:'+native.as_posix()+'?mode=ro',uri=True)) as db:
            accounts.update(str(x[0]) for x in db.execute('SELECT DISTINCT native_account_id FROM identity_bindings'))
    accounts={x for x in accounts if x.isdecimal() and x!='3899701587'}
    salt=Path('/home/hermes/.config/qq-hermes/audit.salt').read_text().strip().encode()
    lookup={hmac.new(salt,('user:'+uid).encode(),hashlib.sha256).hexdigest():uid for uid in accounts}
    batch=[];audited=0
    for path in sorted(audit.glob('*.jsonl')):
        with path.open(encoding='utf-8',errors='replace') as stream:
            for line in stream:
                try:row=json.loads(line)
                except ValueError:continue
                uid=lookup.get(row.get('speakerHash'))
                direction=row.get('direction');turn=row.get('turnId')
                if not uid or direction not in ('incoming','delivered') or not turn or turn=='unsolicited':continue
                channel='private' if row.get('kind')=='private' else 'group:archive:'+str(row.get('sessionHash','unknown'))
                batch.append((uid,turn,channel,'human' if direction=='incoming' else 'bot',row.get('text',''),float(row.get('timestamp',0))/1000,'audit_receipt'))
                if len(batch)>=500:
                    audited+=memory.record_batch(batch);batch=[]
    if batch:audited+=memory.record_batch(batch)
    return {'recorderRowsProcessed':processed,'auditEntriesAdded':audited,**memory.stats()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='/opt/jiangsheng-astrbot/runtime/data');p.add_argument('--plugin',default='/opt/jiangsheng-astrbot/runtime/data/plugins/astrbot_plugin_jiangsheng');p.add_argument('--audit',default='/home/hermes/qq-audit');args=p.parse_args()
    print(json.dumps(backfill(Path(args.root),Path(args.plugin),Path(args.audit))))
