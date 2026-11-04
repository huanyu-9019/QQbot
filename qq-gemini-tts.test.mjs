import test from 'node:test';
import assert from 'node:assert/strict';
import { pcmToWav, shouldSendVoice, createVoiceLimiter } from './qq-gemini-tts.mjs';

test('wraps mono 24kHz PCM as a valid WAV', () => {
  const wav = pcmToWav(Buffer.from([0, 0, 255, 127]), 24000);
  assert.equal(wav.toString('ascii', 0, 4), 'RIFF');
  assert.equal(wav.toString('ascii', 8, 12), 'WAVE');
  assert.equal(wav.readUInt16LE(22), 1);
  assert.equal(wav.readUInt32LE(24), 24000);
  assert.equal(wav.readUInt16LE(34), 16);
  assert.equal(wav.length, 48);
});

test('voice policy keeps short replies occasional and respects cooldown', () => {
  assert.equal(shouldSendVoice({ kind: 'private', text: '好呀', random: () => 0.1, now: 0, lastSentAt: -Infinity, dailyCount: 0 }), true);
  assert.equal(shouldSendVoice({ kind: 'private', text: '好呀', random: () => 0.1, now: 1, lastSentAt: 0, dailyCount: 0 }), false);
  assert.equal(shouldSendVoice({ kind: 'group', text: '好呀', random: () => 0.01, now: 700000, lastSentAt: -Infinity, dailyCount: 0 }), true);
  assert.equal(shouldSendVoice({ kind: 'group', text: '这是一段很长的回复'.repeat(100), random: () => 0, now: 700000, lastSentAt: -Infinity, dailyCount: 0 }), false);
});

test('daily limiter stops after ten generated voices', () => {
  const limiter = createVoiceLimiter({ dailyLimit: 10 });
  for (let i = 0; i < 10; i++) assert.equal(limiter.allow(0), true);
  assert.equal(limiter.allow(0), false);
});

test('extracts MiniMax base64 WAV audio', async () => {
  const { synthesizeMiniMax } = await import('./qq-gemini-tts.mjs');
  const wav = Buffer.from('RIFFmini-test');
  const result = await synthesizeMiniMax('嗯', { apiKey: 'test', fetchImpl: async () => new Response(JSON.stringify({ data: { audio: wav.toString('hex') }, extra_info: { audio_sample_rate: 24000 } }), { status: 200 }) });
  assert.deepEqual(result, wav);
});

test('encodes WAV for OneBot record delivery', async () => {
  const { toOneBotAudio } = await import('./qq-gemini-tts.mjs');
  assert.equal(toOneBotAudio(Buffer.from('wav')), 'base64://d2F2');
});

test('adds natural pauses and chooses an emotion for MiniMax', async () => {
  const { prepareMiniMaxText, emotionForText } = await import('./qq-gemini-tts.mjs');
  assert.equal(prepareMiniMaxText('嗯，好吧。你早点睡。'), '嗯，<#0.16#>好吧。<#0.25#>你早点睡。');
  assert.equal(emotionForText('太好了！终于成功了'), 'happy');
  assert.equal(emotionForText('唉，今天有点累'), 'sad');
});

test('voice policy allows longer replies with higher everyday probability', async () => {
  const { shouldSendVoice } = await import('./qq-gemini-tts.mjs');
  assert.equal(shouldSendVoice({ kind: 'private', text: '长回复'.repeat(100), random: () => 0.3, now: 0, lastSentAt: -Infinity, dailyCount: 0 }), true);
  assert.equal(shouldSendVoice({ kind: 'group', text: '好呀', random: () => 0.14, now: 200000, lastSentAt: -Infinity, dailyCount: 0 }), true);
});

test('uses higher voice probability', async () => {
  const { shouldSendVoice } = await import('./qq-gemini-tts.mjs');
  assert.equal(shouldSendVoice({ kind: 'private', text: '好呀', random: () => 0.55, now: 0, lastSentAt: -Infinity, dailyCount: 0 }), true);
  assert.equal(shouldSendVoice({ kind: 'group', text: '好呀', random: () => 0.25, now: 200000, lastSentAt: -Infinity, dailyCount: 0 }), true);
});
