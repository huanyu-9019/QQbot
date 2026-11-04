import {spawnSync} from 'node:child_process';

export function ensurePublicationLock(lockPath) {
  if (process.platform !== 'linux') throw new Error('QQ空间发布锁需要 Linux');
  if (process.env.QQ_QZONE_LOCK_HELD === lockPath) return;
  const result=spawnSync('/usr/bin/flock',['--exclusive','--wait','40',lockPath,process.execPath,...process.argv.slice(1)],{
    stdio:'inherit',env:{...process.env,QQ_QZONE_LOCK_HELD:lockPath},
  });
  process.exit(result.status ?? 1);
}
