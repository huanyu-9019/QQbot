import test from 'node:test';
import assert from 'node:assert/strict';
import { parseIncoming } from './qq-media.mjs';

const config = { imagesEnabled: true, maxImages: 4 };

test('image-only messages are neutral visual context, not an analysis request', () => {
  const result = parseIncoming([{ type: 'image', data: { url: 'https://multimedia.nt.qq.com.cn/a' } }], { kind: 'private', mentioned: false }, config);
  assert.equal(result.text, '对方发来了一张图片，仅作聊天语气参考。');
});

test('mface-only messages are treated as conversational tone', () => {
  const result = parseIncoming([{ type: 'mface', data: { url: 'https://multimedia.nt.qq.com.cn/a' } }], { kind: 'group', mentioned: false }, config);
  assert.equal(result.text, '对方发来一个表情，仅作聊天语气参考。');
});
