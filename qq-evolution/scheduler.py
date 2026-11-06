"""Half-hour learning iteration bookkeeping and private reflection archive."""
import json
import os
from pathlib import Path

INTERVAL = 900


def learning_notice(row):
    prefix = f"江生学习#{int(row['iteration'])}："
    if row.get('updated') == 'code':
        suffix = '。已发布并通过生产测试和健康检查。'
    elif str(row.get('reason', '')).startswith('Iteration assessment unavailable:'):
        suffix = '。本轮评估失败，保留当前版本，后续重试。'
    else:
        suffix = '。已记录经验；本轮未发布代码。'
    budget = 140 - len(prefix) - len(suffix)
    reason = str(row.get('reason', '')).replace('\n', ' ')
    return prefix + reason[:budget] + suffix


def iteration_due(state, now):
    return int(now) - int(state.get('lastIteration', 0)) >= INTERVAL


def record_iteration(state, *, now, updated, reason, revision=None):
    state['lastIteration'] = int(now)
    state['iterationCount'] = int(state.get('iterationCount', 0)) + 1
    state['updateKind'] = 'code' if updated else 'learning_record'
    state['lastReason'] = str(reason)[:240]
    if revision:
        state['lastRevision'] = revision
    return state


def append_learning_record(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {
        'timestamp': int(state['lastIteration']),
        'iteration': int(state['iterationCount']),
        'updated': state['updateKind'],
        'reason': str(state['lastReason'])[:240],
    }
    if state.get('lastRevision'):
        record['revision'] = str(state['lastRevision'])[:80]
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, (json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8'))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record
