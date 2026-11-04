// Queue state belongs to each pending array; running work is never present here.
const bursts = new WeakMap();
function priority(task) {
  if (task.trigger === 'typing' || task.trigger?.startsWith('proactive') || task.collectionOnly) return 0;
  return task.kind === 'private' || task.mentioned ? 2 : 1;
}
export function isPriorityTask(task) { return priority(task) === 2; }
function coalescible(task) {
  return task.kind === 'group' && !task.mentioned && !task.directed && !task.mentionOnly &&
    !task.collectionOnly && !task.trigger && !task.mediaError && !task.recentImageRef &&
    !task.incomingImageRef && !task.imageUrls?.length && !task.images?.length &&
    typeof task.text === 'string' && Boolean(task.text.trim());
}
export function releaseTask(task) {
  for (const field of ['images','imageUrls','rawImageInputs','incomingImageRef','recentImageRef']) delete task[field];
}
export function enqueueTask(queue, task, config) {
  if (config.enabled && config.coalesceGroupText && coalescible(task)) {
    const index = queue.findIndex(old => coalescible(old) && old.groupId === task.groupId);
    if (index >= 0) {
      releaseTask(queue.splice(index,1)[0]); queue.push(task);
      return {accepted:true,reason:'coalesced'};
    }
  }
  if (queue.length >= config.maxPending) {
    const index = config.enabled && priority(task) === 2 ? queue.findIndex(old => priority(old) < 2) : -1;
    if (index < 0) {releaseTask(task);return {accepted:false,reason:'queue_full'};}
    releaseTask(queue.splice(index,1)[0]); queue.push(task);
    return {accepted:true,reason:'replaced'};
  }
  queue.push(task);return {accepted:true,reason:'queued'};
}
export function dequeueTask(queue, config, {blockedSessions,priorityOnly=false}={}) {
  if (!queue.length) {bursts.delete(queue);return undefined;}
  const eligible = task => !blockedSessions?.has(task.sessionKey) && (!priorityOnly || isPriorityTask(task));
  const first = queue.findIndex(eligible);
  if (first < 0) return undefined;
  if (!config.enabled) {bursts.delete(queue);return queue.splice(first,1)[0];}
  const high = queue.findIndex(task => eligible(task) && priority(task) === 2);
  const normal = queue.findIndex(task => eligible(task) && priority(task) === 1);
  const burst = bursts.get(queue) || 0;
  const index = high >= 0 && (normal < 0 || burst < config.priorityBurst) ? high : normal >= 0 ? normal : first;
  const task = queue.splice(index,1)[0];
  bursts.set(queue,priority(task) === 2 ? Math.min(config.priorityBurst,burst+1) : 0);
  return task;
}
