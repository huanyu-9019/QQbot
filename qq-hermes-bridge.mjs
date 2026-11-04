import { readFileSync } from 'node:fs';
import { buildMessages } from './qq-persona-messages.mjs';
import { OneBotReplyTracker } from './qq-send-receipts.mjs';
import { assertSearchOnlyAccess } from './qq-search-policy.mjs';
import { record, recordAssistant, consolidate, forget, observeRelationship } from './qq-memory.mjs';
import {loadMediaConfig,parseIncoming,prepareImages,normalizeImage,mediaErrorMessage} from './qq-media.mjs';
import {StickerLibrary} from './qq-online-stickers.mjs';
import {LearnedStickerLibrary} from './qq-learned-stickers.mjs';
import {RecentImages} from './qq-recent-images.mjs';
import {TypingNudges,typingText} from './qq-typing.mjs';
import {enqueueTask,dequeueTask,isPriorityTask} from './qq-task-queue.mjs';
import {loadInteractionConfig} from './qq-interaction-config.mjs';
import {createProactiveScheduler} from './qq-proactive.mjs';
import {createReminderScheduler,handleReminderCommand} from './qq-reminders.mjs';
import {isDirectGroupMessage} from './qq-group-routing.mjs';
import { synthesizeMiniMax, toOneBotAudio, shouldSendVoice, createVoiceLimiter, cleanupVoiceFiles } from './qq-gemini-tts.mjs';
import { liveFactReply, requiresFreshFacts, hasFreshSearchEvidence } from './qq-live-facts.mjs';
import { fetchFemaleSongClip, songIntent } from './qq-song-clips.mjs';
import { createConversationAudit } from './qq-conversation-audit.mjs';


const env = readFileSync(`${process.env.HOME}/.hermes/.env`, 'utf8');
const ttsEnv = readFileSync(`${process.env.HOME}/.hermes/qq-minimax-tts.env`, 'utf8');
const minimaxKey = ttsEnv.split(/\r?\n/).find(x => x.startsWith('MINIMAX_API_KEY='))?.slice('MINIMAX_API_KEY='.length).trim();
const keyLine = env.split(/\r?\n/).filter(x => x.startsWith('API_SERVER_KEY=')).at(-1);
const apiKey = keyLine?.slice('API_SERVER_KEY='.length).trim();
if (!apiKey) throw new Error('找不到 API_SERVER_KEY');

const api = 'http://127.0.0.1:8642';
const conversationAudit = createConversationAudit({
  directory: process.env.QQ_AUDIT_DIR || `${process.env.HOME}/qq-audit`,
  saltFile: process.env.QQ_AUDIT_SALT_FILE || `${process.env.HOME}/.config/qq-hermes/audit.salt`,
});
conversationAudit.prune();
const mediaConfig=loadMediaConfig();
const collection=new LearnedStickerLibrary(mediaConfig);
collection.validateAssets();
const stickers=new StickerLibrary(mediaConfig,{collection});
stickers.validateAssets();
const seen = new Set();
const lastMessage = new Map();
const queue = [];
const lastGroupDecision = new Map();
const lastGroupReply = new Map();
const interactionConfig = loadInteractionConfig();
const groupInteraction = interactionConfig.group;
const queueConfig = interactionConfig.queue;
const GROUP_DECISION_INTERVAL_MS = groupInteraction.enabled?groupInteraction.decisionIntervalMs:Infinity;
const GROUP_REPLY_COOLDOWN_MS = groupInteraction.enabled?groupInteraction.replyCooldownMs:Infinity;
let socket;
let connectionOutage = false;
let working = false;
let reminderScheduler;
const activeSessions = new Set();
const voiceLastSent = new Map();
const voiceLimiter = createVoiceLimiter({ dailyLimit: 10 });
const voiceDir = '/tmp/qq-hermes-voice';
void cleanupVoiceFiles(voiceDir).catch(() => {});
const activeLanes = new Set();
const recentImages=new RecentImages(mediaConfig);
const pendingAuditDeliveries = new Map();
const typing=new TypingNudges({
  connected:()=>socket?.readyState===WebSocket.OPEN,
  isBusy:()=>working||queue.length>0,
  enqueue:task=>{
    const result=enqueueTask(queue,task,queueConfig);
    if(result.accepted)void processQueue();
    else console.log('QQ 队列：',JSON.stringify({reason:result.reason,queueDepth:queue.length}));
  },
});
const delivery = new OneBotReplyTracker(outcome => {
  if (outcome.echo) reminderScheduler?.delivery(outcome.echo, outcome.ok);
  const auditEvent = pendingAuditDeliveries.get(outcome.echo);
  if (auditEvent) {
    pendingAuditDeliveries.delete(outcome.echo);
    if (outcome.ok) {
      try { conversationAudit.recordDelivered(auditEvent); }
      catch (error) { console.error('审计回复记录失败：', error.message); }
    }
  }
  const log = outcome.ok ? console.log : console.error;
  log('QQ 发送回执：', JSON.stringify(outcome));
});
const proactive = createProactiveScheduler({
  queue,
  queueConfig,
  activeSessions,
  isConnected: () => socket?.readyState === WebSocket.OPEN,
  processQueue: () => processQueue(),
});

