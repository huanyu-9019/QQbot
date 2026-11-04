export class OneBotReplyTracker {
  constructor(report, { timeoutMs = 45000, setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
    this.report = report;
    this.timeoutMs = timeoutMs;
    this.setTimer = setTimer;
    this.clearTimer = clearTimer;
    this.sequence = 0;
    this.pending = new Map();
  }

  send(socket, action, params, kind) {
    const echo = `qq-send:${process.pid}:${++this.sequence}`;
    const timer = this.setTimer(() => {
      if (!this.pending.delete(echo)) return;
      this.report({ kind, echo, ok: false, reason: 'receipt_timeout' });
    }, this.timeoutMs);
    this.pending.set(echo, { kind, timer });
    try {
      socket.send(JSON.stringify({ action, params, echo }));
    } catch {
      this.clearTimer(timer);
      this.pending.delete(echo);
      this.report({ kind, echo, ok: false, reason: 'socket_send_failed' });
    }
    return echo;
  }

  accept(reply) {
    const item = this.pending.get(reply?.echo);
    if (!item) return false;
    this.clearTimer(item.timer);
    this.pending.delete(reply.echo);
    const retcode = Number.isInteger(reply.retcode) ? reply.retcode : null;
    const ok = reply.status === 'ok' && retcode === 0 && reply.data?.message_id != null;
    const detail = typeof reply.message === 'string' ? reply.message : '';
    this.report({
      kind: item.kind,
      echo: reply.echo,
      ok,
      retcode,
      reason: ok ? 'confirmed' : detail.includes('Timeout: NTEvent') ? 'qq_send_timeout' : 'onebot_rejected',
    });
    return true;
  }

  close() {
    for (const [echo, { kind, timer }] of this.pending.entries()) {
      this.clearTimer(timer);
      this.report({ kind, echo, ok: false, reason: 'connection_closed' });
    }
    this.pending.clear();
  }
}
