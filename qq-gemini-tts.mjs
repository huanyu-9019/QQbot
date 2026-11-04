import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

export const DEFAULT_MODEL = 'gemini-3.1-flash-tts-preview';
export const DEFAULT_VOICE = 'Kore';
export const DEFAULT_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta';
export const MINIMAX_BASE_URL = 'https://api.minimaxi.com/v1';
export const VOICE_COOLDOWN_MS = 10 * 1000;
export const MINIMAX_VOICES = ['Chinese (Mandarin)_Warm_Girl'];
export const MAX_VOICE_CHARS = 500;

export function pcmToWav(pcm, sampleRate = 24000, channels = 1, bitsPerSample = 16) {
  const data = Buffer.from(pcm);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0); header.writeUInt32LE(36 + data.length, 4); header.write('WAVE', 8);
  header.write('fmt ', 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20);
  header.writeUInt16LE(channels, 22); header.writeUInt32LE(sampleRate, 24);
  const byteRate = sampleRate * channels * bitsPerSample / 8;
  header.writeUInt32LE(byteRate, 28); header.writeUInt16LE(channels * bitsPerSample / 8, 32);
  header.writeUInt16LE(bitsPerSample, 34); header.write('data', 36); header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

export function shouldSendVoice({ kind, text, random = Math.random, now = Date.now(), lastSentAt = -Infinity, dailyCount = 0 }) {
  const value = String(text ?? '').trim();
  if (!value || value === '<QQ_SILENT>' || value.length > MAX_VOICE_CHARS) return false;
  if (dailyCount >= 10 || now - lastSentAt < VOICE_COOLDOWN_MS) return false;
  const chance = kind === 'group' ? 0.45 : 0.75;
  return random() < chance;
}

export function createVoiceLimiter({ dailyLimit = 10 } = {}) {
  let day = new Date().toISOString().slice(0, 10);
  let count = 0;
  return {
    allow(now = Date.now()) {
      const current = new Date(now).toISOString().slice(0, 10);
      if (current !== day) { day = current; count = 0; }
      if (count >= dailyLimit) return false;
      count += 1;
      return true;
    },
    get count() { return count; },
  };
}

function parseAudioPayload(payload, chunks) {
  const parts = payload?.candidates?.[0]?.content?.parts ?? [];
  for (const part of parts) {
    const data = part?.inlineData?.data ?? part?.inline_data?.data;
    if (data) chunks.push(Buffer.from(data, 'base64'));
  }
}

export async function synthesizeGemini(text, { apiKey, model = DEFAULT_MODEL, voice = DEFAULT_VOICE, baseUrl = DEFAULT_BASE_URL, fetchImpl = fetch } = {}) {
  if (!apiKey) throw new Error('GEMINI_API_KEY missing');
  const url = `${baseUrl.replace(/\/$/, '')}/models/${encodeURIComponent(model)}:streamGenerateContent?alt=sse`;
  const response = await fetchImpl(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-goog-api-key': apiKey },
    body: JSON.stringify({ contents: [{ parts: [{ text: String(text) }] }], generationConfig: { responseModalities: ['AUDIO'], speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } } } }),
    signal: AbortSignal.timeout(60000),
  });
  if (!response.ok) throw new Error(`Gemini TTS HTTP ${response.status}`);
  const raw = await response.text();
  const chunks = [];
  for (const line of raw.split(/\r?\n/)) {
    const value = line.startsWith('data: ') ? line.slice(6).trim() : line.trim();
    if (!value || value === '[DONE]') continue;
    try { parseAudioPayload(JSON.parse(value), chunks); } catch {}
  }
  if (!chunks.length) { try { parseAudioPayload(JSON.parse(raw), chunks); } catch {} }
  if (!chunks.length) throw new Error('Gemini TTS returned no audio');
  return Buffer.concat(chunks);
}