function sendVoice(task, file, text) {
  if (socket?.readyState !== WebSocket.OPEN) return;
  const action = task.kind === 'group' ? 'send_group_msg' : 'send_private_msg';
  const params = task.kind === 'group'
    ? { group_id: task.groupId, message: [{ type: 'record', data: { file } }] }
    : { user_id: task.userId, message: [{ type: 'record', data: { file } }] };
  const echo = delivery.send(socket, action, params, task.kind);
  if (task.turnId && echo) pendingAuditDeliveries.set(echo, { sessionKey: task.sessionKey, kind: task.kind, text, turnId: task.turnId });
  return echo;
}

async function maybeSendVoice(task, text) {
  const forceVoiceTest = task.kind === 'private' && /^(?:江生[，,、 ]*)?测试语音$/.test(String(task.text ?? '').trim());
  const forceSong = songIntent(task.text) || /(?:给我|帮我|来|放|发|播|听).{0,12}(?:一段|一首|首歌|歌曲|歌词|唱)/i.test(String(task.text ?? '').trim()) || /^(?:唱|哼|放歌|点歌)/i.test(String(task.text ?? '').trim());
  if (!minimaxKey || (!forceVoiceTest && !forceSong && !shouldSendVoice({ kind: task.kind, text, lastSentAt: voiceLastSent.get(task.sessionKey) ?? -Infinity, dailyCount: voiceLimiter.count }))) return false;
  if (!forceVoiceTest && !voiceLimiter.allow()) return false;
  if (forceSong) {
    try {
      const clip = await fetchFemaleSongClip(task.text);
      const result = sendVoice(task, toOneBotAudio(clip.audio), task.text);
      if (result !== undefined) voiceLastSent.set(task.sessionKey, Date.now());
      console.log('QQ 点歌片段发送：', JSON.stringify({ kind: task.kind, title: clip.title, artist: clip.artist }));
      return true;
    } catch (error) {
      console.error('QQ 点歌片段失败，回退 TTS：', error.message);
    }
  }
  try {
    const audio = await synthesizeMiniMax(forceVoiceTest ? '嗯，收到啦。现在是语音测试。' : text, { apiKey: minimaxKey });
    const result = sendVoice(task, toOneBotAudio(audio), text);
    if (result !== undefined) voiceLastSent.set(task.sessionKey, Date.now());
    console.log('QQ 语音发送：', JSON.stringify({ kind: task.kind, chars: Array.from(text).length, forcedTest: forceVoiceTest, forcedSong: forceSong }));
    return true;
  } catch (error) {
    console.error('QQ 语音失败：', error.message);
    return false;
  }
}

function send(task, text, stickerFile = null) {
  if (socket?.readyState !== WebSocket.OPEN) {
    console.error('QQ 发送回执：', JSON.stringify({ kind: task.kind, ok: false, reason: 'not_connected' }));
    return;
  }
  const content = Array.from(text).slice(0, 1500).join('');
  const message = content ? [{ type: 'text', data: { text: content } }] : [];
  if(stickerFile) message.push({type:'image',data:{file:stickerFile,sub_type:1}});
  if(!message.length) return;
  const action = task.kind === 'group' ? 'send_group_msg' : 'send_private_msg';
  const params = task.kind === 'group'
    ? { group_id: task.groupId, message }
    : { user_id: task.userId, message };
  const echo = delivery.send(socket, action, params, task.kind);
  if (task.turnId && echo) pendingAuditDeliveries.set(echo, { sessionKey: task.sessionKey, kind: task.kind, text: content, turnId: task.turnId });
  return echo;
}

