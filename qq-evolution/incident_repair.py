"""Fixed production repair operations. Invoked only over the existing authenticated SSH path."""
import datetime,json,os,re,shutil,subprocess,sys
from pathlib import Path

def repair(action):
    if action=='use_deepseek':
        import yaml
        config=Path('/home/hermes/.hermes/config.yaml')
        original=config.read_text();data=yaml.safe_load(original)
        env=dict(line.split('=',1) for line in Path('/home/hermes/.hermes/.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
        key=env.get('DEEPSEEK_API_KEY','').strip()
        if not key:raise RuntimeError('DeepSeek credential missing')
        model=data['model']
        if model.get('provider')!='deepseek' or model.get('default')!='deepseek-flash':
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup=config.with_name('config.yaml.before-incident-'+stamp)
            shutil.copy2(config,backup);backup.chmod(0o600)
            model.update(provider='deepseek',default='deepseek-flash',base_url='https://api.deepseek.com',key_env='DEEPSEEK_API_KEY',api_key=key)
            block=yaml.safe_dump({'model':model},allow_unicode=True,sort_keys=False)
            pattern=r'(?ms)^model:\s*\n.*?(?=^[A-Za-z_][A-Za-z_0-9]*:|\Z)'
            updated,count=re.subn(pattern,lambda _:block+'\n',original,count=1)
            if count!=1:raise RuntimeError('model config block not found')
            if yaml.safe_load(updated)['model']['default']!='deepseek-flash':raise RuntimeError('invalid model config')
            temporary=config.with_suffix('.incident-tmp');temporary.write_text(updated);temporary.chmod(0o600)
            st=config.stat();os.chown(temporary,st.st_uid,st.st_gid);temporary.replace(config)
    elif action not in {'restart_api','restart_bridge'}:
        raise ValueError('unknown repair action')
    unit='qq-hermes-bridge.service' if action=='restart_bridge' else 'hermes-qq-api.service'
    subprocess.run(['/usr/bin/systemctl','restart',unit],check=True,timeout=60)
    print(json.dumps({'action':action,'executed':True}))

if __name__=='__main__':repair(sys.argv[1])
