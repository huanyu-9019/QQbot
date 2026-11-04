import test from 'node:test';
import assert from 'node:assert/strict';
import {
  fiveMinuteUpdateId,
  formatCapacityReport,
  parseMeminfo,
  validateReport,
} from './qq-space-disk-report.mjs';

test('parses memory and swap totals from proc meminfo', () => {
  assert.deepEqual(parseMeminfo('MemTotal: 1024 kB\nMemAvailable: 512 kB\nSwapTotal: 2048 kB\nSwapFree: 1024 kB'), {
    memoryTotalKiB: 1024,
    memoryAvailableKiB: 512,
    swapTotalKiB: 2048,
    swapFreeKiB: 1024,
  });
});

test('formats disk, memory, swap, and a Beijing timestamp into a safe short post', () => {
  const report = formatCapacityReport({
    now: Date.UTC(2026, 10, 5, 4, 5),
    disk: { freeBytes: 10 * 1024 ** 3, totalBytes: 20 * 1024 ** 3 },
    memory: { memoryAvailableKiB: 512 * 1024, memoryTotalKiB: 1024 * 1024, swapFreeKiB: 1024 * 1024, swapTotalKiB: 2 * 1024 * 1024 },
  });
  assert.match(report, /11月5日 12:05/);
  assert.match(report, /内存可用512\/1024MiB/);
  assert.match(report, /Swap可用1024\/2048MiB/);
  assert.match(report, /磁盘可用10\/20GiB/);
  assert.equal(validateReport(report), true);
});

test('creates one id per five-minute Beijing slot and a new id at the next slot', () => {
  const first = Date.UTC(2026, 10, 5, 4, 0);
  assert.equal(fiveMinuteUpdateId(first), fiveMinuteUpdateId(first + 4 * 60 * 1000));
  assert.notEqual(fiveMinuteUpdateId(first), fiveMinuteUpdateId(first + 5 * 60 * 1000));
  assert.match(fiveMinuteUpdateId(first), /^server-space-[a-z0-9-]+$/);
});

test('rejects public report text outside the publisher constraints', () => {
  assert.equal(validateReport('https://example.com 状态报告，一切都正常'), false);
  assert.equal(validateReport('状态'.repeat(80)), false);
  assert.equal(validateReport('短报告'), false);
});