reminderScheduler = createReminderScheduler({
  path: '/home/hermes/qq-reminders.json',
  send: task => send(task, task.text),
});

async function askHermes(task) {
  const headers = { Authorization: `Bearer ${apiKey}` };
  const toolsetCheckStartedAt = Date.now();
  await assertSearchOnlyAccess(api, headers);
  const toolsetCheckMs = Date.now() - toolsetCheckStartedAt;
  const modelRequestStartedAt = Date.now();

  const verifyFresh = !task.collectionOnly && !task.trigger && requiresFreshFacts(task.text);
  const messages = buildMessages(task,{stickerInstructions:stickers.instructions(),learningInstructions:collection.instructions(task),recentImageInstructions:recentImages.instructions(task)});
  const response = await fetch(`${api}/v1/${verifyFresh ? 'responses' : 'chat/completions'}`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
      'X-Hermes-Session-Key': task.collectionOnly?task.sessionKey+':collection':task.sessionKey,
    },
    body: JSON.stringify({
      model: 'hermes-agent',
      ...(verifyFresh ? {input:messages,store:false} : {messages}),
    }),
    signal: task.signal?AbortSignal.any([task.signal,AbortSignal.timeout(task.timeoutMs||120000)]):AbortSignal.timeout(120000),
  });
  if (!response.ok) throw new Error(`Hermes HTTP ${response.status}`);
  const modelRequestMs = Date.now() - modelRequestStartedAt;
  const result = await response.json();
  if (verifyFresh) {
    if (result.status !== 'completed') throw new Error('Hermes 时效查询未完成');
    const verified = hasFreshSearchEvidence(result);
    const text = (result.output ?? []).filter(x => x.type === 'message' && x.role === 'assistant').flatMap(x => x.content ?? []).filter(x => x.type === 'output_text').map(x => x.text ?? '').join('\n').trim();
    const silent = text === '<QQ_SILENT>';
    console.log('QQ 时效核实：',JSON.stringify({kind:task.kind,verified,silent}));
    return silent ? text : verified && text ? text : '这条我还没核实到最新消息，先不乱说。';
  }
  const choice = result.choices?.[0];
  if (choice?.finish_reason === 'error' || choice?.finish_reason === 'cancelled') {
    throw new Error('Hermes 本轮未成功完成');
  }
  console.log('QQ 阶段耗时：', JSON.stringify({
    kind: task.kind,
    queueWaitMs: Number.isFinite(task.queueWaitMs) ? task.queueWaitMs : null,
    toolsetCheckMs,
    modelRequestMs,
    hasImages: Boolean(task.images?.length),
    imageFollowup: task.imageContext === 'previous',
  }));
  return String(choice?.message?.content ?? '').trim();
}

function sendAnswer(task, answer, stickerFile = null) {
  if(stickerFile) {
    if(answer.trim())send(task,answer);
    send(task,'',stickerFile);
    return;
  }
  const parts = task.kind === 'group'
    ? answer.match(/^([\s\S]+?[。！？!?])\s*([\s\S]+)$/)
    : null;
  if (!parts) {
    send(task, answer);
    return;
  }
  send(task, parts[1]);
  setTimeout(() => send(task, parts[2]), 900);
}