export function prepareMiniMaxText(text) {
  return String(text ?? '').trim()
    .replace(/\s+/g, ' ')
    .replace(/，/g, '，<#0.16#>')
    .replace(/、/g, '、<#0.12#>')
    .replace(/。/g, '。<#0.25#>')
    .replace(/！/g, '！<#0.25#>')
    .replace(/？/g, '？<#0.25#>')
    .replace(/…+/g, '……<#0.35#>')
    .replace(/\s*<#[^>]+#>\s*([，、。！？])/g, '$1')
    .replace(/(<#[^>]+#>)$/g, '');
}

export function emotionForText(text) {
  const value = String(text ?? '');
  if (/[哈哈哈！太好了|开心|喜欢|可爱|好耶]/.test(value)) return 'happy';
  if (/[唉|累|难过|伤心|抱歉|烦]/.test(value)) return 'sad';
  if (/[生气|气死|讨厌|离谱]/.test(value)) return 'angry';
  if (/[嗯|好吧|知道了|晚安]/.test(value)) return 'calm';
  return 'neutral';
}

export function toOneBotAudio(audio) { return `base64://${Buffer.from(audio).toString('base64')}`; }

export async function synthesizeMiniMax(text, { apiKey, model = 'speech-2.6-hd', voice = MINIMAX_VOICES[Math.floor(Math.random() * MINIMAX_VOICES.length)], baseUrl = MINIMAX_BASE_URL, fetchImpl = fetch } = {}) {
  if (!apiKey) throw new Error('MINIMAX_API_KEY missing');
  const response = await fetchImpl(`${baseUrl.replace(/\/$/, '')}/t2a_v2`, {
    method: 'POST', headers: { 'content-type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({ model, text: prepareMiniMaxText(text), voice_setting: { voice_id: voice, emotion: emotionForText(text), speed: 1, vol: 1, pitch: 0, language_boost: 'Chinese' }, audio_setting: { format: 'mp3' } }),
    signal: AbortSignal.timeout(60000),
  });
  if (!response.ok) throw new Error(`MiniMax TTS HTTP ${response.status}`);
  const payload = await response.json();
  if (!payload?.data?.audio) throw new Error('MiniMax TTS returned no audio');
  return Buffer.from(String(payload.data.audio), /^[0-9a-f]+$/i.test(String(payload.data.audio)) ? 'hex' : 'base64');
}

export async function synthesizeMiniMaxToFile(text, options = {}) {
  const audio = await synthesizeMiniMax(text, options);
  const dir = options.tempDir ?? path.join(os.tmpdir(), 'qq-hermes-voice');
  await fs.mkdir(dir, { recursive: true, mode: 0o700 });
  const file = path.join(dir, `voice-${Date.now()}-${crypto.randomBytes(5).toString('hex')}.wav`);
  await fs.writeFile(file, audio);
  return file;
}

export async function synthesizeToFile(text, options = {}) {
  const pcm = await synthesizeGemini(text, options);
  const dir = options.tempDir ?? path.join(os.tmpdir(), 'qq-hermes-voice');
  await fs.mkdir(dir, { recursive: true, mode: 0o700 });
  const file = path.join(dir, `voice-${Date.now()}-${crypto.randomBytes(5).toString('hex')}.wav`);
  await fs.writeFile(file, pcmToWav(pcm, options.sampleRate ?? 24000));
  return file;
}

export async function cleanupVoiceFiles(dir, maxAgeMs = 60 * 60 * 1000) {
  const entries = await fs.readdir(dir, { withFileTypes: true }).catch(() => []);
  const cutoff = Date.now() - maxAgeMs;
  await Promise.all(entries.filter(x => x.isFile() && x.name.endsWith('.wav')).map(async entry => {
    const file = path.join(dir, entry.name);
    const stat = await fs.stat(file).catch(() => null);
    if (stat && stat.mtimeMs < cutoff) await fs.unlink(file).catch(() => {});
  }));
}