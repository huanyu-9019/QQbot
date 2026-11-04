import test from 'node:test';
import assert from 'node:assert/strict';
import { songIntent, CHORUS_START_SECONDS } from './qq-song-clips.mjs';

test('recognizes direct and fuzzy song requests', () => {
  for (const text of ['给我唱首歌', '唱一下', '哼一段', '来点像小幸运的歌', '你唱那个最近很火的歌', '放首歌']) {
    assert.equal(songIntent(text), true, text);
  }
});

test('does not treat ordinary speech as a song request', () => {
  assert.equal(songIntent('你今天吃饭了吗'), false);
});

test('song clips start at the chorus section, past the intro', () => {
  assert.equal(CHORUS_START_SECONDS, 55);
});