async function processQueue(priorityOnly = false) {
  const lane = priorityOnly ? 'priority' : 'main';
  const priorityEnabled = queueConfig.enabled && queueConfig.priorityLane;
  if (activeLanes.has(lane)) {
    if (!priorityOnly && priorityEnabled) void processQueue(true);
    return;
  }
  if (priorityOnly && (!priorityEnabled || !queue.some(task => isPriorityTask(task) && !activeSessions.has(task.sessionKey)))) return;
  activeLanes.add(lane);
  working = true;
  try {
    while (true) {
      const task = dequeueTask(queue,queueConfig,{blockedSessions:activeSessions,priorityOnly});
      if(!task)break;
      task.queueWaitMs = Number.isFinite(task.enqueuedAt) ? Math.max(0, Date.now() - task.enqueuedAt) : null;
      activeSessions.add(task.sessionKey);
      let taskCompleted = false;
      try {
        if(task.trigger==='typing'){
          if(!typing.isCurrent(task))continue;
          const answer=await askHermes(task);
          if(typing.isCurrent(task)){
            const text=typingText(answer);if(text)send(task,text);
          }
          continue;
        }
        if (task.kind === 'group' && !task.directed && !task.trigger?.startsWith('proactive')) {
          const now = Date.now();
          if (now - (lastGroupReply.get(task.groupId) ?? 0) < GROUP_REPLY_COOLDOWN_MS ||
              now - (lastGroupDecision.get(task.groupId) ?? 0) < GROUP_DECISION_INTERVAL_MS) {
            console.log('QQ 群聊决策：',JSON.stringify({reason:GROUP_REPLY_COOLDOWN_MS===Infinity?'group_disabled':now-(lastGroupReply.get(task.groupId)??0)<GROUP_REPLY_COOLDOWN_MS?'reply_cooldown':'decision_cooldown',collectionOnly:Boolean(collection.enabled&&task.imageUrls?.length&&collection.eligible(task).length)}));
            if(collection.enabled&&task.imageUrls?.length&&collection.eligible(task).length)task.collectionOnly=true;
            else continue;
          }
          if(!task.collectionOnly)lastGroupDecision.set(task.groupId, now);
        }

        if(task.mediaError) {
          if(!task.collectionOnly&&(task.kind==='private'||task.mentioned))send(task,mediaErrorMessage(task.mediaError));
          continue;
        }
        if(task.imageUrls?.length) {
          const imageStartedAt=Date.now();
          try {
            if(collection.enabled&&task.collectibleIndexes?.length){
              task.rawImageInputs=[];
              task.images=await prepareImages(task.imageUrls,mediaConfig,{normalize:async(bytes,c)=>{task.rawImageInputs.push(bytes);return normalizeImage(bytes,c);}});
            }else task.images=await prepareImages(task.imageUrls,mediaConfig);
            if(task.incomingImageRef)recentImages.cache(task.incomingImageRef,task.images.at(-1));
            console.log('QQ 图片处理：',JSON.stringify({ok:true,count:task.images.length,elapsedMs:Date.now()-imageStartedAt}));
          } catch(error) {
            console.error('QQ 图片处理：',JSON.stringify({ok:false,code:error.code||'INVALID_IMAGE',elapsedMs:Date.now()-imageStartedAt}));
            if(!task.collectionOnly&&(task.kind==='private'||task.mentioned))send(task,mediaErrorMessage(error.code));
            continue;
          }
        }
        let answer = await askHermes(task);
        if(!task.collectionOnly&&answer.trim()==='[[LOOK_RECENT_IMAGE]]'){
          try{
            const images=await recentImages.resolve(task);
            if(!images.length)throw new Error('RECENT_IMAGE_UNAVAILABLE');
            task.images=images;task.imageContext='previous';
            delete task.recentImageRef;
            answer=await askHermes(task);
          }catch{
            if(task.kind==='private'||task.mentioned)send(task,'最近那张图暂时没读到，请把图片重新发一下。');
            continue;
          }
        }
        answer=answer.replaceAll('[[LOOK_RECENT_IMAGE]]','').trim();
        const learned=await collection.consume(task,answer);
        answer=learned.text;
        if(learned.saved)console.log('QQ 表情收藏：',JSON.stringify({count:learned.saved}));
        taskCompleted = true;
        if(task.collectionOnly)continue;
        if (task.kind === 'group' && task.directed && (!answer || answer === '<QQ_SILENT>')) { console.log('QQ 群聊决策：',JSON.stringify({reason:'directed_empty_model_reply'})); answer = '我在，刚才那句我接住了。'; }
        if (task.kind === 'group' && !task.directed && (!answer || answer === '<QQ_SILENT>')) {console.log('QQ 群聊决策：',JSON.stringify({reason:answer?'model_silent':'empty_model_reply'}));continue;}
        const reply=stickers.parse(answer);
        if(task.kind==='group'&&reply.text==='<QQ_SILENT>'&&!task.directed){console.log('QQ 群聊决策：',JSON.stringify({reason:'model_silent'}));continue;}
        let stickerFile=null;
        try{stickerFile=await stickers.select(task,reply);}catch{
          stickers.status={reason:'unavailable'};
          console.error('QQ 网络表情：',JSON.stringify({ok:false,reason:'image_unavailable'}));
        }
        const text=reply.id&&reply.mode==='requested'&&!stickerFile?stickers.fallbackText(reply):reply.text||(stickerFile?'':reply.id?stickers.fallbackText(reply):'这次没有生成回复，请再试一次。');
        if(!text&&!stickerFile){if(task.kind==='group')console.log('QQ 群聊决策：',JSON.stringify({reason:'sticker_only_unavailable',stickerReason:stickers.status.reason}));continue;}
        const voiceSent = text ? await maybeSendVoice(task, text) : false;
        if (!voiceSent) sendAnswer(task,text,stickerFile);
        recordAssistant(task, text);
        if(task.kind==='group')console.log('QQ 群聊决策：',JSON.stringify({reason:'reply_ready',mentioned:Boolean(task.mentioned)}));
        if(stickerFile)console.log('QQ 网络表情：',JSON.stringify({ok:true,source:stickers.status.source}));
        if (task.kind === 'group') lastGroupReply.set(task.groupId, Date.now());
      } catch (error) {
        taskCompleted = false;
        console.error('处理失败：', error.message);
        if ((task.kind === 'private'||task.kind === 'group'&&task.mentioned)&&task.trigger!=='typing'&&!task.trigger?.startsWith('proactive')&&!task.collectionOnly) send(task, '这次没能回复成功，请稍后再试。');
      } finally {
        delete task.images;
        delete task.imageUrls;
        delete task.rawImageInputs;
        delete task.incomingImageRef;
        delete task.recentImageRef;
        activeSessions.delete(task.sessionKey);
        if(taskCompleted&&task.trigger!=='typing'&&!task.trigger?.startsWith('proactive')&&!task.collectionOnly&&queue.length===0&&activeLanes.size===1){
          try { await consolidate(task, askHermes); }
          catch (error) { console.error('记忆整理失败：', error.message); }
        }
      }
    }
  } finally {
    activeLanes.delete(lane);
    working = activeLanes.size > 0;
    const available = queue.filter(task => !activeSessions.has(task.sessionKey));
    if (available.length) {
      if (!activeLanes.has('main')) void processQueue();
      else if (priorityEnabled && !activeLanes.has('priority') && available.some(isPriorityTask)) void processQueue(true);
    }
  }
}

