import { promises as fs } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';
import crypto from 'node:crypto';

const SEARCH_URL = 'https://music.163.com/api/search/get/web';
const AUDIO_URL = id => `https://music.163.com/song/media/outer/url?id=${id}.mp3`;
export const CHORUS_START_SECONDS = 55;
const FEMALE_HINT = /女声|女生|女版|翻唱|cover|girl|female|live女/i;

function cleanQuery(text) {
  return String(text ?? '').replace(/^(?:江生[，,、 ]*)?/, '').replace(/(?:给我|帮我|请|来|唱一下|唱首歌|唱一首|唱歌|唱唱|唱|像|类似|那首|的歌|这首|放一首|放首|播一首|播放|听一下|听首歌)/gi, ' ').replace(/[，。！？!?、,.：:；;“”"'‘’]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
}

function request(url, options = {}) {
  return fetch(url, { ...options, headers: { 'user-agent': 'Mozilla/5.0', ...(options.headers ?? {}) }, signal: AbortSignal.timeout(options.timeout ?? 15000) });
}

async function search(query) {
  const variants = [query, `${query} 女声`, `${query} 翻唱 女生`, "女声 翻唱"].filter(Boolean);
  for (const term of variants) {
    const response = await request(`${SEARCH_URL}?${new URLSearchParams({ s: term, type: '1', offset: '0', total: 'true', limit: '10' })}`);
    if (!response.ok) continue;
    const body = await response.json();
    const songs = Array.isArray(body?.result?.songs) ? body.result.songs : [];
    if (!songs.length) continue;
    const female = songs.filter(song => FEMALE_HINT.test(`${song.name} ${(song.artists ?? []).map(x => x.name).join(' ')}`));
    if (female.length) return female[0];
  }
  return null;
}

async function runFfmpeg(input, output, offset = CHORUS_START_SECONDS) {
  await new Promise((resolve, reject) => {
    const child = spawn('/usr/bin/ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(offset), '-i', input, '-t', '15', '-vn', '-ac', '1', '-ar', '24000', '-c:a', 'libopus', '-b:a', '32k', output]);
    let error = ''; child.stderr.on('data', chunk => { error += chunk; });
    child.on('error', reject); child.on('close', code => code === 0 ? resolve() : reject(new Error(error || `ffmpeg exited ${code}`)));
  });
}

export function songIntent(text) { return /(?:唱|哼|来点|点一首|放一首|放首|播放|听一下|听首歌|来首)/i.test(String(text ?? '')); }

export async function fetchFemaleSongClip(text, { dir = '/home/hermes/.cache/qq-hermes-song' } = {}) {
  const query = cleanQuery(text);
  if (!query) throw new Error('song query empty');
  const song = await search(query);
  if (!song?.id) throw new Error('song unavailable');
  await fs.mkdir(dir, { recursive: true, mode: 0o700 });
  const token = crypto.randomBytes(6).toString('hex');
  const source = path.join(dir, `${token}.source`);
  const output = path.join(dir, `${token}.ogg`);
  try {
    const response = await request(AUDIO_URL(song.id), { redirect: 'follow', timeout: 20000 });
    if (!response.ok || !response.body) throw new Error(`audio HTTP ${response.status}`);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length < 4096) throw new Error('audio too small');
    await fs.writeFile(source, bytes, { mode: 0o600 });
    await runFfmpeg(source, output);
    const audio = await fs.readFile(output);
    return { audio, title: String(song.name ?? query), startSeconds: CHORUS_START_SECONDS, artist: (song.artists ?? []).map(x => x.name).join('、') };
  } finally { await Promise.allSettled([fs.unlink(source), fs.unlink(output)]); }
}