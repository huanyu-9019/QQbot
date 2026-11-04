import { readFileSync } from 'node:fs';
import { statfsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const MIB = 1024 ** 2;
const GIB = 1024 ** 3;

function timeParts(now) {
  return Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(now).filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
}

export function parseMeminfo(text) {
  const values = Object.fromEntries(String(text).split(/\r?\n/).flatMap(line => {
    const match = line.match(/^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+)\s+kB$/);
    return match ? [[match[1], Number(match[2])]] : [];
  }));
  if (['MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'].some(key => !Number.isSafeInteger(values[key]))) {
    throw new Error('系统内存信息不完整');
  }
  return {
    memoryTotalKiB: values.MemTotal,
    memoryAvailableKiB: values.MemAvailable,
    swapTotalKiB: values.SwapTotal,
    swapFreeKiB: values.SwapFree,
  };
}

export function fiveMinuteUpdateId(timestamp = Date.now()) {
  const parts = timeParts(new Date(timestamp));
  const minute = String(Math.floor(Number(parts.minute) / 5) * 5).padStart(2, '0');
  return `server-space-${parts.year}${parts.month}${parts.day}-${parts.hour}${minute}`;
}

export function formatCapacityReport({ now = Date.now(), disk, memory }) {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(now));
  const get = type => parts.find(part => part.type === type)?.value;
  const timestamp = `${get('month')}月${get('day')}日 ${get('hour')}:${get('minute')}`;
  const report = `${timestamp} 服务器余量：内存可用${Math.round(memory.memoryAvailableKiB / 1024)}/${Math.round(memory.memoryTotalKiB / 1024)}MiB，Swap可用${Math.round(memory.swapFreeKiB / 1024)}/${Math.round(memory.swapTotalKiB / 1024)}MiB，磁盘可用${Math.round(disk.freeBytes / GIB)}/${Math.round(disk.totalBytes / GIB)}GiB。`;
  if (!validateReport(report)) throw new Error('服务器容量文案未通过检查');
  return report;
}

export function validateReport(text) {
  const value = String(text ?? '').trim();
  return Array.from(value).length >= 25 && Array.from(value).length <= 140 &&
    !/https?:\/\/|www\.|@|#|<QQ_SILENT>|(?:\d[\s-]?){7,}/i.test(value);
}

function readCapacity() {
  const fs = statfsSync('/', { bigint: true });
  return {
    disk: { freeBytes: Number(fs.bavail * fs.bsize), totalBytes: Number(fs.blocks * fs.bsize) },
    memory: parseMeminfo(readFileSync('/proc/meminfo', 'utf8')),
  };
}

function main() {
  const report = formatCapacityReport({ now: Date.now(), ...readCapacity() });
  const updateId = fiveMinuteUpdateId();
  if (process.argv.includes('--dry-run')) {
    console.log(JSON.stringify({ updateId, report }));
    return;
  }
  const publisher = join(homedir(), 'qq-qzone-post.mjs');
  const result = spawnSync(process.execPath, [publisher, '--publish-update', updateId], {
    input: report,
    encoding: 'utf8',
    timeout: 120000,
    maxBuffer: 1024 * 1024,
  });
  if (result.error || result.status !== 0) {
    console.error('QQ 空间容量播报失败：', result.error?.name ?? `exit_${result.status}`);
    process.exitCode = 1;
    return;
  }
  console.log(JSON.stringify({ updateId, result: result.stdout.trim() }));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