function receive(event) {
  if(typing.receive(event))return;
  if (event.post_type !== 'message') return;
  if (event.message_type !== 'private' && event.message_type !== 'group') return;
  const userId = String(event.user_id ?? '');
  const selfId = String(event.self_id ?? '');
  if (!/^\d+$/.test(userId) || userId === selfId) return;

  const kind = event.message_type;
  const groupId = String(event.group_id ?? '');
  if (kind === 'group' && !/^\d+$/.test(groupId)) return;
  const sessionKey = kind === 'group'
    ? `qq:group:${groupId}`
    : `qq:private:${userId}`;

  const messageId = String(event.message_id ?? '');
  const identity = `${sessionKey}:${messageId}`;
  if (messageId && seen.has(identity)) return;
  if (messageId) {
    seen.add(identity);
    if (seen.size > 1000) seen.delete(seen.values().next().value);
  }
  proactive.observe({ sessionKey });
  typing.message({kind,userId,sessionKey});
  const segments = Array.isArray(event.message) ? event.message : [];
  const mentioned = kind === 'group' &&
    segments.some(x => x.type === 'at' && String(x.data?.qq) === selfId);
  const input=parseIncoming(segments,{kind,mentioned},mediaConfig);
  console.log('QQ 消息接收：',JSON.stringify({kind,mentioned,hasText:Boolean(input.text),images:input.imageUrls.length,queueDepth:queue.length}));
  if(input.ignored||!mentioned&&!input.text&&!input.imageUrls.length&&!input.error){console.log('QQ 消息跳过：',JSON.stringify({kind,reason:'empty_unsupported'}));return;}
  const mentionOnly=mentioned&&!input.text&&!input.imageUrls.length&&!input.error;
  const text=input.text;

  const now = Date.now();
  const privateTooSoon = kind === 'private' &&
    now - (lastMessage.get(sessionKey) ?? 0) < 3000;
  lastMessage.set(sessionKey, now);
  if (lastMessage.size > 1000) lastMessage.delete(lastMessage.keys().next().value);

  const sender = event.sender ?? {};
  const speakerName = kind === 'group'
    ? String(sender.card || sender.nickname || '').replace(/[\r\n\t]+/g, ' ').trim().slice(0, 80)
    : '';
  const privateNickname = kind === 'private'
    ? String(sender.nickname || '').replace(/[\r\n\t]+/g, ' ').trim().slice(0, 80)
    : '';
  const directed = kind === 'group' && isDirectGroupMessage({ mentioned, text });
  const task = { kind, userId, groupId, sessionKey, speakerName, privateNickname, text, mentioned, directed, mentionOnly, imageUrls:input.imageUrls,mediaKind:input.mediaKind,mediaError:input.error,collectibleIndexes:input.imageIndexes,markedStickerIndexes:input.collectibleIndexes };
  try {
    task.turnId = conversationAudit.recordIncoming({ sessionKey, kind, text });
  } catch (error) {
    console.error('审计消息记录失败：', error.message);
  }
  try { observeRelationship(task); }
  catch (error) { console.error('关系状态更新失败：', error.message); }
  const explicitReminderCommand = /(?:提醒我|请提醒|提醒一下|查询提醒|查看提醒|我的提醒|取消提醒|删除提醒|停止提醒)/.test(text);
  const liveReply = liveFactReply(text);
  if (liveReply && (kind === 'private' || mentioned)) {
    send(task, liveReply);
    recordAssistant(task, liveReply);
    return;
  }
  if (kind === 'private' || mentioned || explicitReminderCommand) {
    const reminderReply = handleReminderCommand(task, reminderScheduler);
    if (reminderReply !== null) {
      send(task, reminderReply);
      return;
    }
  }
  recentImages.observe(task);
  try { record(task); }
  catch (error) { console.error('记录消息失败：', error.message); }
  if (privateTooSoon&&!recentImages.allowFastFollowup(task)){
    if(collection.enabled&&task.imageUrls?.length&&collection.eligible(task).length)task.collectionOnly=true;
    else {console.log('QQ 消息跳过：',JSON.stringify({kind,reason:'private_throttle'}));return;}
  }
  if (Array.from(text).length > 2000&&!task.collectionOnly) {
    console.log('QQ 消息跳过：',JSON.stringify({kind,reason:'text_too_long'}));
    if (kind === 'private') send(task, '一次最多发送 2000 字。');
    return;
  }
  task.enqueuedAt=Date.now();
  const queued=enqueueTask(queue,task,queueConfig);
  if (!queued.accepted) {
    console.log('QQ 消息跳过：',JSON.stringify({reason:queued.reason,queueDepth:queue.length}));
    if (!task.collectionOnly&&(kind === 'private'||queueConfig.enabled&&mentioned)) send(task, '现在消息较多，请稍后再发。');
    return;
  }
  if(queued.reason!=='queued')console.log('QQ 队列：',JSON.stringify({reason:queued.reason,queueDepth:queue.length}));
  console.log('QQ 消息入队：',JSON.stringify({kind,mentioned,collectionOnly:Boolean(task.collectionOnly),queueDepth:queue.length}));
  void processQueue();
}

function connect() {
  socket = new WebSocket('ws://127.0.0.1:3001');
  socket.addEventListener('open', () => {
    console.log(connectionOutage ? '已重新连接 NapCat OneBot' : '已连接 NapCat OneBot');
    connectionOutage = false;
  });
  socket.addEventListener('message', ({ data }) => {
    try {
      const event = JSON.parse(String(data));
      if (!delivery.accept(event)) receive(event);
    } catch {
      console.error('忽略无法解析的 OneBot 事件');
    }
  });
  socket.addEventListener('error', () => {
    if (!connectionOutage) console.error('NapCat WebSocket 连接出错，3 秒后重试');
    connectionOutage = true;
  });
  socket.addEventListener('close', () => {
    typing.close();
    delivery.close();
    if (!connectionOutage) console.log('NapCat 连接断开，3 秒后重连');
    connectionOutage = true;
    setTimeout(connect, 3000);
  });
}

connect();
